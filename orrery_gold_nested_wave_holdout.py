# SPDX-License-Identifier: GPL-3.0-only
"""December Gold nested-wave research replay on caller-supplied OANDA OHLC."""
import argparse
from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
import json
from math import fsum, isclose
from pathlib import Path

from orrery_gold_mtf_ab_price_references import evaluate
from orrery_gold_nested_wave_study import COSTS, candidates, resume_room_gate, summarize
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


def summarize_gate_rejections(records, screens):
    """Measure what the room gate excludes using the unchanged delayed outcomes."""
    rejected = [row for row in records
                if screens[row['candidate_id']]['decision'] != 'PASS_RESEARCH_SCREEN']
    resolved = [row for row in rejected if row['reference_r'] is not None]
    scenarios = []
    for cost in COSTS:
        values = []
        for row in resolved:
            width = abs(float(row['entry_open_reference']) - float(row['structural_stop']))
            adjusted = row['reference_r'] - cost / width
            values.append(0.0 if isclose(adjusted, 0.0, abs_tol=1e-12) else adjusted)
        losses = [value for value in values if value < 0]
        gains = [value for value in values if value > 0]
        scenarios.append(dict(assumed_round_trip_cost_price=cost,
                              avoided_loss_count=len(losses), missed_profit_count=len(gains),
                              flat_count=len(values)-len(losses)-len(gains),
                              avoided_loss_r=-fsum(losses) if losses else 0.0,
                              missed_profit_r=fsum(gains)))
    return dict(rejected_candidate_ids=[row['candidate_id'] for row in rejected],
                resolved_count=len(resolved),
                unresolved_candidate_ids=[row['candidate_id'] for row in rejected
                                          if row['reference_r'] is None],
                scenarios=scenarios)



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

    delayed_results = assess(delayed)
    return dict(source_label='OANDA:XAUUSD (caller declaration)',
                independent_source_authentication=False, start_utc_epoch=START, end_utc_epoch=END,
                observed_m5=len(exits), observed_m15=sum(b['open_time'] >= START for b in m15),
                first_observed_m5_open=exits[0]['close_time']-300,
                last_observed_m5_close=exits[-1]['close_time'],
                wait_states=dict(wait_states), room_decisions=screens,
                immediate=assess(immediate), delayed=delayed_results,
                room_gate_rejections=summarize_gate_rejections(delayed_results['records'], screens),
                delayed_with_room_gate=assess(approved),
                actual_win_rate_pct=None, account_return_pct=None, net_expectancy_r=None,
                execution_allowed=False, adoption_allowed=False)


def classify_session_slots(slots, receipt):
    """Classify against explicitly supplied intervals, leaving other slots unknown."""
    schedule = receipt.get('session_intervals', [])
    reference = receipt.get('session_reference')
    if not isinstance(schedule, list) or len(schedule) > 256:
        raise ValueError('Bounded session intervals required')
    if schedule and (not isinstance(reference, str) or not reference.strip() or len(reference) > 512):
        raise ValueError('Session intervals require a provenance reference')

    declared = {}
    previous_end = START
    for interval in schedule:
        if not isinstance(interval, dict):
            raise ValueError('Invalid session interval')
        start = interval.get('start_utc_epoch')
        end = interval.get('end_utc_epoch')
        state = interval.get('state')
        if (type(start) is not int or type(end) is not int or start % 300 or end % 300
                or not previous_end <= start < end <= END or state not in ('OPEN', 'CLOSED')):
            raise ValueError('Expected sorted non-overlapping UTC M5 session intervals')
        declared.update(dict.fromkeys(range(start, end, 300), state))
        previous_end = end

    counts = dict(unobserved_declared_open=0, unobserved_declared_closed=0,
                  unobserved_unknown_session=0, observed_declared_closed=0)
    observed = set(slots)
    for stamp in range(START, END-300, 300):
        state = declared.get(stamp)
        if stamp in observed:
            counts['observed_declared_closed'] += state == 'CLOSED'
        elif state == 'OPEN':
            counts['unobserved_declared_open'] += 1
        elif state == 'CLOSED':
            counts['unobserved_declared_closed'] += 1
        else:
            counts['unobserved_unknown_session'] += 1
    return dict(counts, session_reference=reference if schedule else None)



def audit_source(bars, receipt, expected_sha256):
    """Check declared provenance and inventory the UTC grid and any declared sessions."""
    required = dict(instrument='OANDA:XAUUSD', timeframe='M5', price_basis='MID',
                    timestamp_convention='UTC_BAR_OPEN', confirmed_only=True,
                    csv_sha256=expected_sha256)
    if (not isinstance(receipt, dict) or receipt.get('confirmed_only') is not True
            or any(receipt.get(k) != v for k, v in required.items())):
        raise ValueError('Source receipt must bind confirmed OANDA XAUUSD M5 MID to CSV hash')
    acquisition = receipt.get('acquisition_reference')
    if not isinstance(acquisition, str) or not acquisition.strip() or len(acquisition) > 512:
        raise ValueError('Bounded acquisition reference required')

    slots = [bar['open_time'] for bar in bars
             if START <= bar['open_time'] and bar['close_time'] < END]
    gaps = []
    cursor = START
    for stamp in slots:
        if stamp > cursor:
            gaps.append(dict(start_open_utc_epoch=cursor, end_open_exclusive_utc_epoch=stamp,
                             unobserved_slots=(stamp-cursor)//300))
        cursor = stamp + 300
    if cursor < END - 300:
        gaps.append(dict(start_open_utc_epoch=cursor, end_open_exclusive_utc_epoch=END-300,
                         unobserved_slots=(END-300-cursor)//300))
    return dict(declared_source=required, acquisition_reference=acquisition,
                independent_source_authentication=False, session_calendar_verified=False,
                observed_slots=len(slots), unobserved_slots=sum(g['unobserved_slots'] for g in gaps),
                unobserved_intervals=gaps, session_classification=classify_session_slots(slots, receipt))



def run(path, expected_sha256, receipt_path=None):
    if datetime.now(timezone.utc).timestamp() < END:
        raise ValueError('Frozen evaluation period has not ended')
    if path.stat().st_size > 16 * 1024 * 1024:
        raise ValueError('M5 input byte limit exceeded')
    if sha256(path.read_bytes()).hexdigest() != expected_sha256:
        raise ValueError('M5 source hash mismatch')
    bars = load(path, 'M5')['bars']
    if sha256(path.read_bytes()).hexdigest() != expected_sha256:
        raise ValueError('M5 source changed during read')
    if receipt_path is None or receipt_path.stat().st_size > 32 * 1024:
        raise ValueError('Bounded source receipt required')
    receipt = json.loads(receipt_path.read_text(encoding='utf-8'))
    source_audit = audit_source(bars, receipt, expected_sha256)
    result = replay(bars)
    return dict(result, source_sha256=expected_sha256, source_audit=source_audit)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('m5_csv', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--sha256', required=True)
    parser.add_argument('--source-receipt', type=Path, required=True)
    args = parser.parse_args()
    payload = json.dumps(run(args.m5_csv, args.sha256, args.source_receipt), indent=2, allow_nan=False)
    with args.output.open('x', encoding='utf-8', newline='\n') as output:
        output.write(payload + '\n')
