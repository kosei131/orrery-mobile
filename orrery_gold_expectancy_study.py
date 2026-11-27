# SPDX-License-Identifier: GPL-3.0-only
"""Compare Gold targets by estimated win probability and net expectancy."""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
from statistics import mean

from orrery_gold_conditional_exit import COST, net, stats
from orrery_gold_probability_study import MIN_BUCKET, PRIOR_WEIGHT, bucket, candidates
from orrery_gold_pullback_study import END, START, evaluate_pullback, load_archive
from orrery_gold_session_breakout import load_q4

TARGETS = (0.10, 0.25, 0.50, 1.50)
WIN_GOAL = 0.95
RESOLVED = 'RESOLVED_REFERENCE'


def retarget(row, bid, ask, target_r):
    at = row['at_utc']
    if at not in bid or at not in ask:
        return row
    buy = row['side'] == 'BUY'
    entry = (ask if buy else bid)[at]['open']
    direction = 1 if buy else -1
    risk = direction * (entry-row['stop'])
    outcome = evaluate_pullback(
        {'first_poi_touch_close': at, 'side': row['side']},
        bid, ask, structural_stop=row['stop'], structural_known_at=row['setup_at_utc'],
        horizon=60, target_price=entry+direction*target_r*risk,
    )
    return {**row, **outcome} if outcome['status'] == RESOLVED else {
        'at_utc': at, 'side': row['side'], 'compression_ratio': row['compression_ratio'], **outcome,
    }


def exit_type(row):
    return {'TP_TOUCH': 'TP', 'TIMEOUT_CLOSE': 'TIMEOUT'}.get(row['exit_reason'], 'SL')


def estimate(local, pooled):
    if len(local) < MIN_BUCKET:
        distribution = [(row, 1.0) for row in pooled]
    else:
        distribution = [(row, 1.0) for row in local]
        distribution.extend((row, PRIOR_WEIGHT/len(pooled)) for row in pooled)
    weight = sum(w for _, w in distribution)
    if not weight:
        raise ValueError('Missing training data')
    mass = defaultdict(float)
    payoff = defaultdict(float)
    win_weight = 0.0
    for row, w in distribution:
        reason = exit_type(row)
        result = net(row)
        mass[reason] += w
        payoff[reason] += w*result
        if result > 0:
            win_weight += w
    return dict(
        positive_probability=win_weight/weight,
        expected_r=sum(payoff.values())/weight,
        exits={k: dict(p=mass[k]/weight, mean_r=payoff[k]/mass[k] if mass[k] else None)
               for k in ('TP', 'SL', 'TIMEOUT')},
    )


def report(rows):
    summary = stats(rows)
    values = [net(row) for row in rows if row['status'] == RESOLVED]
    equity = peak = drawdown = 0.0
    for value in values:
        equity += value
        peak = max(peak, equity)
        drawdown = max(drawdown, peak-equity)
    return {**summary, 'candidates_per_calendar_week': len(rows)*604800/(END-START),
            'resolved_drawdown_r': drawdown if values else None,
            'exit_counts': dict(Counter(exit_type(row) for row in rows if row['status'] == RESOLVED))}


def run(root_2026, root_q4):
    bid, ask, bars, _ = load_q4(root_q4)
    training = candidates(bid, ask, bars, START)
    groups = {bucket(row) for row in training}
    models = defaultdict(dict)
    for target in TARGETS:
        training_rows = [retarget(row, bid, ask, target) for row in training]
        pooled = [row for row in training_rows if row['status'] == RESOLVED]
        for key in groups:
            local = [row for row in pooled if bucket(row) == key]
            models[key][target] = estimate(local, pooled)
        models[None][target] = estimate([], pooled)

    bid, ask, _, bars, _, _ = load_archive(root_2026)
    test = candidates(bid, ask, bars, END)
    fixed = {target: [retarget(row, bid, ask, target) for row in test] for target in TARGETS}
    policies = {'positive_ev': [], 'win_goal_with_positive_ev': []}
    goal_signals = 0
    for i, row in enumerate(test):
        scores = models.get(bucket(row), models[None])
        best = max(TARGETS, key=lambda target: scores[target]['expected_r'])
        if scores[best]['expected_r'] > 0:
            policies['positive_ev'].append(fixed[best][i])
        high = [target for target in TARGETS if scores[target]['positive_probability'] >= WIN_GOAL]
        goal_signals += bool(high)
        if high:
            goal = max(high, key=lambda target: scores[target]['expected_r'])
            if scores[goal]['expected_r'] > 0:
                policies['win_goal_with_positive_ev'].append(fixed[goal][i])
    return dict(
        training_period='2025 Q4 UTC', evaluation_start='2026-01-01 UTC',
        evaluation_end_exclusive='2026-10-19 14:00 UTC', targets_r=TARGETS,
        extra_round_trip_cost=COST, win_goal=WIN_GOAL, goal_signals=goal_signals,
        max_estimated_win_probability=max(s['positive_probability'] for m in models.values() for s in m.values()),
        fixed_targets={str(k): report(v) for k, v in fixed.items()},
        policies={k: report(v) for k, v in policies.items()},
        models={str(k): v for k, v in sorted(models.items(), key=lambda item: str(item[0]))},
        historical_data_previously_seen=True, execution_allowed=False, adoption_allowed=False,
        account_return_pct=None,
    )


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive_2026', type=Path)
    parser.add_argument('archive_2025_q4', type=Path)
    args = parser.parse_args()
    print(json.dumps(run(args.archive_2026, args.archive_2025_q4),
                     separators=(',', ':'), allow_nan=False))
