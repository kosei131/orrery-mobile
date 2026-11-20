# SPDX-License-Identifier: GPL-3.0-only
"""Replay fixed Gold trade clocks against entry friction and momentum filters."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from orrery_gold_expectancy_study import COST, report, retarget
from orrery_gold_probability_study import candidates
from orrery_gold_pullback_study import END, START, load_archive
from orrery_gold_session_breakout import load_q4

TARGETS = (0.10, 0.50)
MAX_COST_SHARE = 0.35
MIN_BREAKOUT = 0.25
MIN_TRAIN = 30
WIN_GOAL = 0.95
FILTERS = ('ALL', 'COST', 'MOMENTUM', 'BOTH')


def entry_features(row, bars, bid, ask, target):
    at = row['at_utc']
    if at not in bid or at not in ask:
        return None
    buy = row['side'] == 'BUY'
    bid_open, ask_open = bid[at]['open'], ask[at]['open']
    spread = ask_open-bid_open
    risk = ask_open-row['stop'] if buy else row['stop']-bid_open
    if spread < 0 or risk <= 0:
        return None
    prior = [bars[t] for t in range(at-3600, at, 900)]
    high = max(bar['high'] for bar in prior)
    low = min(bar['low'] for bar in prior)
    if high <= low:
        return None
    close = bars[at]['close']
    penetration = (close-high if buy else low-close)/(high-low)
    return (spread+COST)/(target*risk), penetration


def collect(bid, ask, bars, end):
    clocks = {bar['close_time']: bar for bar in bars}
    cohort = candidates(bid, ask, bars, end)
    arms = {str(target): {name: [] for name in FILTERS} for target in TARGETS}
    for target in TARGETS:
        groups = arms[str(target)]
        for row in cohort:
            result = retarget(row, bid, ask, target)
            groups['ALL'].append(result)
            features = entry_features(row, clocks, bid, ask, target)
            if features is None:
                continue
            cost_ok = features[0] <= MAX_COST_SHARE
            momentum_ok = features[1] >= MIN_BREAKOUT
            for name, passed in (('COST', cost_ok), ('MOMENTUM', momentum_ok),
                                 ('BOTH', cost_ok and momentum_ok)):
                if passed:
                    groups[name].append(result)
    return arms


def eligible(rows):
    return rows['resolved'] >= MIN_TRAIN and rows['mean_r'] > 0


def summarize(arms, weeks):
    result = {}
    for target, groups in arms.items():
        result[target] = {}
        for name, rows in groups.items():
            summary = report(rows)
            summary['candidates_per_calendar_week'] = len(rows)/weeks
            summary['attained_95_pct'] = (summary['positive_rate'] or 0) >= WIN_GOAL
            by_month = {}
            for row in rows:
                if row['status'] != 'RESOLVED_REFERENCE':
                    continue
                month = datetime.fromtimestamp(row['at_utc'], timezone.utc).strftime('%Y-%m')
                by_month.setdefault(month, []).append(row)
            summary['positive_months'] = sum(report(items)['mean_r'] > 0 for items in by_month.values())
            summary['months_with_resolved_trades'] = len(by_month)
            result[target][name] = summary
    return result


def run(root_2026, root_q4):
    bid, ask, bars, _ = load_q4(root_q4)
    training = summarize(collect(bid, ask, bars, START), 92/7)
    qualified = [(target, name) for target, arms in training.items()
                 for name, values in arms.items() if name != 'ALL' and eligible(values)]
    bid, ask, _, bars, _, _ = load_archive(root_2026)
    evaluation = summarize(collect(bid, ask, bars, END), (END-START)/604800)
    return dict(
        study='gold_entry_friction', training_period='2025 Q4 UTC',
        evaluation_end_exclusive='2026-10-19 14:00 UTC',
        evaluation_start='2026-01-01 UTC', extra_round_trip_cost=COST,
        max_friction_share_of_target=MAX_COST_SHARE, min_breakout_fraction=MIN_BREAKOUT,
        minimum_training_resolved=MIN_TRAIN, win_goal=WIN_GOAL, training=training,
        training_eligible=qualified, evaluation=evaluation,
        historical_data_previously_seen=True, account_return_pct=None,
        adoption_allowed=False, execution_allowed=False,
    )


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive_2026', type=Path)
    parser.add_argument('archive_2025_q4', type=Path)
    args = parser.parse_args()
    print(json.dumps(run(args.archive_2026, args.archive_2025_q4),
                     separators=(',', ':'), allow_nan=False))
