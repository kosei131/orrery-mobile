# SPDX-License-Identifier: GPL-3.0-only
"""Precommitted R-multiple expectancy arithmetic for Gold research.

This is a mathematical preflight, NOT a win-rate estimate or a backtest.
All costs here are hypothetical *additional* R costs beyond any spread
already reflected in Bid/Ask entry and exit quotes; never double-count.
"""
from math import isfinite

TARGETS=(0.05,0.10,0.25,1.5)
ADDITIONAL_COST_R=(0.0,0.01,0.025,0.05)
REFERENCE_WIN_RATE=0.95


def require_nonnegative(value,name):
    if type(value) not in (int,float) or not isfinite(value) or value<0:
        raise ValueError(name+' must be finite nonnegative')
    return float(value)


def expectancy(*, win_probability, reward_r, loss_r=1.0, additional_cost_r=0.0):
    p=require_nonnegative(win_probability,'win_probability')
    reward=require_nonnegative(reward_r,'reward_r')
    loss=require_nonnegative(loss_r,'loss_r')
    cost=require_nonnegative(additional_cost_r,'additional_cost_r')
    if p>1 or reward<=0 or loss<=0:
        raise ValueError('Probabilities and positive reward/loss required')
    return p*reward-(1-p)*loss-cost


def break_even(*, reward_r, loss_r=1.0, additional_cost_r=0.0):
    reward=require_nonnegative(reward_r,'reward_r')
    loss=require_nonnegative(loss_r,'loss_r')
    cost=require_nonnegative(additional_cost_r,'additional_cost_r')
    if reward<=0 or loss<=0:
        raise ValueError('Positive reward/loss required')
    threshold=(loss+cost)/(reward+loss)
    return dict(min_win_probability=threshold if threshold<=1 else None,
                mathematically_possible=threshold<=1,
                extra_cost_r=cost)


def table(*, targets=TARGETS, additional_costs=ADDITIONAL_COST_R,
          reference_win_rate=REFERENCE_WIN_RATE):
    if not isinstance(targets,(tuple,list)) or not isinstance(additional_costs,(tuple,list)):
        raise ValueError('Bounded target and cost sequences required')
    if not (1<=len(targets)<=20 and 1<=len(additional_costs)<=20):
        raise ValueError('Bounded nonempty scenarios required')
    p=require_nonnegative(reference_win_rate,'reference_win_rate')
    if p>1:
        raise ValueError('Invalid reference win rate')
    scenarios=[]
    for reward in targets:
        require_nonnegative(reward,'reward_r')
        if reward<=0:raise ValueError('Positive reward required')
        rows=[]
        for cost in additional_costs:
            threshold=break_even(reward_r=reward,additional_cost_r=cost)
            rows.append(dict(**threshold,
                required_win_rate_pct=100*threshold['min_win_probability'] if threshold['mathematically_possible'] else None,
                expectancy_at_reference_win_rate_r=expectancy(
                    win_probability=p,reward_r=reward,additional_cost_r=cost)))
        scenarios.append(dict(reward_r=reward,additional_cost_sensitivity=rows))
    return dict(status='MATHEMATICAL_R_EXPECTANCY_PREFLIGHT_ONLY',
        assumed_loss_r=1.0,assumed_fixed_win_r=True,
        reference_win_probability_hypothetical=p,scenarios=scenarios,
        source_data_used=False,historical_win_rate_measured=False,
        spreads_already_in_bid_ask_must_not_be_counted_twice=True,
        additional_costs_not_observed_broker_charges=True,
        stop_slippage_and_gaps_not_modeled=True,account_max_dd_usd=None,
        actual_win_rate_pct=None,net_expectancy_r=None,actual_profit_usd=None,
        adoption_allowed=False,execution_allowed=False)
