# SPDX-License-Identifier: GPL-3.0-only
"""Fixed hourly Gold trend cross with optional completed H4 direction."""
import argparse
from bisect import bisect_right
from collections import Counter
import json
from pathlib import Path
from statistics import mean

from orrery_gold_ab_archive_comparison import aggregate_complete
from orrery_gold_channel_breakout import summarize
from orrery_gold_nested_wave_october import complete_m5
from orrery_gold_pullback_study import END, START, evaluate_pullback, load_archive
from orrery_gold_session_breakout import Q4_START, load_q4

LOOKBACK = 20
H4_LOOKBACK = 10
HORIZON = 480


def h4_directions(bars):
    for i in range(H4_LOOKBACK, len(bars)):
        window = bars[i-H4_LOOKBACK:i+1]
        at = window[-1]['close_time']
        if any(row['close_time'] != at-(H4_LOOKBACK-j)*14400 for j,row in enumerate(window)):
            continue
        prices = [row['close'] for row in window]
        current, prior = mean(prices[1:]), mean(prices[:-1])
        if prices[-1] > current > prior:
            yield at, 'BUY'
        elif prices[-1] < current < prior:
            yield at, 'SELL'


def signals(h1, h4, end):
    directions = dict(h4_directions(h4))
    clocks = sorted(directions)
    for i in range(LOOKBACK, len(h1)):
        current = h1[i]
        at = current['close_time']
        if at >= end:
            break
        previous = h1[i-LOOKBACK:i]
        if any(row['close_time'] != at-(LOOKBACK-j)*3600 for j,row in enumerate(previous)):
            continue
        average = mean(row['close'] for row in previous)
        if previous[-1]['close'] <= average < current['close']:
            side = 'BUY'
        elif previous[-1]['close'] >= average > current['close']:
            side = 'SELL'
        else:
            continue
        ranges = [max(b['high']-b['low'], abs(b['high']-a['close']),
                      abs(b['low']-a['close'])) for a,b in zip(previous[-15:],previous[-14:])]
        distance = 2*mean(ranges)
        if distance <= 0:
            continue
        index = bisect_right(clocks, at)-1
        direction = directions[clocks[index]] if index >= 0 and at-clocks[index] < 14400 else None
        yield dict(at_utc=at, side=side, stop_distance=distance, h4_direction=direction)


def longest_chain(bars, seconds):
    longest = current = 0
    previous = None
    for row in bars:
        at = row['close_time']
        current = current+1 if previous is not None and at-previous == seconds else 1
        longest = max(longest, current)
        previous = at
    return longest


def measure(bid, ask, m5, start, end):
    h1, h4 = (aggregate_complete(m5, seconds) for seconds in (3600, 14400))
    found = list(signals(h1, h4, end))
    arms = {}
    for name in ('H1', 'H1_H4'):
        eligible = 0
        rows = []
        for signal in found:
            at = signal['at_utc']
            if at < eligible or (name == 'H1_H4' and signal['h4_direction'] != signal['side']):
                continue
            if at not in bid or at not in ask:
                rows.append(dict(signal, status='UNKNOWN_ENTRY_HISTORY'))
                continue
            buy = signal['side'] == 'BUY'
            sign = 1 if buy else -1
            entry = (ask if buy else bid)[at]['open']
            stop = (bid if buy else ask)[at]['open']-sign*signal['stop_distance']
            target = entry+2*(entry-stop)
            result = evaluate_pullback(
                dict(first_poi_touch_close=at, side=signal['side']), bid, ask,
                structural_stop=stop, structural_known_at=at, target_price=target, horizon=HORIZON,
            )
            rows.append(dict(signal, **result))
            if result['status'] == 'RESOLVED_REFERENCE':
                eligible = result['exit_at']+(0 if result['exit_reason']=='TIMEOUT_CLOSE' else 60)
            elif result['status'] in ('CENSORED_AT_SIDE_GAP','AMBIGUOUS_SAME_MINUTE'):
                eligible = at+HORIZON*60
        arms[name] = dict(summarize(rows), resolved_per_week=sum(
            row['status']=='RESOLVED_REFERENCE' for row in rows)*604800/(end-start))
    return dict(complete_h1=len(h1), complete_h4=len(h4), raw_signals=len(found),
                longest_h1_chain=longest_chain(h1, 3600),
                longest_h4_chain=longest_chain(h4, 14400),
                h4_unavailable=sum(row['h4_direction'] is None for row in found),
                raw_h4_alignment=dict(Counter('MISSING' if row['h4_direction'] is None else
                    'MATCH' if row['h4_direction']==row['side'] else 'OPPOSITE' for row in found)),
                arms=arms)


def run(root, prior_root):
    bid, ask, m5, _, _, _ = load_archive(root)
    recent = measure(bid, ask, m5, START, END)
    bid, ask, _, _ = load_q4(prior_root)
    paired = {t: bid[t] for t in bid.keys() & ask.keys()}
    old = measure(bid, ask, complete_m5(paired, Q4_START, START), Q4_START, START)
    return dict(study='gold_hourly_trend', horizon_minutes=HORIZON,
                historical_2026=recent, separate_2025_q4=old,
                out_of_sample=False, account_return_pct=None, execution_allowed=False, adoption_allowed=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive_2026', type=Path)
    parser.add_argument('archive_2025_q4', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    with args.output.open('x', encoding='utf-8', newline='\n') as output:
        json.dump(run(args.archive_2026, args.archive_2025_q4), output, indent=2, allow_nan=False)
        output.write('\n')
