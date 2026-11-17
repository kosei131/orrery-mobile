# SPDX-License-Identifier: GPL-3.0-only
"""Fixed Bollinger re-entry / mean target hypothesis on pinned Gold Bid/Ask."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
from statistics import mean, pstdev

from orrery_gold_conditional_exit import stats
from orrery_gold_channel_breakout import summarize
from orrery_gold_pullback_study import END, START, evaluate_pullback, load_archive
from orrery_gold_session_breakout import Q4_START, load_q4

PERIOD = 20
DEVIATIONS = 2
STOP_ATR = 1.5
HORIZON = 60


def signals(bars, end):
    for i in range(PERIOD, len(bars)):
        current = bars[i]
        at = current['close_time']
        prior = bars[i-PERIOD:i]
        if at >= end:
            break
        if any(row['close_time'] != at-(PERIOD-j)*900 for j, row in enumerate(prior)):
            continue
        prices = [row['close'] for row in prior]
        center = mean(prices)
        deviation = pstdev(prices)
        if deviation == 0:
            continue
        lower, upper = center-DEVIATIONS*deviation, center+DEVIATIONS*deviation
        if prices[-1] < lower < current['close'] < center:
            side = 'BUY'
        elif prices[-1] > upper > current['close'] > center:
            side = 'SELL'
        else:
            continue
        ranges = [max(b['high']-b['low'], abs(b['high']-a['close']),
                      abs(b['low']-a['close'])) for a,b in zip(prior[-15:],prior[-14:])]
        yield dict(at_utc=at, side=side, target=center, stop_distance=STOP_ATR*mean(ranges))


def measure(bid, ask, bars, start, end):
    rows = []
    eligible = 0
    skipped = 0
    for signal in signals(bars, end):
        at = signal['at_utc']
        if at < eligible:
            skipped += 1
            continue
        if at not in bid or at not in ask:
            rows.append(dict(signal, status='UNKNOWN_ENTRY_HISTORY'))
            continue
        buy = signal['side'] == 'BUY'
        exit_open = (bid if buy else ask)[at]['open']
        stop = exit_open + (-signal['stop_distance'] if buy else signal['stop_distance'])
        row = evaluate_pullback(
            dict(first_poi_touch_close=at, side=signal['side']), bid, ask,
            structural_stop=stop, structural_known_at=at,
            target_price=signal['target'], horizon=HORIZON,
        )
        rows.append(dict(signal, **row))
        if row['status'] == 'RESOLVED_REFERENCE':
            eligible = row['exit_at']+(0 if row['exit_reason']=='TIMEOUT_CLOSE' else 60)
        elif row['status'] in ('CENSORED_AT_SIDE_GAP','AMBIGUOUS_SAME_MINUTE'):
            eligible = at+HORIZON*60
    result = stats(rows)
    result['scenarios'] = summarize(rows)['scenarios']
    result['skipped_while_occupied'] = skipped
    result['resolved_per_week'] = result['resolved']*604800/(end-start)
    return result


def run(root, prior_root):
    bid, ask, _, bars, _, audit = load_archive(root)
    recent = measure(bid, ask, bars, START, END)
    bid, ask, bars, prior_audit = load_q4(prior_root)
    older = measure(bid, ask, bars, Q4_START, START)
    return dict(study='gold_band_reentry', historical_2026=recent, separate_2025_q4=older,
                paired_minutes_2026=audit['paired_minutes'],
                paired_minutes_2025_q4=prior_audit['paired_minutes'],
                code_sha256=sha256(Path(__file__).read_bytes()).hexdigest(),
                historical_data_previously_seen=True, account_return_pct=None,
                adoption_allowed=False, execution_allowed=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive_2026', type=Path)
    parser.add_argument('archive_2025_q4', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    with args.output.open('x', encoding='utf-8', newline='\n') as output:
        json.dump(run(args.archive_2026, args.archive_2025_q4), output, indent=2, allow_nan=False)
        output.write('\n')
