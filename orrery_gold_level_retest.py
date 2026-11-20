# SPDX-License-Identifier: GPL-3.0-only
"""Compare immediate and confirmed level-retest entries on fixed Gold breakouts."""
import argparse
from collections import Counter
import json
from pathlib import Path
from statistics import mean

from orrery_gold_compression_study import END, START
from orrery_gold_conditional_exit import COST, RESOLVED, net, stats
from orrery_gold_expectancy_study import retarget
from orrery_gold_probability_study import candidates
from orrery_gold_pullback_study import evaluate_pullback, load_archive
from orrery_gold_session_breakout import Q4_START, load_q4
from orrery_gold_nested_wave_october import complete_m5

TARGET_R = 0.5
NO_TRADE = {'NO_RETEST', 'STRUCTURE_BREACHED_BEFORE_ENTRY',
            'TARGET_REACHED_BEFORE_ENTRY', 'TARGET_INVALID_AT_ENTRY', 'STOP_INVALID_AT_ENTRY'}


def wait_for_retest(row, level, target, m5, bid, ask):
    start = row['at_utc']
    buy = row['side'] == 'BUY'
    exit_side = bid if buy else ask
    stop = row['stop']
    for close in range(start+300, start+1801, 300):
        bar = m5.get(close)
        if bar is None:
            return {'status': 'UNKNOWN_RETEST_HISTORY'}
        for stamp in range(close-300, close, 60):
            quote = exit_side[stamp]
            stopped = quote['low'] <= stop if buy else quote['high'] >= stop
            reached = quote['high'] >= target if buy else quote['low'] <= target
            if stopped or reached:
                return {'status': ('STRUCTURE_BREACHED_BEFORE_ENTRY' if stopped
                                   else 'TARGET_REACHED_BEFORE_ENTRY')}
        confirmed = bar['low'] <= level < bar['close'] if buy else bar['high'] >= level > bar['close']
        if confirmed:
            return evaluate_pullback(
                {'first_poi_touch_close': close, 'side': row['side']}, bid, ask,
                structural_stop=stop, structural_known_at=close,
                target_price=target, horizon=(start+3600-close)//60,
            )
    return {'status': 'NO_RETEST'}


def score(row):
    if row['status'] in NO_TRADE:
        return 0.0
    if row['status'] == RESOLVED:
        return net(row)
    return None


def measure(bid, ask, m5, m15, start, end):
    clocks = {row['close_time']: row for row in m15}
    m5 = {row['close_time']: row for row in m5}
    cohort = candidates(bid, ask, m15, end)
    pairs = []
    entries = []
    for row in cohort:
        at = row['at_utc']
        immediate = retarget(row, bid, ask, TARGET_R)
        if at not in bid or at not in ask:
            waiting = {'status': 'UNKNOWN_ENTRY_HISTORY'}
        elif immediate['status'] == 'STOP_INVALID_AT_ENTRY':
            waiting = {'status': 'STOP_INVALID_AT_ENTRY'}
        else:
            buy = row['side'] == 'BUY'
            prior = [clocks[t] for t in range(at-3600, at, 900)]
            level = max(x['high'] for x in prior) if buy else min(x['low'] for x in prior)
            direction = 1 if buy else -1
            entry = (ask if buy else bid)[at]['open']
            target = entry+TARGET_R*(entry-row['stop'])
            waiting = wait_for_retest(row, level, target, m5, bid, ask)
            if waiting['status'] == RESOLVED:
                entries.append(direction*(entry-waiting['entry']))
        pairs.append((immediate, waiting))
    matched = [(score(a), score(b)) for a,b in pairs]
    matched = [(a,b) for a,b in matched if a is not None and b is not None]
    immediate = stats([a for a,_ in pairs])
    waiting = stats([b for _, b in pairs if b['status'] not in NO_TRADE])
    known_no_trade = sum(b['status'] in NO_TRADE for _, b in pairs)
    return dict(
        base_candidates=len(pairs), common_known=len(matched), common_unknown=len(pairs)-len(matched),
        immediate=immediate, wait=waiting, wait_known_no_trade=known_no_trade,
        wait_dispositions=dict(Counter(b['status'] for _,b in pairs)),
        immediate_resolved_per_week=immediate['resolved']*604800/(end-start),
        wait_resolved_per_week=waiting['resolved']*604800/(end-start),
        mean_entry_improvement_price=mean(entries) if entries else None,
        mean_r_per_common_candidate_immediate=mean(a for a,_ in matched) if matched else None,
        mean_r_per_common_candidate_wait=mean(b for _,b in matched) if matched else None,
    )


def run(root_2026, root_q4):
    bid, ask, m15, _ = load_q4(root_q4)
    pairs = {t: bid[t] for t in bid.keys() & ask.keys()}
    old = measure(bid, ask, complete_m5(pairs, Q4_START, START), m15, Q4_START, START)
    bid, ask, m5, m15, _, _ = load_archive(root_2026)
    recent = measure(bid, ask, m5, m15, START, END)
    return dict(target_r_at_breakout=TARGET_R, extra_round_trip_price=COST,
                historical_2026=recent, separate_2025_q4=old,
                retrospective=True, account_return_pct=None,
                diagnostic_allows_overlap=True, adoption_allowed=False, execution_allowed=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive_2026', type=Path)
    parser.add_argument('archive_2025_q4', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    with args.output.open('x', encoding='utf-8', newline='\n') as output:
        json.dump(run(args.archive_2026, args.archive_2025_q4), output, indent=2, allow_nan=False)
        output.write('\n')
