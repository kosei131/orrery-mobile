# SPDX-License-Identifier: GPL-3.0-only
"""Audit M1 Bid exit ordering for the existing paired Gold candidate set."""
import argparse
from decimal import Decimal
import json
from pathlib import Path

from orrery_gold_nested_wave_october import END, SOURCE, read_pinned
from orrery_gold_nested_wave_paired import run as paired_replay
from orrery_gold_nested_wave_study import summarize


def minute_exit(record, bid, *, end):
    """Keep the Ask entry and bracket fixed, then inspect each completed M1."""
    result = dict(record, reference_r=None, exit_m5_close=None, exit_m1_close=None)
    if any(record[key] is None for key in ('entry_open_reference', 'target_reference')):
        return result
    if record['state'] in ('CENSORED_INVALID_OPEN_RISK', 'CENSORED_NO_TARGET_ROOM_AT_OPEN'):
        return result
    entry, stop, target = (Decimal(record[key]) for key in
                           ('entry_open_reference', 'structural_stop', 'target_reference'))
    start = record['known_at_utc']
    for stamp in range(start, start + 7200, 60):
        if stamp + 60 >= end:
            return dict(result, state='CENSORED_PERIOD_END_M1')
        if stamp not in bid:
            return dict(result, state='CENSORED_M1_GAP')
        row = bid[stamp]
        opening, high, low, close = (Decimal(str(row[key])) for key in
                                     ('open', 'high', 'low', 'close'))
        price = None
        if opening <= stop:
            state, price = 'ADVERSE_OPEN_REFERENCE', opening
        elif opening >= target:
            state, price = 'FAVORABLE_OPEN_CAPPED_REFERENCE', target
        elif low <= stop and high >= target:
            return dict(result, state='AMBIGUOUS_SAME_M1', exit_m1_close=stamp + 60)
        elif low <= stop:
            state, price = 'STOP_REFERENCE', stop
        elif high >= target:
            state, price = 'TARGET_REFERENCE', target
        elif stamp + 60 == start + 7200:
            state, price = 'TIMEOUT_REFERENCE', close
        if price is not None:
            return dict(result, state=state, exit_m1_close=stamp + 60,
                        reference_r=float((price-entry)/(entry-stop)))
    raise AssertionError('M1 exit horizon must terminate')


def run(root):
    paired = paired_replay(root)
    sep, _ = read_pinned(root / 'bid_2026_09.csv', 'bid_2026_09.csv')
    oct_, _ = read_pinned(root / SOURCE, SOURCE)
    bid = sep | oct_
    reports = {}
    for arm in ('immediate', 'delayed', 'delayed_with_room_gate'):
        previous = paired['paired'][arm]['records']
        minute = [minute_exit(record, bid, end=END) for record in previous]
        reports[arm] = dict(
            previous_m5=paired['paired'][arm]['summary'],
            minute=summarize(minute),
            comparisons=[dict(candidate_id=a['candidate_id'], m5_state=a['state'],
                              m5_reference_r=a['reference_r'], m5_close=a['exit_m5_close'],
                              m1_state=b['state'],
                              m1_reference_r=b['reference_r'], m1_close=b['exit_m1_close'])
                         for a, b in zip(previous, minute, strict=True)],
        )
    return dict(status='THIRD_PARTY_M1_EXIT_ORDER_AUDIT',
                source_audits=paired['source_audits'], arms=reports,
                actual_broker_profit=None, execution_allowed=False, adoption_allowed=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive_directory', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    payload = json.dumps(run(args.archive_directory), indent=2, allow_nan=False)
    with args.output.open('x', encoding='utf-8', newline='\n') as output:
        output.write(payload + '\n')
