# SPDX-License-Identifier: GPL-3.0-only
"""Reprice existing Gold A/B candidates using paired side-labeled M5 OHLC."""
import argparse
import json
from pathlib import Path

from orrery_gold_ab_archive_comparison import aggregate_complete, run as baseline
from orrery_gold_entry_family_comparison import describe
from orrery_gold_mtf_ab_price_references import VALID_FAMILIES, evaluate
from orrery_gold_nested_wave_october import END, SEPTEMBER, complete_m5, read_pinned


def run(root):
    reference = baseline(root)
    sides, audits = {}, {}
    for side in ('bid', 'ask'):
        minutes = {}
        for month in ('09', '10'):
            name = f'{side}_2026_{month}.csv'
            rows, audits[name] = read_pinned(root / name, name)
            if minutes.keys() & rows.keys():
                raise ValueError('Archive months overlap')
            minutes.update(rows)
        sides[side] = [row for row in complete_m5(minutes, SEPTEMBER, END)
                       if row['close_time'] < END]
    bid = {row['open_time']: row['open'] for row in sides['bid']}
    ask = {row['open_time']: row['open'] for row in sides['ask']}
    matched = {clock for clock in bid.keys() & ask.keys() if ask[clock] >= bid[clock]}
    candidates = reference['scan']['candidates']
    results = {}
    for side, exit_side, entry_arg, opens in (
            ('BUY', 'bid', 'buy_ask_open_by_clock', ask),
            ('SELL', 'ask', 'sell_bid_open_by_clock', bid)):
        selected = [row for row in candidates if row['side'] == side]
        bars = aggregate_complete(sides[exit_side], 300)
        rows = evaluate(bars, selected, **{entry_arg: {clock: opens[clock] for clock in matched}})
        results.update((row['candidate_id'], row) for row in rows['records'])
    if results.keys() != {row['candidate_id'] for row in reference['records']}:
        raise ValueError('Candidate identity drift')
    paired = [results[row['candidate_id']] for row in reference['records']]
    return dict(
        status='GOLD_AB_PAIRED_OHLC_PRICE_REFERENCE', source_audits=audits,
        baseline_families=reference['families'],
        paired_families={family: describe([row for row in paired if row['family'] == family])
                         for family in VALID_FAMILIES},
        comparisons=[
            dict(candidate_id=old['candidate_id'], baseline=old, paired=new,
                 opening_spread_price=ask[old['known_at_utc']]-bid[old['known_at_utc']]
                 if old['known_at_utc'] in matched else None)
            for old, new in zip(reference['records'], paired, strict=True)
        ],
        cost_note='The zero additional cost scenario embeds the quoted spread. Fees and slippage are unverified.',
        out_of_sample=False, actual_broker_profit=None,
        execution_allowed=False, adoption_allowed=False,
    )


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive_directory', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    payload = json.dumps(run(args.archive_directory), indent=2, allow_nan=False)
    with args.output.open('x', encoding='utf-8', newline='\n') as output:
        output.write(payload + '\n')
