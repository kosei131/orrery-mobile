# SPDX-License-Identifier: GPL-3.0-only
"""Compare fixed Gold range breakouts with and without recent range compression."""
import argparse
import json
from pathlib import Path
from statistics import mean, median

from orrery_gold_pullback_study import END, START, describe, load_archive, replay
from orrery_gold_session_breakout import Q4_START, load_q4
from orrery_paired_archive_study import REVISION, iso

RECENT = 4
BASELINE = 20
MAX_RATIO = 0.70
HORIZONS = (60, 240)
TARGET_R = 1.5
M15 = 900


def signals(bars, ask, end):
    width = RECENT + BASELINE
    for i in range(width, len(bars)):
        current = bars[i]
        at = current['close_time']
        if at >= end:
            break
        prior = bars[i-width:i]
        if prior[0]['close_time'] != at-width*M15:
            continue
        recent = prior[-RECENT:]
        high = max(bar['high'] for bar in recent)
        low = min(bar['low'] for bar in recent)
        buy = current['close'] > high
        if not buy and current['close'] >= low:
            continue
        reference = median(bar['high']-bar['low'] for bar in prior[:-RECENT])
        if reference <= 0:
            continue
        ratio = mean(bar['high']-bar['low'] for bar in recent)/reference
        stop = low if buy else max(
            ask[t]['high'] for t in range(at-(RECENT+1)*M15, at-M15, 60)
        )
        yield dict(at_utc=at, setup_at_utc=at, side='BUY' if buy else 'SELL',
                   stop=stop, compression_ratio=ratio)


def measure(bid, ask, bars, start, end, audit):
    raw = list(signals(bars, ask, end))
    compressed = [row for row in raw if row['compression_ratio'] <= MAX_RATIO]
    arms = {}
    for scope, found in (('all', raw), ('compressed', compressed)):
        for horizon in HORIZONS:
            rows, skips = replay(found, bid, ask, TARGET_R, horizon=horizon)
            arms[f'{scope}_{horizon}'] = dict(describe(rows, start, end),
                                            raw_signals=len(found), occupied_skips=skips)
    return dict(start_utc=iso(start), end_utc_exclusive=iso(end), audit=audit, arms=arms)


def run(root_2026, root_q4):
    bid, ask, _, m15, _, audit = load_archive(root_2026)
    old_bid, old_ask, old_m15, prior_audit = load_q4(root_q4)
    return dict(source_revision=REVISION, max_compression_ratio=MAX_RATIO,
                horizons_minutes=HORIZONS, target_r=TARGET_R,
                historical_2026=measure(bid, ask, m15, START, END,
                                        dict(paired_minutes=audit['paired_minutes'])),
                separate_2025_q4=measure(old_bid, old_ask, old_m15, Q4_START, START, prior_audit),
                out_of_sample=False, account_return_pct=None, execution_allowed=False,
                adoption_allowed=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive_2026', type=Path)
    parser.add_argument('archive_2025_q4', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    payload = json.dumps(run(args.archive_2026, args.archive_2025_q4), indent=2, allow_nan=False)
    with args.output.open('x', encoding='utf-8', newline='\n') as output:
        output.write(payload + '\n')
