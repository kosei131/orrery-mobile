# SPDX-License-Identifier: GPL-3.0-only
"""Replay first session opening-range breach, continuation versus failed breakout."""
import argparse
from datetime import date, datetime, time, timedelta, timezone
import json
from pathlib import Path
from zoneinfo import ZoneInfo

from orrery_gold_ab_archive_comparison import aggregate_complete
from orrery_gold_nested_wave_october import complete_m5
from orrery_gold_pullback_study import END, START, describe, load_archive, replay, suspect_flat_minutes
from orrery_paired_archive_study import REVISION, iso, read_side

Q4_START = int(datetime(2025, 10, 1, tzinfo=timezone.utc).timestamp())
PINS = Path(__file__).with_name('research_evidence') / 'local-history-20261101' / 'gold_session_q4_pins.json'
SESSIONS = {'LONDON': ('Europe/London', time(8)), 'NEW_YORK': ('America/New_York', time(8, 30))}
TARGET_R = 1.5


def session_signals(m15, bid, ask, start, end):
    bars = {row['close_time']: row for row in m15}
    day = datetime.fromtimestamp(start, timezone.utc).date()
    last = datetime.fromtimestamp(end-1, timezone.utc).date()
    zones = {label: ZoneInfo(zone) for label, (zone, _) in SESSIONS.items()}
    while day <= last:
        for label, (_, anchor) in SESSIONS.items():
            opened = int(datetime.combine(day, anchor, zones[label]).timestamp())
            first, second = bars.get(opened+900), bars.get(opened+1800)
            if first is None or second is None:
                continue
            high = max(first['high'], second['high'])
            low = min(first['low'], second['low'])
            for at in range(opened+2700, opened+9001, 900):
                bar = bars.get(at)
                if at >= end or bar is None:
                    break
                upper, lower = bar['high'] > high, bar['low'] < low
                if not upper and not lower:
                    continue
                if upper and lower or bar['close'] in (high, low):
                    break
                continues = bar['close'] > high if upper else bar['close'] < low
                buy = upper == continues
                stop = bar['low'] if buy else max(ask[t]['high'] for t in range(at-900, at, 60))
                yield dict(at_utc=at, side='BUY' if buy else 'SELL', stop=stop,
                           setup_at_utc=at, session=label,
                           pattern='CONTINUATION' if continues else 'RECLAIM')
                break
        day += timedelta(days=1)


def load_q4(root):
    pins = json.loads(PINS.read_text(encoding='utf-8'))
    inputs = {}
    for side in ('bid', 'ask'):
        rows = {}
        for month in (10, 11, 12):
            name = f'{side}_2025_{month}.csv'
            new, audit = read_side(root/name)
            if audit['sha256'] != pins[name] or rows.keys() & new.keys():
                raise ValueError(f'Archive hash mismatch or overlap: {name}')
            if any(datetime.fromtimestamp(t, timezone.utc).date().replace(day=1) != date(2025,month,1)
                   for t in new):
                raise ValueError(f'Archive month mismatch: {name}')
            rows.update(new)
        inputs[side] = rows
    bid, ask = inputs['bid'], inputs['ask']
    shared = bid.keys() & ask.keys()
    if any(ask[t][k] < bid[t][k] for t in shared for k in ('open','high','low','close')):
        raise ValueError('Crossed quote history')
    initial = len(shared)
    for t in set(suspect_flat_minutes(bid)) | set(suspect_flat_minutes(ask)):
        bid.pop(t, None)
        ask.pop(t, None)
    shared = bid.keys() & ask.keys()
    m15 = aggregate_complete(complete_m5({t: bid[t] for t in shared}, Q4_START, START), 900)
    return bid, ask, m15, dict(paired_minutes=len(shared), flat_minutes_removed=initial-len(shared))


def measure(bid, ask, m15, start, end, audit):
    candidates = sorted(session_signals(m15, bid, ask, start, end), key=lambda row: row['at_utc'])
    arms = {}
    for pattern in ('CONTINUATION', 'RECLAIM'):
        for session in (*SESSIONS, 'ALL'):
            selected = [r for r in candidates if r['pattern'] == pattern and
                        (session == 'ALL' or r['session'] == session)]
            rows, skips = replay(selected, bid, ask, TARGET_R)
            arms[f'{pattern}_{session}'] = dict(describe(rows, start, end),
                                               signals=len(selected), occupied_skips=skips)
    return dict(start_utc=iso(start), end_utc_exclusive=iso(end), audit=audit, arms=arms)


def run(root_2026, root_q4):
    bid, ask, _, m15, _, audit = load_archive(root_2026)
    old_bid, old_ask, old_m15, old_audit = load_q4(root_q4)
    return dict(source_revision=REVISION, target_r=TARGET_R,
                historical_2026=measure(bid, ask, m15, START, END, dict(paired_minutes=audit['paired_minutes'])),
                separate_2025_q4=measure(old_bid, old_ask, old_m15, Q4_START, START, old_audit),
                account_return_pct=None, execution_allowed=False, adoption_allowed=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive_2026', type=Path)
    parser.add_argument('archive_2025_q4', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    payload = json.dumps(run(args.archive_2026, args.archive_2025_q4), indent=2, allow_nan=False)
    with args.output.open('x', encoding='utf-8', newline='\n') as output:
        output.write(payload + '\n')
