# SPDX-License-Identifier: GPL-3.0-only
"""Exploratory replay on the pinned October archive's Bid-labeled OHLC."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from orrery_gold_nested_wave_holdout import replay_window
from orrery_paired_archive_study import SOURCE_PINS, read_side

SOURCE = 'bid_2026_10.csv'
START = int(datetime(2026, 10, 1, tzinfo=timezone.utc).timestamp())
END = int(datetime(2026, 10, 19, 14, tzinfo=timezone.utc).timestamp())


def run(source):
    minutes, audit = read_side(source)
    if audit['sha256'] != SOURCE_PINS[SOURCE]:
        raise ValueError('Pinned October source mismatch')
    bars = []
    for stamp in range(START, END, 300):
        clocks = range(stamp, stamp + 300, 60)
        if any(clock not in minutes for clock in clocks):
            continue
        group = [minutes[clock] for clock in clocks]
        bars.append(dict(open_time=stamp, close_time=stamp + 300,
                         open=group[0]['open'], close=group[-1]['close'],
                         high=max(row['high'] for row in group),
                         low=min(row['low'] for row in group)))
    return dict(replay_window(bars, start=START, end=END),
                source_audit=audit, price_basis='third-party BID-labeled OHLC',
                cost_model='flat hypothetical friction; no Ask entry or broker fills',
                out_of_sample=False, independent_source_authentication=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    payload = json.dumps(run(args.source), indent=2, allow_nan=False)
    with args.output.open('x', encoding='utf-8', newline='\n') as output:
        output.write(payload + '\n')
