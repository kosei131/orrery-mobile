# SPDX-License-Identifier: GPL-3.0-only
"""Evaluate past-only XAUUSD take-profit-first probabilities on later entries."""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
from statistics import mean

from orrery_gold_compression_study import END, START, TARGET_R, signals
from orrery_gold_conditional_exit import COST, stats
from orrery_gold_pullback_study import load_archive, replay
from orrery_gold_session_breakout import load_q4

HORIZON = 60
PRIOR_WEIGHT = 30
MIN_BUCKET = 30
PREMIUM = 0.03


def bucket(row):
    return row['side'], row['compression_ratio'] <= 0.70


def fit(rows):
    known = [row for row in rows if row['status'] == 'RESOLVED_REFERENCE']
    if not known:
        raise ValueError('No resolved training outcomes')
    prior = mean(row['exit_reason'] == 'TP_TOUCH' for row in known)
    groups = defaultdict(list)
    for row in known:
        groups[bucket(row)].append(row['exit_reason'] == 'TP_TOUCH')
    scores = {key: (sum(labels)+PRIOR_WEIGHT*prior)/(len(labels)+PRIOR_WEIGHT)
              for key, labels in groups.items() if len(labels) >= MIN_BUCKET}
    return prior, scores


def evaluate(training, test):
    prior, scores = fit(training)
    labeled = []
    by_bucket = defaultdict(list)
    selected = []
    for row in test:
        key = bucket(row)
        probability = scores.get(key, prior)
        by_bucket[key].append(row)
        if probability >= prior+PREMIUM:
            selected.append(row)
        if row['status'] == 'RESOLVED_REFERENCE':
            labeled.append((probability, row['exit_reason'] == 'TP_TOUCH'))
    if not labeled:
        raise ValueError('No resolved evaluation outcomes')
    calibration = {}
    for key, rows in sorted(by_bucket.items()):
        known = [row for row in rows if row['status'] == 'RESOLVED_REFERENCE']
        calibration[str(key)] = dict(
            predictions=len(rows), resolved=len(known), predicted=scores.get(key, prior),
            actual=mean(row['exit_reason'] == 'TP_TOUCH' for row in known) if known else None,
            tp_sl_timeout=dict(Counter(row['exit_reason'] for row in known)),
        )
    return dict(
        train_resolved=sum(row['status'] == 'RESOLVED_REFERENCE' for row in training),
        baseline_probability=prior, brier_model=mean((p-y)**2 for p, y in labeled),
        brier_baseline=mean((prior-y)**2 for _, y in labeled),
        calibration=calibration, all_entries=stats(test), selected_entries=stats(selected),
        selected_per_calendar_week=len(selected)*604800/(END-START),
        predictions_at_least_95_pct=sum(scores.get(bucket(row), prior) >= .95 for row in test),
    )


def candidates(bid, ask, bars, end):
    return replay(signals(bars, ask, end), bid, ask, TARGET_R, horizon=HORIZON)[0]


def run(root_2026, root_q4):
    bid, ask, bars, _ = load_q4(root_q4)
    training = candidates(bid, ask, bars, START)
    bid, ask, _, bars, _, _ = load_archive(root_2026)
    test = candidates(bid, ask, bars, END)
    return dict(training_period='2025 Q4 UTC', test_period='2026-01-01 through 2026-10-19 14:00 UTC',
                target_r=TARGET_R, horizon_minutes=HORIZON, extra_cost=COST,
                prior_weight=PRIOR_WEIGHT, selection_premium=PREMIUM,
                later_period_seen_in_prior_research=True,
                account_return_pct=None, adoption_allowed=False, execution_allowed=False,
                results=evaluate(training, test))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive_2026', type=Path)
    parser.add_argument('archive_2025_q4', type=Path)
    args = parser.parse_args()
    print(json.dumps(run(args.archive_2026, args.archive_2025_q4), indent=2, allow_nan=False))
