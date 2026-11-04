# SPDX-License-Identifier: GPL-3.0-only
"""Exploratory H1/M15 nested wave comparison using pinned public Gold bars."""
import argparse
from collections import Counter, defaultdict
from hashlib import sha256
import json
from pathlib import Path

from orrery_gold_mtf_ab_replay import BARS_PINS, RAW_PIN
from orrery_gold_mtf_ab_price_references import evaluate
from orrery_real_bars_lsr_bridge import load

M15 = 900
H1 = 3600
WAIT_BARS = 4
COSTS = (0, 0.30, 0.54, 0.70)


def complete_hours(bars):
    groups = defaultdict(list)
    for bar in bars:
        groups[bar['open_time'] // H1 * H1].append(bar)
    return {
        start + H1: dict(open=group[0]['open'], close=group[-1]['close'],
                         low=min(b['low'] for b in group),
                         high=max(b['high'] for b in group))
        for start, group in groups.items()
        if [b['open_time'] for b in group] == list(range(start, start + H1, M15))
    }


def wait_for_resume(bars, at, origin, reversal_low):
    """BUY study only. First confirmed pullback then close above its high."""
    pullback = None
    previous = origin
    for step in range(1, WAIT_BARS + 1):
        clock = at + step * M15
        bar = bars.get(clock)
        if bar is None:
            return 'WAIT_DATA_GAP', None
        if bar['low'] <= reversal_low:
            return 'WAIT_INVALIDATED', None
        if pullback is not None and bar['close'] > pullback['high']:
            return 'RESUMED', clock
        if bar['close'] < previous['close'] and bar['low'] < previous['low']:
            pullback = bar
        previous = bar
    return 'WAIT_EXPIRED', None


def candidates(m15):
    hourly = complete_hours(m15)
    by_close = {b['close_time']: b for b in m15}
    seen = set()
    for at, signal in by_close.items():
        hour = at // H1 * H1
        base, impulse, correction = (hourly.get(hour - k * H1) for k in (2, 1, 0))
        if hour in seen or not all((base, impulse, correction)):
            continue
        if not (impulse['close'] > base['high'] and correction['close'] < impulse['close']
                and correction['low'] > impulse['low']):
            continue
        older, recent = (by_close.get(at - k * M15) for k in (2, 1))
        if not older or not recent or not (
            recent['low'] < older['low'] and recent['high'] < older['high']
            and signal['close'] > recent['high']
        ):
            continue
        stop = min(recent['low'], signal['low'])
        room = impulse['high'] - signal['close']
        if room <= 0 or stop >= signal['close']:
            continue
        seen.add(hour)
        initial = dict(candidate_id=f'GOLD_NESTED_WAVE_BUY:{at}', family='A_CONTINUATION',
                       side='BUY', known_at_utc=at, fill_verified=False,
                       execution_allowed=False, structural_stop=stop,
                       indicative_close=signal['close'], known_room_price=room)
        state, later = wait_for_resume(by_close, at, signal, stop)
        yield initial, state, dict(initial, known_at_utc=later) if later else None


def summarize(records):
    resolved = [row for row in records if row['reference_r'] is not None]
    scenarios = []
    for cost in COSTS:
        values = [r['reference_r'] - cost / abs(float(r['entry_open_reference']) -
                                                 float(r['structural_stop'])) for r in resolved]
        losses = -sum(r for r in values if r < 0)
        scenarios.append(dict(cost_price=cost, mean_r=sum(values)/len(values) if values else None,
                              positive_pct=100*sum(r > 0 for r in values)/len(values) if values else None,
                              pf=sum(r for r in values if r > 0)/losses if losses else None))
    return dict(candidates=len(records), resolved=len(resolved),
                states=dict(Counter(r['state'] for r in records)), scenarios=scenarios)


def compare_entries(early, late, target_ceiling):
    """Retain the entry geometry even when an exit is unresolved."""
    def entry_details(row):
        raw_entry = row['entry_open_reference']
        entry = float(raw_entry) if raw_entry is not None else None
        stop = float(row['structural_stop'])
        target = row['target_reference']
        risk = entry - stop if entry is not None else None
        return dict(entry=entry, stop=stop, risk_price=risk,
                    room_to_ceiling_price=target_ceiling-entry if entry is not None else None,
                    target=float(target) if target is not None else None,
                    target_r=(float(target)-entry)/risk if target is not None and risk > 0 else None,
                    state=row['state'], reference_r=row['reference_r'])

    immediate = entry_details(early)
    delayed = entry_details(late)
    change = (delayed['entry'] - immediate['entry']
              if immediate['entry'] is not None and delayed['entry'] is not None else None)
    return dict(candidate_id=early['candidate_id'], known_at_utc=early['known_at_utc'],
                delay_minutes=(late['known_at_utc']-early['known_at_utc'])//60,
                target_ceiling=target_ceiling, entry_change_price=change,
                immediate=immediate, delayed=delayed)


def run(raw, bars_dir):
    if sha256(raw.read_bytes()).hexdigest() != RAW_PIN:
        raise ValueError('Original public M1 pin mismatch')
    bars = {}
    for timeframe in ('M5', 'M15'):
        path = bars_dir / f'XAUUSD_{timeframe}_UNVERIFIED_QUOTE.csv'
        if sha256(path.read_bytes()).hexdigest() != BARS_PINS[timeframe]:
            raise ValueError(f'{timeframe} source pin mismatch')
        bars[timeframe] = load(path, timeframe)['bars']
    pairs = list(candidates(bars['M15']))
    m5 = [{k: v for k, v in row.items() if k != 'open_time'} for row in bars['M5']]
    immediate = evaluate(m5, [row for row, _, _ in pairs])['records']
    delayed = evaluate(m5, [row for _, _, row in pairs if row is not None])['records']
    delayed_ids = {r['candidate_id'] for r in delayed}
    missed = [r for r in immediate if r['candidate_id'] not in delayed_ids]
    immediate_by_id = {r['candidate_id']: r for r in immediate}
    ceilings = {row['candidate_id']: row['indicative_close'] + row['known_room_price']
                for row, _, _ in pairs}
    entry_comparison = [compare_entries(immediate_by_id[r['candidate_id']], r,
                                        ceilings[r['candidate_id']]) for r in delayed]
    matched = [r for r in delayed if r['reference_r'] is not None
               and immediate_by_id[r['candidate_id']]['reference_r'] is not None]
    return dict(status='EXPLORATORY_NESTED_WAVE_BUY_PUBLIC_OHLC', source_sha256=RAW_PIN,
                wait_status=dict(Counter(state for _, state, _ in pairs)),
                wait_by_candidate={row['candidate_id']: state for row, state, _ in pairs},
                immediate=summarize(immediate), delayed=summarize(delayed),
                immediate_on_both_resolved=summarize([immediate_by_id[r['candidate_id']] for r in matched]),
                delayed_on_both_resolved=summarize(matched),
                missed_immediate=summarize(missed), paired_entry_geometry=entry_comparison,
                missed_positive_reference=sum(r['reference_r'] > 0 for r in missed if r['reference_r'] is not None),
                missed_negative_reference=sum(r['reference_r'] < 0 for r in missed if r['reference_r'] is not None),
                actual_win_rate_pct=None, net_expectancy_r=None, account_return_pct=None,
                out_of_sample=False, execution_allowed=False, adoption_allowed=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for argument in ('raw', 'bars_dir', 'output'):
        parser.add_argument(argument, type=Path)
    args = parser.parse_args()
    result = json.dumps(run(args.raw, args.bars_dir), indent=2, allow_nan=False)
    with args.output.open('x', encoding='utf-8', newline='\n') as output:
        output.write(result + '\n')
