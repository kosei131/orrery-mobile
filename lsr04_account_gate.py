"""Fail-closed research gate for account-level daily and basket risk.

Explicit UTC boundaries; current equity includes floating PnL. External cash
is excluded from daily performance only with caller verification. Fixed
opening-equity budgets are never increased by deposits. No order permission.
"""
from datetime import datetime, timedelta
from decimal import Decimal
from math import isfinite


def _amount(value):
    if type(value) not in (int, float) or not isfinite(value):
        raise ValueError("Finite numerical data required")
    return Decimal(str(value))


def review(*, day_start_utc, now_utc, day_start_equity, current_equity,
           existing_stop_risk, proposed_stop_risk, consecutive_losses,
           daily_limit_fraction=.01, basket_limit_fraction=.01,
           maximum_consecutive_losses=3, external_cash_net=0,
           cash_flows_verified=False):
    if not all(isinstance(v, datetime) and v.utcoffset() is not None and
               v.utcoffset().total_seconds() == 0 for v in (day_start_utc, now_utc)):
        raise ValueError("Explicit UTC session boundary required")
    if now_utc < day_start_utc or now_utc-day_start_utc >= timedelta(days=1):
        raise ValueError("Time must be within a single session")
    start, current = _amount(day_start_equity), _amount(current_equity)
    existing, proposed = _amount(existing_stop_risk), _amount(proposed_stop_risk)
    daily, basket = _amount(daily_limit_fraction), _amount(basket_limit_fraction)
    cash = _amount(external_cash_net)
    if type(cash_flows_verified) is not bool or (cash != 0 and not cash_flows_verified):
        raise ValueError("Nonzero external cash requires verified reconciliation")
    if start <= 0 or current <= 0 or min(existing, proposed) < 0 or not 0 < daily <= Decimal('.05') or not 0 < basket <= Decimal('.05'):
        raise ValueError("Invalid account and risk bounds")
    if type(consecutive_losses) is not int or consecutive_losses < 0 or type(maximum_consecutive_losses) is not int or maximum_consecutive_losses < 1:
        raise ValueError("Invalid loss count")
    adjusted = current-cash
    daily_drawdown = max(Decimal(0), start-adjusted)
    remaining_daily = max(Decimal(0), start*daily-daily_drawdown)
    total_risk = existing+proposed
    projected_at_stops = current-total_risk  # actual equity, never synthetic cash-adjusted equity
    reasons = []
    if consecutive_losses >= maximum_consecutive_losses:
        reasons.append("LOSS_STREAK_STOP")
    if daily_drawdown >= start*daily:
        reasons.append("DAILY_DRAWDOWN_STOP")
    if total_risk > start*basket:
        reasons.append("BASKET_RISK_CAP")
    if total_risk > remaining_daily:
        reasons.append("DAILY_REMAINING_RISK")
    if projected_at_stops <= 0:
        reasons.append("PROJECTED_NONPOSITIVE_EQUITY")
    values = dict(remaining_daily_risk=remaining_daily, total_stop_risk=total_risk,
                  projected_equity_at_stops=projected_at_stops,
                  cash_adjusted_equity=adjusted, external_cash_net=cash,
                  daily_drawdown=daily_drawdown, daily_loss_budget=start*daily,
                  basket_risk_budget=start*basket)
    result = {k: float(v) for k, v in values.items()}
    if not all(isfinite(v) for v in result.values()):
        raise ValueError("Account risk arithmetic overflow")
    return dict(result, status="BLOCKED" if reasons else "RESEARCH_WITHIN_LIMITS",
                reasons=reasons, cash_flows_verified=cash_flows_verified,
                execution_allowed=False,
                caveat="Research fixed-opening-equity rule, not a funding-provider rule. Requires complete equity, costs, stop exposure and authoritative streak history.")
