# SPDX-License-Identifier: GPL-3.0-only
"""Exploratory standalone Gold channel breakout on pinned paired archive bars."""
import argparse
from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path

from orrery_gold_ab_archive_comparison import aggregate_complete
from orrery_gold_nested_wave_october import END, SEPTEMBER, complete_m5, read_pinned
from orrery_paired_archive_study import evaluate_plan

LOOKBACK = 20
RANGE_PERIOD = 14
HOLD_MINUTES = 120
ADDITIONAL_COSTS = (0, 0.30, 0.60)


def signals(bars):
    next_allowed = 0
    for index in range(LOOKBACK, len(bars)):
        previous = bars[index-LOOKBACK:index]
        current = bars[index]
        at = current['close_time']
        if any(at-row['close_time'] != (LOOKBACK-i)*900 for i, row in enumerate(previous)):
            continue
        if current['close'] > max(row['high'] for row in previous):
            side = 'BUY'
        elif current['close'] < min(row['low'] for row in previous):
            side = 'SELL'
        else:
            continue
        window = previous[-RANGE_PERIOD-1:]
        ranges = [max(b['high']-b['low'], abs(b['high']-a['close']), abs(b['low']-a['close']))
                  for a, b in zip(window, window[1:])]
        distance = sum(ranges)/RANGE_PERIOD
        if distance <= 0:
            continue
        selected = at >= next_allowed
        if selected:
            next_allowed = at + HOLD_MINUTES*60
        yield dict(at_utc=at, side=side, stop_range_price=distance, selected=selected)


def evaluate_signal(signal, bid, ask):
    stamp = signal['at_utc']
    side = signal['side']
    if stamp not in bid or stamp not in ask:
        return dict(signal, status='UNKNOWN_ENTRY_HISTORY')
    if bid[stamp]['open'] > ask[stamp]['open']:
        return dict(signal, status='CROSSED_OPEN_QUOTE')
    distance = signal['stop_range_price']
    stop = bid[stamp]['open']-distance if side == 'BUY' else ask[stamp]['open']+distance
    result = evaluate_plan(dict(first_poi_touch_close=stamp, side=side), bid, ask,
                           structural_stop=stop, structural_known_at=stamp,
                           horizon=HOLD_MINUTES)
    return dict(signal, **result)


def summarize(rows):
    resolved = [row for row in rows if row['status'] == 'RESOLVED_REFERENCE']
    scenarios = []
    for friction in ADDITIONAL_COSTS:
        values = [row['r']-friction/row['initial_risk_price'] for row in resolved]
        wins = [value for value in values if value > 0]
        losses = [value for value in values if value < 0]
        equity = peak = drawdown = 0
        for value in values:
            equity += value
            peak = max(peak, equity)
            drawdown = max(drawdown, peak-equity)
        scenarios.append(dict(additional_cost_price=friction,
                              mean_resolved_r=sum(values)/len(values) if values else None,
                              positive_rate_pct=100*len(wins)/len(values) if values else None,
                              pf=-sum(wins)/sum(losses) if losses else None,
                              resolved_sequence_drawdown_r=drawdown if values else None))
    return dict(candidates=len(rows), resolved=len(resolved),
                statuses=dict(Counter(row['status'] for row in rows)),
                exit_reasons=dict(Counter(row['exit_reason'] for row in resolved)),
                scenarios=scenarios)


def run(root):
    inputs, audits = {}, {}
    for side in ('bid', 'ask'):
        inputs[side] = {}
        for month in ('09', '10'):
            name = f'{side}_2026_{month}.csv'
            rows, audits[name] = read_pinned(root / name, name)
            if inputs[side].keys() & rows.keys():
                raise ValueError('Monthly archive overlap')
            inputs[side].update({stamp: row for stamp, row in rows.items() if SEPTEMBER <= stamp < END})
    bid, ask = inputs['bid'], inputs['ask']
    bars = aggregate_complete(complete_m5(bid, SEPTEMBER, END), 900)
    found = list(signals([bar for bar in bars if bar['close_time'] < END]))
    records = [evaluate_signal(signal, bid, ask) for signal in found if signal['selected']]
    return dict(
        status='EXPLORATORY_XAUUSD_STANDALONE_CHANNEL_BREAKOUT',
        rules=dict(timeframe='M15', channel_lookback=LOOKBACK, prior_true_range_average=RANGE_PERIOD,
                   stop_range_multiplier=1, target_r=1.5, max_hold_minutes=HOLD_MINUTES,
                   minimum_signal_separation_minutes=HOLD_MINUTES),
        source_audits=audits, complete_m15=len(bars), raw_signals=len(found),
        cooldown_skips=sum(not row['selected'] for row in found),
        overall=summarize(records),
        by_utc_month={month: summarize([row for row in records if
                         datetime.fromtimestamp(row['at_utc'], timezone.utc).strftime('%Y-%m') == month])
                      for month in ('2026-09', '2026-10')},
        by_side={side: summarize([row for row in records if row['side'] == side])
                 for side in ('BUY', 'SELL')},
        records=records, out_of_sample=False, actual_broker_profit=None,
        account_return_pct=None, execution_allowed=False, adoption_allowed=False,
        code_sha256=sha256(Path(__file__).read_bytes()).hexdigest(),
    )


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive_directory', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    payload = json.dumps(run(args.archive_directory), indent=2, allow_nan=False)
    with args.output.open('x', encoding='utf-8', newline='\n') as output:
        output.write(payload + '\n')
