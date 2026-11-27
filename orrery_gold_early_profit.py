# SPDX-License-Identifier: GPL-3.0-only
"""Measure SL rescues and foregone gains with a fixed half-R Gold profit cap."""
import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
from statistics import mean

from orrery_gold_loss_attribution import (
    END, EVIDENCE, Q4_START, RESOLVED, START, attribute, band_measure,
    breakout_signals, load_archive, load_q4, replay, stats,
)
from orrery_gold_pullback_study import evaluate_pullback
from orrery_gold_conditional_exit import net

CAP_R = 0.5


def capped_result(row, bid, ask):
    at, side = row['at_utc'], row['side']
    if at not in bid or at not in ask:
        return dict(at_utc=at, side=side, status='UNKNOWN_ENTRY_HISTORY')
    buy = side == 'BUY'
    sign = 1 if buy else -1
    entry = (ask if buy else bid)[at]['open']
    stop = row.get('stop')
    if stop is None:
        stop = (bid if buy else ask)[at]['open']-sign*row['stop_distance']
    risk = sign*(entry-stop)
    original_target = row.get('target', entry+sign*1.5*risk)
    target = entry+sign*min(CAP_R*risk, sign*(original_target-entry))
    return dict(at_utc=at, **evaluate_pullback(
        dict(first_poi_touch_close=at, side=side), bid, ask,
        structural_stop=stop, structural_known_at=at, target_price=target, horizon=60,
    ))


def compare(rows, bid, ask):
    capped = [capped_result(row, bid, ask) for row in rows]
    paired = [(a,b) for a,b in zip(rows,capped) if a['status'] == b['status'] == RESOLVED]
    by_exit = {}
    for reason in sorted({a['exit_reason'] for a,b in paired}):
        cohort = [(a,b) for a,b in paired if a['exit_reason'] == reason]
        by_exit[reason] = dict(count=len(cohort),
                              changed_to_tp=sum(b['exit_reason'] == 'TP_TOUCH' for a,b in cohort),
                              capped_positive=sum(net(b)>0 for a,b in cohort),
                              net_total_change_r=sum(net(b)-net(a) for a,b in cohort))
    return dict(
        baseline=stats(rows), capped=stats(capped),
        paired_resolved=len(paired), paired_unresolved=len(rows)-len(paired),
        matched_baseline=stats([a for a,b in paired]), matched_capped=stats([b for a,b in paired]),
        mean_change_r=mean(net(b)-net(a) for a,b in paired) if paired else None,
        by_original_exit=by_exit,
        transitions=dict(Counter(f"{a['status']} -> {b['status']}" for a,b in zip(rows,capped))),
    )


def measure(bid, ask, bars, start, end, expected):
    breakout, _ = replay(breakout_signals(bars, ask, end), bid, ask, 1.5, horizon=60)
    band = []
    band_measure(bid, ask, bars, start, end, row_sink=band)
    result = {}
    for name, rows in (('breakout', breakout), ('band_reentry', band)):
        if attribute(rows, start, end) != expected[name]:
            raise ValueError(f'Baseline does not reproduce: {name}')
        result[name] = compare(rows, bid, ask)
    return result


def run(root, prior_root):
    raw = (EVIDENCE/'gold_loss_attribution_summary.json').read_bytes()
    expected = json.loads(raw)
    bid, ask, _, bars, _, _ = load_archive(root)
    recent = measure(bid, ask, bars, START, END, expected['historical_2026'])
    bid, ask, bars, _ = load_q4(prior_root)
    old = measure(bid, ask, bars, Q4_START, START, expected['separate_2025_q4'])
    return dict(profit_cap_r=CAP_R, baseline_sha256=sha256(raw).hexdigest(),
                historical_2026=recent, separate_2025_q4=old,
                fixed_entries_can_overlap=True, out_of_sample=False,
                execution_allowed=False, adoption_allowed=False, account_return_pct=None)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive_2026', type=Path)
    parser.add_argument('archive_2025_q4', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    with args.output.open('x', encoding='utf-8', newline='\n') as output:
        json.dump(run(args.archive_2026, args.archive_2025_q4), output, indent=2, allow_nan=False)
        output.write('\n')
