# SPDX-License-Identifier: GPL-3.0-only
"""Replay fixed H1 trend / M15 pullback / M5 resumption on XAUUSD Bid/Ask."""
import argparse
from bisect import bisect_right
from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
from itertools import groupby
from math import isfinite
import json
from pathlib import Path

from orrery_gold_ab_archive_comparison import aggregate_complete
from orrery_gold_channel_breakout import HOLD_MINUTES, summarize
from orrery_gold_nested_wave_october import END, SEPTEMBER, complete_m5
from orrery_paired_archive_study import REVISION, iso, read_side

START = int(datetime(2026, 1, 1, tzinfo=timezone.utc).timestamp())
SMA_HOURS = 10
SLOPE_HOURS = 3
FLAT_MINUTES = 60
TARGETS = (0.5, 1.5)
WINDOWS = {'JAN_AUG': (START, SEPTEMBER), 'SEP_OCT': (SEPTEMBER, END)}
PINS = Path(__file__).with_name('research_evidence') / 'local-history-20261101' / 'gold_pullback_source_pins.json'


def suspect_flat_minutes(rows):
    def run_key(t):
        bar = rows[t]
        if bar['open'] == bar['high'] == bar['low'] == bar['close']:
            return bar['close']
        return None

    for price, clocks in groupby(rows, key=run_key):
        if price is None:
            continue
        for _, run in groupby(enumerate(clocks), key=lambda item: item[1]-60*item[0]):
            stamps = [stamp for _, stamp in run]
            if len(stamps) >= FLAT_MINUTES:
                yield from stamps


def hourly_directions(h1):
    by_close = {row['close_time']: row['close'] for row in h1}
    for at, close in by_close.items():
        closes = [by_close.get(t) for t in range(at-(SMA_HOURS+SLOPE_HOURS-1)*3600, at+1, 3600)]
        if None in closes:
            continue
        recent = sum(closes[-SMA_HOURS:])/SMA_HOURS
        prior = sum(closes[:SMA_HOURS])/SMA_HOURS
        if close > recent > prior:
            yield at, 'BUY'
        elif close < recent < prior:
            yield at, 'SELL'


def signals(m5, m15, h1, ask):
    directions = dict(hourly_directions(h1))
    clock = sorted(directions)
    by_close = {row['close_time']: row for row in m5}

    def direction(at):
        index = bisect_right(clock, at)-1
        if index >= 0 and at-clock[index] < 3600:
            return directions[clock[index]]
        return None

    for pullback in m15:
        setup = pullback['close_time']
        side = direction(setup)
        if side is None:
            continue
        buy = side == 'BUY'
        if (buy and pullback['close'] >= pullback['open']) or (
            not buy and pullback['close'] <= pullback['open']
        ):
            continue
        stop = pullback['low'] if buy else max(ask[t]['high'] for t in range(setup-900, setup, 60))
        previous = by_close[setup]
        for at in range(setup+300, setup+901, 300):
            current = by_close.get(at)
            if current is None or direction(at) != side:
                break
            resumed = current['close'] > previous['high'] if buy else current['close'] < previous['low']
            if resumed:
                yield dict(at_utc=at, side=side, setup_at_utc=setup, stop=stop)
                break
            previous = current


def evaluate_pullback(plan, bid, ask, *, structural_stop, structural_known_at,
                      horizon=HOLD_MINUTES, target_r=1.5):
    """Paired archive barrier semantics, with a configurable target for this study."""
    t = plan['first_poi_touch_close']
    side = plan['side']
    if side not in ('BUY', 'SELL') or target_r not in TARGETS:
        raise ValueError('Invalid pullback exit specification')
    stop = structural_stop
    known = structural_known_at
    if not isfinite(stop) or stop <= 0 or known > t or (t-known) % 60:
        raise ValueError('Invalid pullback stop or clock')
    buy = side == 'BUY'
    exit_side = bid if buy else ask

    def output(status, **details):
        return dict(entry_at=t, side=side, status=status, **details)

    if t not in bid or t not in ask:
        return output('UNKNOWN_ENTRY_HISTORY')
    entry = (ask if buy else bid)[t]['open']
    for stamp in range(known, t, 60):
        if stamp not in bid or stamp not in ask:
            return output('UNKNOWN_PRE_ENTRY_HISTORY')
        bar = exit_side[stamp]
        stop_touched = bar['low'] <= stop if buy else bar['high'] >= stop
        if stop_touched:
            return output('STRUCTURE_BREACHED_BEFORE_ENTRY')

    direction = 1 if buy else -1
    risk = direction*(entry-stop)
    if risk <= 0 or direction*(exit_side[t]['open']-stop) <= 0:
        return output('STOP_INVALID_AT_ENTRY')
    target = entry+direction*target_r*risk

    def resolved(stamp, price, reason):
        return output('RESOLVED_REFERENCE', r=direction*(price-entry)/risk,
                      exit_at=stamp, exit_reason=reason, entry=entry,
                      stop=stop, target=target, initial_risk_price=risk)

    deadline = t+horizon*60
    for stamp in range(t, deadline, 60):
        if stamp not in bid or stamp not in ask:
            return output('CENSORED_AT_SIDE_GAP', last_observed_until=stamp)
        bar = exit_side[stamp]
        if direction*(bar['open']-stop) <= 0:
            return resolved(stamp, bar['open'], 'STOP_AT_OBSERVED_OPEN')
        sl = bar['low'] <= stop if buy else bar['high'] >= stop
        tp = bar['high'] >= target if buy else bar['low'] <= target
        if sl and tp:
            return output('AMBIGUOUS_SAME_MINUTE', exit_at=stamp, r=None,
                          stop_first_reference_r=-1)
        if sl:
            return resolved(stamp, stop, 'SL_TOUCH')
        if tp:
            return resolved(stamp, target, 'TP_TOUCH')
    return resolved(deadline, exit_side[deadline-60]['close'], 'TIMEOUT_CLOSE')


