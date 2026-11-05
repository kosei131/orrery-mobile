# SPDX-License-Identifier: GPL-3.0-only
"""Exploratory replay on pinned September and October Bid-labeled OHLC."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from orrery_gold_nested_wave_holdout import replay_window
from orrery_paired_archive_study import SOURCE_PINS, read_side

SOURCE = 'bid_2026_10.csv'
START = int(datetime(2026, 10, 1, tzinfo=timezone.utc).timestamp())
END = int(datetime(2026, 10, 19, 14, tzinfo=timezone.utc).timestamp())


SEPTEMBER = int(datetime(2026, 9, 1, tzinfo=timezone.utc).timestamp())


def read_pinned(source, name):
    minutes, audit = read_side(source)
    if audit['sha256'] != SOURCE_PINS[name]:
        raise ValueError(f'Pinned source mismatch: {name}')
    return minutes, audit


def complete_m5(minutes, start, end):
    bars = []
    for stamp in range(start, end, 300):
        clocks = range(stamp, stamp + 300, 60)
        if any(clock not in minutes for clock in clocks):
            continue
        group = [minutes[clock] for clock in clocks]
        bars.append(dict(open_time=stamp, close_time=stamp + 300,
                         open=group[0]['open'], close=group[-1]['close'],
                         high=max(row['high'] for row in group),
                         low=min(row['low'] for row in group)))
    return bars


def run(source):
    minutes, audit = read_pinned(source, SOURCE)
    bars = complete_m5(minutes, START, END)
    return dict(replay_window(bars, start=START, end=END),
                source_audit=audit, price_basis='third-party BID-labeled OHLC',
                cost_model='flat hypothetical friction; no Ask entry or broker fills',
                out_of_sample=False, independent_source_authentication=False)

def compare_months(september, october):
    sep, sep_audit = read_pinned(september, 'bid_2026_09.csv')
    oct_, oct_audit = read_pinned(october, SOURCE)
    if max(sep) >= START or min(oct_) < START:
        raise ValueError('Monthly source boundary mismatch')
    bars = complete_m5(sep | oct_, SEPTEMBER, END)
    return dict(
        price_basis='third-party BID-labeled OHLC',
        cost_model='flat hypothetical friction; no Ask entry or broker fills',
        source_audits=dict(september=sep_audit, october=oct_audit),
        out_of_sample=False, independent_source_authentication=False,
        pooled=replay_window(bars, start=SEPTEMBER, end=END),
        september=replay_window(bars, start=SEPTEMBER, end=START),
        october_with_september_context=replay_window(bars, start=START, end=END),
    )


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--september', type=Path)
    args = parser.parse_args()
    result = compare_months(args.september, args.source) if args.september else run(args.source)
    payload = json.dumps(result, indent=2, allow_nan=False)
    with args.output.open('x', encoding='utf-8', newline='\n') as output:
        output.write(payload + '\n')
