# SPDX-License-Identifier: GPL-3.0-only
"""Separate retrospective H1 clock comparison; no trading permission."""
import argparse
from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from statistics import mean

from orrery_gold_ab_archive_comparison import aggregate_complete
from orrery_gold_channel_breakout import summarize
from orrery_gold_clock_audit import scheduled_open
from orrery_gold_hourly_trend import LOOKBACK, HORIZON
from orrery_gold_nested_wave_october import complete_m5
from orrery_gold_pullback_study import START, END, load_archive, evaluate_pullback
from orrery_gold_session_breakout import Q4_START, load_q4


def chains(bars, *, session):
    """Only complete open H1 bars; missing open minutes break context."""
    window = []
    previous = None
    for row in bars:
        at = row['close_time']
        begin = at - 3600
        if previous is not None and begin < previous:
            raise ValueError('Unordered or overlapping H1 bars')
        if not all(scheduled_open(t) for t in range(begin, at, 60)):
            window = []
            previous = at
            continue
        if previous is not None and begin != previous:
            if not session or any(scheduled_open(t) for t in range(previous, begin, 60)):
                window = []
        window.append(row)
        window = window[-(LOOKBACK+1):]
        previous = at
        if len(window) == LOOKBACK+1:
            yield window[:]


def signals(bars, end, *, session):
    for window in chains(bars, session=session):
        current, previous = window[-1], window[:-1]
        at = current['close_time']
        if at >= end:
            break
        average = mean(row['close'] for row in previous)
        if previous[-1]['close'] <= average < current['close']:
            side = 'BUY'
        elif previous[-1]['close'] >= average > current['close']:
            side = 'SELL'
        else:
            continue
        ranges = [max(b['high']-b['low'], abs(b['high']-a['close']),
                      abs(b['low']-a['close'])) for a,b in zip(previous[-15:], previous[-14:])]
        distance = 2*mean(ranges)
        if distance > 0:
            yield dict(at_utc=at, side=side, stop_distance=distance)


def open_horizon(at, end):
    """Known clock boundary only, never select a horizon using observed prices."""
    for minute in range(HORIZON):
        stamp = at + minute*60
        if stamp >= end or not scheduled_open(stamp):
            return minute
    return HORIZON


def replay(found, bid, ask, end):
    rows = []
    occupied_until = 0
    skipped = Counter()
    for signal in found:
        at = signal['at_utc']
        if at < occupied_until:
            skipped['OCCUPIED_OR_UNKNOWN_OUTCOME'] += 1
            continue
        horizon = open_horizon(at, end)
        if horizon == 0:
            skipped['CLOSED_OR_PERIOD_END'] += 1
            continue
        if at not in bid or at not in ask:
            rows.append(dict(signal, status='UNKNOWN_ENTRY_HISTORY'))
            continue
        buy = signal['side'] == 'BUY'
        sign = 1 if buy else -1
        entry = (ask if buy else bid)[at]['open']
        stop = (bid if buy else ask)[at]['open'] - sign*signal['stop_distance']
        target = entry + 2*(entry-stop)
        result = evaluate_pullback(dict(first_poi_touch_close=at, side=signal['side']),
            bid, ask, structural_stop=stop, structural_known_at=at,
            target_price=target, horizon=horizon)
        if result['status'] == 'RESOLVED_REFERENCE':
            if result['exit_reason'] == 'TIMEOUT_CLOSE' and horizon < HORIZON:
                result['exit_reason'] = 'PERIOD_END_CLOSE' if at+horizon*60 == end else 'SESSION_CLOSE'
            occupied_until = result['exit_at'] + (0 if result['exit_reason'] in
                ('TIMEOUT_CLOSE', 'SESSION_CLOSE', 'PERIOD_END_CLOSE') else 60)
        elif result['status'] in ('CENSORED_AT_SIDE_GAP', 'AMBIGUOUS_SAME_MINUTE'):
            occupied_until = at+horizon*60
        rows.append(dict(signal, horizon_minutes=horizon, **result))
    return rows, dict(skipped)


def measure(bid, ask, m5, start, end):
    h1 = aggregate_complete(m5, 3600)
    arms = {}
    records = {}
    for name, session in (('STRICT_CLOCK', False), ('SESSION_HYPOTHESIS', True)):
        found = list(signals(h1, end, session=session))
        rows, skips = replay(found, bid, ask, end)
        months = sorted({datetime.fromtimestamp(t, timezone.utc).strftime('%Y-%m')
                         for t in range(start, end, 86400)})
        arms[name] = dict(summarize(rows), raw_signals=len(found), skipped=skips,
            resolved_per_calendar_week=sum(r['status']=='RESOLVED_REFERENCE' for r in rows)*604800/(end-start),
            by_utc_month={month: summarize([r for r in rows if
                datetime.fromtimestamp(r['at_utc'], timezone.utc).strftime('%Y-%m') == month]) for month in months})
        records[name] = rows
    return dict(start_utc=datetime.fromtimestamp(start, timezone.utc).isoformat(),
                end_utc_exclusive=datetime.fromtimestamp(end, timezone.utc).isoformat(),
                complete_h1=len(h1), arms=arms, records=records)


def run(root, prior_root):
    bid, ask, m5, _, _, audit = load_archive(root)
    recent = measure(bid, ask, m5, START, END)
    bid, ask, _, prior_audit = load_q4(prior_root)
    m5 = complete_m5({t:bid[t] for t in bid.keys() & ask.keys()}, Q4_START, START)
    old = measure(bid, ask, m5, Q4_START, START)
    return dict(study='gold_session_hourly_v1', historical_2026=recent, separate_2025_q4=old,
        source_audit_2026=audit, source_audit_q4=prior_audit,
        code_sha256=sha256(Path(__file__).read_bytes()).hexdigest(),
        historical_session_rule_authenticated=False, historical_holiday_exceptions_authenticated=False,
        out_of_sample=False, prices_interpolated=False, account_return_pct=None,
        account_max_drawdown_pct=None, execution_allowed=False, adoption_allowed=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive_2026', type=Path)
    parser.add_argument('archive_2025_q4', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    result = run(args.archive_2026, args.archive_2025_q4)
    with args.output.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write('\n')
