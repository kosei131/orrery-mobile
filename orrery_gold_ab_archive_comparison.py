# SPDX-License-Identifier: GPL-3.0-only
"""Recheck the unchanged Gold A/B scanner on the pinned Bid-labeled archive."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from orrery_gold_entry_family_comparison import describe
from orrery_gold_mtf_ab_price_references import VALID_FAMILIES, evaluate
from orrery_gold_mtf_ab_replay import scan_frames
from orrery_gold_nested_wave_october import END, SEPTEMBER, SOURCE, START, complete_m5, read_pinned


def aggregate_complete(m5, seconds):
    by_open = {bar['open_time']: bar for bar in m5}
    result = []
    for start in by_open:
        if start % seconds:
            continue
        group = [by_open.get(clock) for clock in range(start, start + seconds, 300)]
        if any(row is None for row in group):
            continue
        result.append(dict(close_time=start+seconds, open=group[0]['open'],
                           high=max(row['high'] for row in group),
                           low=min(row['low'] for row in group), close=group[-1]['close']))
    return result


def run(root):
    sep, sep_audit = read_pinned(root / 'bid_2026_09.csv', 'bid_2026_09.csv')
    oct_, oct_audit = read_pinned(root / SOURCE, SOURCE)
    if max(sep) >= min(oct_):
        raise ValueError('Archive sources overlap')
    m5 = complete_m5(sep | oct_, SEPTEMBER, END)
    m5 = [row for row in m5 if row['close_time'] < END]
    frames = dict(M5=aggregate_complete(m5, 300),
                  M15=aggregate_complete(m5, 900),
                  H4=aggregate_complete(m5, 14400))
    scan = scan_frames(frames)
    rows = evaluate(frames['M5'], scan['candidates'])['records']
    return dict(
        status='EXPLORATORY_GOLD_AB_ON_PINNED_ALTERNATE_ARCHIVE',
        start_utc=datetime.fromtimestamp(SEPTEMBER, timezone.utc).isoformat(),
        end_utc_exclusive=datetime.fromtimestamp(END, timezone.utc).isoformat(),
        source_audits=[sep_audit, oct_audit],
        price_basis='third-party Bid-labeled OHLC; hypothetical flat friction',
        scan=scan,
        families={name: describe([row for row in rows if row['family'] == name])
                  for name in VALID_FAMILIES},
        by_signal_month={
            month: {name: describe([row for row in rows
                                    if row['family'] == name and lo <= row['known_at_utc'] < hi])
                    for name in VALID_FAMILIES}
            for month, lo, hi in (('2026-09', SEPTEMBER, START), ('2026-10', START, END))
        },
        records=rows, out_of_sample=False, actual_broker_profit=None,
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
