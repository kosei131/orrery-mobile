# SPDX-License-Identifier: GPL-3.0-only
"""Test inverted pullback barriers and a separate failed-breakout hypothesis."""
import argparse
import json
from pathlib import Path

from orrery_gold_pullback_study import (
    END, START, WINDOWS, describe, entry_opportunities, load_archive, replay,
)
from orrery_paired_archive_study import REVISION, iso

EARLY_TARGET = 0.5
RECLAIM_TARGET = 1.5
LOOKBACK = 20
M15 = 900


def reverse_signals(early, bid, ask):
    for signal in early:
        at = signal['at_utc']
        if at not in bid or at not in ask:
            continue
        buy = signal['side'] == 'BUY'
        direction = 1 if buy else -1
        exit_open = (bid if buy else ask)[at]['open']
        original_stop = signal['stop']
        if direction*(exit_open-original_stop) <= 0:
            continue
        entry = (ask if buy else bid)[at]['open']
        original_risk = direction*(entry-original_stop)
        original_target = entry + direction*EARLY_TARGET*original_risk
        yield dict(signal, side='SELL' if buy else 'BUY', stop=original_target,
                   target_price=original_stop)


def reclaims(m15, ask):
    for index in range(LOOKBACK, len(m15)):
        bar = m15[index]
        at = bar['close_time']
        if at >= END:
            break
        prior = m15[index-LOOKBACK:index]
        if prior[0]['close_time'] != at-LOOKBACK*M15:
            continue
        low = min(row['low'] for row in prior)
        high = max(row['high'] for row in prior)
        broke_low = bar['low'] < low
        broke_high = bar['high'] > high
        if broke_low == broke_high or not low < bar['close'] < high:
            continue
        stop = bar['low'] if broke_low else max(ask[t]['high'] for t in range(at-M15, at, 60))
        yield dict(at_utc=at, side='BUY' if broke_low else 'SELL', setup_at_utc=at, stop=stop)


def run(root):
    bid, ask, m5, m15, h1, audit = load_archive(root)
    early = [a for a, _ in entry_opportunities(m5, m15, h1, ask) if a['at_utc'] < END]
    inverse = list(reverse_signals(early, bid, ask))
    common_clocks = {row['at_utc'] for row in inverse}
    paired_early = [row for row in early if row['at_utc'] in common_clocks]
    arms = {}
    for label, candidates, target in (
        ('original_common', paired_early, EARLY_TARGET),
        ('reverse_swapped', inverse, EARLY_TARGET),
        ('failed_breakout', list(reclaims(m15, ask)), RECLAIM_TARGET),
    ):
        rows, skips = replay(candidates, bid, ask, target)
        arms[label] = dict(raw_candidates=len(candidates), skipped_while_occupied=skips,
                           overall=describe(rows, START, END),
                           by_period={k: describe(rows, a, b) for k, (a,b) in WINDOWS.items()})
    return dict(source_revision=REVISION, paired_minutes=audit['paired_minutes'],
                start_utc=iso(START), end_utc_exclusive=iso(END),
                early_source_setups=len(early), inverse_invalid_or_missing=len(early)-len(inverse),
                arms=arms, out_of_sample=False, account_return_pct=None,
                adoption_allowed=False, execution_allowed=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive_directory', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    payload = json.dumps(run(args.archive_directory), indent=2, allow_nan=False)
    with args.output.open('x', encoding='utf-8', newline='\n') as output:
        output.write(payload + '\n')
