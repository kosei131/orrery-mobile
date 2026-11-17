# SPDX-License-Identifier: GPL-3.0-only
"""Attribute reference Gold results by exit with identical source windows."""
import argparse
from collections import Counter, defaultdict
from hashlib import sha256
import json
from pathlib import Path

from orrery_gold_band_reentry import measure as band_measure
from orrery_gold_compression_study import signals as breakout_signals
from orrery_gold_conditional_exit import COST, RESOLVED, stats
from orrery_gold_nested_wave_october import complete_m5
from orrery_gold_pullback_study import END, START, load_archive, replay
from orrery_gold_session_breakout import Q4_START, load_q4

EVIDENCE = Path(__file__).with_name('research_evidence') / 'local-history-20261101'


def attribute(rows, start, end):
    groups = defaultdict(list)
    resolved = [row for row in rows if row['status'] == RESOLVED]
    for row in resolved:
        groups[row['exit_reason']].append(row)
    exits = {}
    for reason, items in sorted(groups.items()):
        gross = sum(row['r'] for row in items)
        cost = sum(COST/row['initial_risk_price'] for row in items)
        exits[reason] = dict(count=len(items), gross_r=gross, extra_cost_r=cost,
                             net_r=gross-cost, net_r_per_all_resolved=(gross-cost)/len(resolved))
    gross = sum(row['r'] for row in resolved)
    cost = sum(COST/row['initial_risk_price'] for row in resolved)
    return dict(
        summary=stats(rows), resolved_per_calendar_week=len(resolved)*604800/(end-start),
        statuses=dict(Counter(row['status'] for row in rows)), exit_contributions=exits,
        total_gross_r=gross, extra_cost_r=cost, total_net_r=gross-cost,
        gross_mean_r=gross/len(resolved) if resolved else None,
    )


def measure(bid, ask, bars, start, end, expected_breakout, expected_band):
    breakout, _ = replay(breakout_signals(bars, ask, end), bid, ask, 1.5, horizon=60)
    baseline = stats(breakout)
    if (baseline['resolved'] != expected_breakout['resolved'] or
        abs(baseline['mean_r']-expected_breakout['scenarios'][1]['mean_resolved_r']) > 1e-12):
        raise ValueError('Breakout baseline changed')
    band_rows = []
    actual = band_measure(bid, ask, bars, start, end, row_sink=band_rows)
    if actual != expected_band:
        raise ValueError('Band baseline changed')
    return dict(breakout=attribute(breakout, start, end),
                band_reentry=attribute(band_rows, start, end), baselines_reproduced=True)


def run(root, prior_root):
    compression_bytes = (EVIDENCE/'gold_compression_summary.json').read_bytes()
    band_bytes = (EVIDENCE/'gold_band_reentry_summary.json').read_bytes()
    compression, band = json.loads(compression_bytes), json.loads(band_bytes)
    bid, ask, _, bars, _, _ = load_archive(root)
    recent = measure(bid, ask, bars, START, END,
                     compression['historical_2026']['arms']['all_60'], band['historical_2026'])
    bid, ask, bars, _ = load_q4(prior_root)
    older = measure(bid, ask, bars, Q4_START, START,
                    compression['separate_2025_q4']['arms']['all_60'], band['separate_2025_q4'])
    return dict(historical_2026=recent, separate_2025_q4=older,
                baseline_sha256=dict(compression=sha256(compression_bytes).hexdigest(),
                                     band=sha256(band_bytes).hexdigest()),
                out_of_sample=False, execution_allowed=False, adoption_allowed=False,
                account_return_pct=None)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive_2026', type=Path)
    parser.add_argument('archive_2025_q4', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    with args.output.open('x', encoding='utf-8', newline='\n') as output:
        json.dump(run(args.archive_2026, args.archive_2025_q4), output, indent=2, allow_nan=False)
        output.write('\n')
