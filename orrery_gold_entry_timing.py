# SPDX-License-Identifier: GPL-3.0-only
"""Compare fixed early, confirmed and no-trade policies for the same Gold setups."""
import argparse
from collections import Counter
import json
from pathlib import Path

from orrery_gold_pullback_study import (
    END, START, WINDOWS, describe, entry_opportunities, evaluate_pullback, load_archive, replay,
)
from orrery_paired_archive_study import REVISION, iso

TARGET = 0.5
FRICTION = 0.30
KNOWN_NO_TRADE = {'STRUCTURE_BREACHED_BEFORE_ENTRY', 'STOP_INVALID_AT_ENTRY',
                  'NO_OBSERVED_CONFIRMATION'}


def outcome(signal, bid, ask):
    return evaluate_pullback(dict(first_poi_touch_close=signal['at_utc'], side=signal['side']),
                             bid, ask, structural_stop=signal['stop'],
                             structural_known_at=signal['setup_at_utc'], target_r=TARGET)


def net(row):
    if row['status'] in KNOWN_NO_TRADE:
        return 0.0
    if row['status'] == 'RESOLVED_REFERENCE':
        return row['r']-FRICTION/row['initial_risk_price']
    return None


def compare(pairs, start, end):
    cohort = [pair for pair in pairs if start <= pair['setup'] < end]
    early = [net(pair['early']) for pair in cohort]
    wait = [net(pair['wait']) for pair in cohort]
    matched = [(a, b) for a, b in zip(early, wait) if a is not None and b is not None]
    by_wait = {}
    for state, count in Counter(pair['wait']['status'] for pair in cohort).items():
        values = [a for pair, a in zip(cohort, early) if pair['wait']['status'] == state and a is not None]
        by_wait[state] = dict(setups=count, early_known=len(values),
                              early_positive=sum(a > 0 for a in values),
                              early_negative=sum(a < 0 for a in values),
                              early_total_r=sum(values))
    return dict(setups=len(cohort), paired_evaluable=len(matched),
                paired_unknown=len(cohort)-len(matched),
                early_r_per_evaluable_setup=sum(a for a, _ in matched)/len(matched) if matched else None,
                wait_r_per_evaluable_setup=sum(b for _, b in matched)/len(matched) if matched else None,
                no_trade_r_per_setup=0.0, by_wait_status=by_wait)


def run(root):
    bid, ask, m5, m15, h1, audit = load_archive(root)
    opportunities = [(early, wait) for early, wait in entry_opportunities(m5, m15, h1, ask)
                     if early['at_utc'] < END]
    m5_clocks = {row['close_time'] for row in m5}
    pairs = []
    for early, wait in opportunities:
        setup = early['at_utc']
        window_complete = all(at in m5_clocks for at in range(setup+300, setup+901, 300))
        if wait is not None and wait['at_utc'] < END:
            waiting = outcome(wait, bid, ask)
        else:
            waiting = dict(status='NO_OBSERVED_CONFIRMATION' if window_complete and setup+900 < END
                           else 'UNKNOWN_CONFIRMATION_WINDOW')
        pairs.append(dict(setup=setup, early=outcome(early, bid, ask), wait=waiting))
    early_signals = [early for early, _ in opportunities]
    wait_signals = {}
    for _, wait in sorted(opportunities, key=lambda pair: pair[1]['at_utc'] if pair[1] else END):
        if wait is not None and wait['at_utc'] < END:
            wait_signals.setdefault(wait['at_utc'], wait)
    operational = {}
    for name, items in (('early', early_signals), ('wait', wait_signals.values())):
        rows, skips = replay(items, bid, ask, TARGET)
        operational[name] = dict(skipped_while_occupied=skips, overall=describe(rows, START, END),
                                 by_period={k: describe(rows, a, b) for k, (a, b) in WINDOWS.items()})
    return dict(source_revision=REVISION, paired_minutes=audit['paired_minutes'],
                start_utc=iso(START), end_utc_exclusive=iso(END), target_r=TARGET, extra_cost=FRICTION,
                opportunity_comparison=compare(pairs, START, END),
                by_setup_period={k: compare(pairs, a, b) for k, (a, b) in WINDOWS.items()},
                operational=operational, out_of_sample=False,
                account_return_pct=None, adoption_allowed=False, execution_allowed=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive_directory', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    payload = json.dumps(run(args.archive_directory), indent=2, allow_nan=False)
    with args.output.open('x', encoding='utf-8', newline='\n') as output:
        output.write(payload + '\n')
