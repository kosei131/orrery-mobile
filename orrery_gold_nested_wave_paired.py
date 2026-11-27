# SPDX-License-Identifier: GPL-3.0-only
"""Compare unchanged Gold signals using Bid or matched Ask entry references."""
import argparse
import json
from pathlib import Path

from orrery_gold_nested_wave_holdout import replay_window
from orrery_gold_nested_wave_october import (
    END, SEPTEMBER, SOURCE, complete_m5, read_pinned,
)


def run(root):
    bid_sep, bid_sep_audit = read_pinned(root / 'bid_2026_09.csv', 'bid_2026_09.csv')
    bid_oct, bid_oct_audit = read_pinned(root / SOURCE, SOURCE)
    ask_sep, ask_sep_audit = read_pinned(root / 'ask_2026_09.csv', 'ask_2026_09.csv')
    ask_oct, ask_oct_audit = read_pinned(root / 'ask_2026_10.csv', 'ask_2026_10.csv')
    bid, ask = bid_sep | bid_oct, ask_sep | ask_oct
    bars = complete_m5(bid, SEPTEMBER, END)
    ask_opens = {
        stamp: ask[stamp]['open'] for stamp in bid.keys() & ask.keys()
        if stamp % 300 == 0 and ask[stamp]['open'] >= bid[stamp]['open']
    }
    baseline = replay_window(bars, start=SEPTEMBER, end=END)
    paired = replay_window(bars, start=SEPTEMBER, end=END, buy_ask_open_by_clock=ask_opens)
    comparisons = []
    for name in ('immediate', 'delayed', 'delayed_with_room_gate'):
        for a, b in zip(baseline[name]['records'], paired[name]['records'], strict=True):
            if a['candidate_id'] != b['candidate_id']:
                raise ValueError('Candidate identity changed')
            clock = a['known_at_utc']
            spread = ask_opens[clock] - bid[clock]['open'] if clock in ask_opens else None
            comparisons.append(dict(arm=name, candidate_id=a['candidate_id'],
                                    observed_open_spread_price=spread,
                                    bid_entry=a, ask_entry=b))
    return dict(
        status='THIRD_PARTY_PAIRED_OHLC_PRICE_REFERENCE',
        source_audits=[bid_sep_audit, bid_oct_audit, ask_sep_audit, ask_oct_audit],
        baseline=baseline, paired=paired, comparisons=comparisons,
        paired_cost_note='Scenario zero includes the quoted entry spread through Ask/Bid; other scenarios add hypothetical friction.',
        independent_source_authentication=False, out_of_sample=False,
        actual_broker_profit=None, execution_allowed=False, adoption_allowed=False,
    )


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive_directory', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    payload = json.dumps(run(args.archive_directory), indent=2, allow_nan=False)
    with args.output.open('x', encoding='utf-8', newline='\n') as output:
        output.write(payload + '\n')
