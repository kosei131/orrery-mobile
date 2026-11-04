# SPDX-License-Identifier: GPL-3.0-only
"""December Gold nested-wave research replay on caller-supplied OANDA OHLC."""
import argparse
from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path

from orrery_gold_mtf_ab_price_references import evaluate
from orrery_gold_nested_wave_study import candidates, resume_room_gate, summarize
from orrery_real_bars_lsr_bridge import load

START = int(datetime(2026, 12, 1, tzinfo=timezone.utc).timestamp())
END = int(datetime(2027, 1, 1, tzinfo=timezone.utc).timestamp())
CONTEXT = 3 * 3600


def complete_m15(m5):
    by_open = {bar['open_time']: bar for bar in m5}
    result = []
    for start in by_open:
        if start % 900:
            continue
        group = [by_open.get(start + offset) for offset in (0, 300, 600)]
        if any(bar is None for bar in group):
            continue
        first, _, last = group
        result.append(dict(open_time=start, close_time=start + 900,
                           open=first['open'], close=last['close'],
                           high=max(bar['high'] for bar in group),
                           low=min(bar['low'] for bar in group)))
    return result


def replay(m5):
    context = [bar for bar in m5 if START - CONTEXT <= bar['open_time']
               and bar['close_time'] < END]
    if not any(bar['open_time'] >= START for bar in context):
        raise ValueError('No confirmed M5 observations inside frozen period')
    m15 = complete_m15(context)
    closes = {bar['close_time']: bar['close'] for bar in m15}
    pairs = [pair for pair in candidates(m15) if pair[0]['known_at_utc'] >= START]
    exits = [{k: v for k, v in bar.items() if k != 'open_time'}
             for bar in context if bar['open_time'] >= START]
    immediate, delayed, approved = [], [], []
    wait_states = Counter()
    screens = {}
    for early, state, late in pairs:
        immediate.append(early)
        if state == 'WAIT_DATA_GAP' and early['known_at_utc'] + 4 * 900 >= END:
            # Preserve an actual gap before the boundary as a data gap.
            for offset in range(900, 3601, 900):
                next_close = early['known_at_utc'] + offset
                if next_close not in closes:
                    if next_close >= END:
                        state = 'WAIT_PERIOD_END'
                    break
        wait_states[state] += 1
        if late is None:
            continue
        delayed.append(late)
        decision = resume_room_gate(
            signal_close=closes[late['known_at_utc']], stop=late['structural_stop'],
            ceiling=early['indicative_close'] + early['known_room_price'])
        screens[early['candidate_id']] = decision
        if decision['decision'] == 'PASS_RESEARCH_SCREEN':
            approved.append(late)

    def assess(group):
        rows = evaluate(exits, group)['records']
        return dict(summary=summarize(rows), records=rows)

    return dict(source_label='OANDA:XAUUSD (caller declaration)',
                independent_source_authentication=False, start_utc_epoch=START, end_utc_epoch=END,
                observed_m5=len(exits), observed_m15=sum(b['open_time'] >= START for b in m15),
                first_observed_m5_open=exits[0]['close_time']-300,
                last_observed_m5_close=exits[-1]['close_time'],
                wait_states=dict(wait_states), room_decisions=screens,
                immediate=assess(immediate), delayed=assess(delayed),
                delayed_with_room_gate=assess(approved),
                actual_win_rate_pct=None, account_return_pct=None, net_expectancy_r=None,
                execution_allowed=False, adoption_allowed=False)


def run(path, expected_sha256):
    if datetime.now(timezone.utc).timestamp() < END:
        raise ValueError('Frozen evaluation period has not ended')
    if path.stat().st_size > 16 * 1024 * 1024:
        raise ValueError('M5 input byte limit exceeded')
    if sha256(path.read_bytes()).hexdigest() != expected_sha256:
        raise ValueError('M5 source hash mismatch')
    bars = load(path, 'M5')['bars']
    if sha256(path.read_bytes()).hexdigest() != expected_sha256:
        raise ValueError('M5 source changed during read')
    result = replay(bars)
    return dict(result, source_sha256=expected_sha256)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('m5_csv', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--sha256', required=True)
    args = parser.parse_args()
    payload = json.dumps(run(args.m5_csv, args.sha256), indent=2, allow_nan=False)
    with args.output.open('x', encoding='utf-8', newline='\n') as output:
        output.write(payload + '\n')
