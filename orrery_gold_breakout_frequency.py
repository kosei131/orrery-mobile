# SPDX-License-Identifier: GPL-3.0-only
"""Compare fixed breakout spacing with a single position and observed exits."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from orrery_gold_ab_archive_comparison import aggregate_complete
from orrery_gold_channel_breakout import HOLD_MINUTES, LOOKBACK, evaluate_signal, signals, summarize
from orrery_gold_nested_wave_october import END, SEPTEMBER, complete_m5, read_pinned

MIN_EFFICIENCY = 0.40


def directional_efficiency(prior_closes, side):
    distance = sum(abs(b-a) for a, b in zip(prior_closes, prior_closes[1:]))
    signed_move = (prior_closes[-1]-prior_closes[0]) * (1 if side == 'BUY' else -1)
    return signed_move/distance if distance else None


def next_eligible_clock(row):
    if row['status'] != 'RESOLVED_REFERENCE':
        return row['at_utc'] + HOLD_MINUTES*60
    return row['exit_at'] + (0 if row['exit_reason'] == 'TIMEOUT_CLOSE' else 60)


def replay(found, bid, ask, *, require_efficiency):
    next_at = 0
    rows = []
    skipped_for_position = skipped_for_efficiency = 0
    for signal in found:
        if signal['at_utc'] < next_at:
            skipped_for_position += 1
            continue
        ratio = signal['directional_efficiency']
        if require_efficiency and (ratio is None or ratio < MIN_EFFICIENCY):
            skipped_for_efficiency += 1
            continue
        row = evaluate_signal(signal, bid, ask)
        rows.append(row)
        next_at = next_eligible_clock(row)
    return dict(describe(rows), skipped_for_position=skipped_for_position,
                skipped_for_efficiency=skipped_for_efficiency)


def describe(rows):
    return dict(overall=summarize(rows), by_utc_month={
        month: summarize([row for row in rows if
                          datetime.fromtimestamp(row['at_utc'], timezone.utc).strftime('%Y-%m') == month])
        for month in ('2026-09', '2026-10')
    }, records=rows)


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
    bars = [bar for bar in aggregate_complete(complete_m5(bid, SEPTEMBER, END), 900)
            if bar['close_time'] < END]
    by_clock = {bar['close_time']: bar['close'] for bar in bars}
    found = []
    for signal in signals(bars):
        at = signal['at_utc']
        prior = [by_clock[clock] for clock in range(at-LOOKBACK*900, at, 900)]
        found.append(dict(signal, directional_efficiency=directional_efficiency(prior, signal['side'])))
    fixed = [evaluate_signal(signal, bid, ask) for signal in found if signal['selected']]
    return dict(
        status='EXPLORATORY_GOLD_BREAKOUT_FREQUENCY',
        source_audits=audits, raw_signals=len(found), efficiency_threshold=MIN_EFFICIENCY,
        efficiency_definition='directional net move / sum absolute moves, previous 20 closed M15 closes',
        unresolved_release='120-minute research horizon; no recovery of unknown outcomes',
        fixed_spacing=describe(fixed),
        release_after_observed_exit=replay(found, bid, ask, require_efficiency=False),
        release_with_efficiency=replay(found, bid, ask, require_efficiency=True),
        out_of_sample=False, actual_broker_profit=None, execution_allowed=False, adoption_allowed=False,
    )


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive_directory', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    payload = json.dumps(run(args.archive_directory), indent=2, allow_nan=False)
    with args.output.open('x', encoding='utf-8', newline='\n') as output:
        output.write(payload + '\n')
