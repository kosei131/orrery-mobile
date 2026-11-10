# SPDX-License-Identifier: GPL-3.0-only
"""Audit unchanged A/B Bid/Ask brackets against the corresponding minute series."""
import argparse
import json
from pathlib import Path

from orrery_gold_ab_archive_sides import run as paired_replay
from orrery_gold_entry_family_comparison import describe
from orrery_gold_mtf_ab_price_references import VALID_FAMILIES
from orrery_gold_nested_wave_minute import minute_exit
from orrery_gold_nested_wave_october import END, read_pinned


def run(root):
    paired = paired_replay(root)
    prices = {}
    for side in ('bid', 'ask'):
        first, _ = read_pinned(root / f'{side}_2026_09.csv', f'{side}_2026_09.csv')
        second, _ = read_pinned(root / f'{side}_2026_10.csv', f'{side}_2026_10.csv')
        prices[side] = first | second
    records, comparisons = [], []
    for item in paired['comparisons']:
        original = item['paired']
        exit_side = 'bid' if original['side'] == 'BUY' else 'ask'
        updated = minute_exit(original, prices[exit_side], end=END)
        records.append(updated)
        comparisons.append(dict(candidate_id=original['candidate_id'], exit_side=exit_side,
                                m5_state=original['state'], m1_state=updated['state'],
                                m5_r=original['reference_r'], m1_r=updated['reference_r'],
                                m5_close=original['exit_m5_close'], m1_close=updated['exit_m1_close']))
    return dict(
        status='GOLD_AB_SIDE_LABELED_M1_EXIT_ORDER_AUDIT',
        source_audits=paired['source_audits'],
        m5=paired['paired_families'],
        m1={family: describe([row for row in records if row['family'] == family])
            for family in VALID_FAMILIES},
        comparisons=comparisons, actual_broker_profit=None, out_of_sample=False,
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