def replay(found, bid, ask, target):
    available = 0
    rows = []
    skipped = 0
    for signal in found:
        at = signal['at_utc']
        if at < available:
            skipped += 1
            continue
        row = evaluate_pullback(
            {'first_poi_touch_close': at, 'side': signal['side']}, bid, ask,
            structural_stop=signal['stop'], structural_known_at=signal['setup_at_utc'],
            horizon=HOLD_MINUTES, target_r=target,
        )
        rows.append({**signal, **row})
        if row['status'] == 'RESOLVED_REFERENCE':
            available = row['exit_at'] + (0 if row['exit_reason'] == 'TIMEOUT_CLOSE' else 60)
        elif row['status'] in ('CENSORED_AT_SIDE_GAP', 'AMBIGUOUS_SAME_MINUTE'):
            available = at + HOLD_MINUTES*60
    return rows, skipped


def describe(rows, start, end):
    selected = [row for row in rows if start <= row['at_utc'] < end]
    result = summarize(selected)
    resolved = [row for row in selected if row['status'] == 'RESOLVED_REFERENCE']
    result['resolved_per_calendar_week'] = len(resolved)*604800/(end-start)
    result['cost_break_even_price'] = (
        sum(row['r'] for row in resolved)/sum(1/row['initial_risk_price'] for row in resolved)
        if resolved else None
    )
    return result


def run(root, *, exclude_suspect_flat=True):
    manifest = json.loads(PINS.read_text(encoding='utf-8'))
    inputs = {'bid': {}, 'ask': {}}
    audits = {}
    for side, rows in inputs.items():
        for month in range(1, 11):
            name = f'{side}_2026_{month:02}.csv'
            new, audit = read_side(root/name)
            if audit['sha256'] != manifest[name] or rows.keys() & new.keys():
                raise ValueError(f'Source pin mismatch or overlap: {name}')
            if any(datetime.fromtimestamp(t, timezone.utc).month != month or
                   datetime.fromtimestamp(t, timezone.utc).year != 2026 for t in new):
                raise ValueError(f'Source month mismatch: {name}')
            audits[name] = audit
            rows.update({t: bar for t, bar in new.items() if START <= t < END})
    bid, ask = inputs['bid'], inputs['ask']
    shared = bid.keys() & ask.keys()
    if any(ask[t][k] < bid[t][k] for t in shared for k in ('open', 'high', 'low', 'close')):
        raise ValueError('Crossed side OHLC requires source review')
    paired_before_filter = len(shared)
    unpaired_minutes = {side: len(rows)-len(shared) for side, rows in inputs.items()}
    if exclude_suspect_flat:
        suspect = set(suspect_flat_minutes(bid)) | set(suspect_flat_minutes(ask))
        for stamp in suspect:
            bid.pop(stamp, None)
            ask.pop(stamp, None)
        shared = bid.keys() & ask.keys()
    paired_bid = {t: bid[t] for t in shared}
    m5 = complete_m5(paired_bid, START, END)
    m15 = aggregate_complete(m5, 900)
    h1 = aggregate_complete(m5, 3600)
    found = sorted((row for row in signals(m5, m15, h1, ask) if row['at_utc'] < END),
                   key=lambda row: row['at_utc'])
    # A boundary clock can be reached by adjacent setups. Keep the oldest setup.
    unique = {}
    for row in found:
        unique.setdefault(row['at_utc'], row)
    arms = {}
    records = {}
    for target in TARGETS:
        rows, skipped = replay(unique.values(), bid, ask, target)
        key = str(target)
        arms[key] = dict(
            skipped_while_occupied=skipped,
            overall=describe(rows, START, END),
            by_period={name: describe(rows, a, b) for name, (a, b) in WINDOWS.items()},
            by_month={f'2026-{month:02}': describe(
                rows, int(datetime(2026, month, 1, tzinfo=timezone.utc).timestamp()),
                int(datetime(2026, month+1, 1, tzinfo=timezone.utc).timestamp()) if month < 10 else END)
                for month in range(1, 11)},
        )
        records[key] = rows
    return dict(
        status='RETROSPECTIVE_GOLD_PULLBACK', source_revision=REVISION,
        source_audits=audits, paired_minutes=len(shared),
        unpaired_minutes=unpaired_minutes,
        paired_minutes_before_filter=paired_before_filter,
        suspect_flat_paired_minutes_excluded=paired_before_filter-len(shared),
        long_flat_source_files=[name for name, audit in audits.items()
                                if audit['longest_identical_flat_minutes'] >= 60],
        start_utc=iso(START), end_utc_exclusive=iso(END),
        complete_bars=dict(M5=len(m5), M15=len(m15), H1=len(h1)),
        raw_resumption_signals=len(unique),
        duplicate_signal_clocks=len(found)-len(unique),
        raw_by_side=dict(Counter(row['side'] for row in unique.values())),
        max_hold_minutes=HOLD_MINUTES, arms=arms, records=records,
        code_sha256=sha256(Path(__file__).read_bytes()).hexdigest(),
        out_of_sample=False, account_return_pct=None, adoption_allowed=False, execution_allowed=False,
    )


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive_directory', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--include-suspect-flat', action='store_true',
                        help='Reproduce the unfiltered data quality sensitivity only')
    args = parser.parse_args()
    with args.output.open('x', encoding='utf-8', newline='\n') as output:
        json.dump(run(args.archive_directory, exclude_suspect_flat=not args.include_suspect_flat),
                  output, indent=2, allow_nan=False)
        output.write('\n')
