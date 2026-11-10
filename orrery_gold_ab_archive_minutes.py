# SPDX-License-Identifier: GPL-3.0-only
"""Audit unchanged A/B Bid/Ask brackets against the corresponding minute series."""
import argparse
from decimal import Decimal
import json
from pathlib import Path

from orrery_gold_ab_archive_sides import run as paired_replay
from orrery_gold_entry_family_comparison import describe
from orrery_gold_mtf_ab_price_references import VALID_FAMILIES
from orrery_gold_nested_wave_minute import minute_exit
from orrery_gold_nested_wave_october import END, read_pinned


def audit_timeout(record, prices):
    """Describe the observed path of a position still open at its time limit."""
    sign = 1 if record['side'] == 'BUY' else -1
    entry, stop, target = (Decimal(record[key]) for key in
                           ('entry_open_reference', 'structural_stop', 'target_reference'))
    risk = sign*(entry-stop)
    planned = sign*(target-entry)
    start, end = record['known_at_utc'], record['exit_m1_close']
    if end != start + 7200 or any(t not in prices for t in range(start, end, 60)):
        raise ValueError('Complete 120-minute timeout path required')
    extreme = 'high' if sign == 1 else 'low'
    moves = [sign*(Decimal(str(prices[t][extreme]))-entry) for t in range(start, end, 60)]
    best = max(moves)
    final = sign*(Decimal(str(prices[end-60]['close']))-entry)
    if best >= planned or float(final/risk) != record['reference_r']:
        raise ValueError('Timeout path disagrees with fixed bracket')
    return dict(candidate_id=record['candidate_id'], side=record['side'],
                target_r=float(planned/risk), peak_reference_r=float(best/risk),
                target_fraction_at_peak=float(best/planned),
                peak_minute_close=moves.index(best)+1,
                timeout_reference_r=float(final/risk),
                peak_to_exit_giveback_r=float((best-final)/risk),
                mark_reference_r={
                    str(minutes): float(sign*(Decimal(str(prices[start+(minutes-1)*60]['close']))-entry)/risk)
                    for minutes in (30, 60, 90, 120)
                })



def run(root):
    paired = paired_replay(root)
    prices = {}
    for side in ('bid', 'ask'):
        first, _ = read_pinned(root / f'{side}_2026_09.csv', f'{side}_2026_09.csv')
        second, _ = read_pinned(root / f'{side}_2026_10.csv', f'{side}_2026_10.csv')
        prices[side] = first | second
    records, comparisons, b_timeouts = [], [], []
    for item in paired['comparisons']:
        original = item['paired']
        exit_side = 'bid' if original['side'] == 'BUY' else 'ask'
        updated = minute_exit(original, prices[exit_side], end=END)
        records.append(updated)
        if updated['family'] == 'B_COUNTER_SWEEP' and updated['state'] == 'TIMEOUT_REFERENCE':
            b_timeouts.append(audit_timeout(updated, prices[exit_side]))
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
        comparisons=comparisons, b_timeout_paths=b_timeouts,
        actual_broker_profit=None, out_of_sample=False,
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
