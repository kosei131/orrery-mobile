"""Fail-closed research gate for account-level daily and basket risk.

Day boundaries are supplied by the caller in UTC; equity includes floating PnL.
Never authorizes real orders. This is not a broker position synchronization.
"""
from datetime import datetime,timezone
from math import isfinite

def _amount(x):
    if type(x) not in (int,float) or not isfinite(x):
        raise ValueError("Finite numerical data required")
    return float(x)

def review(*,day_start_utc,now_utc,day_start_equity,current_equity,
           existing_stop_risk,proposed_stop_risk,consecutive_losses,
           daily_limit_fraction=.01,basket_limit_fraction=.01,
           maximum_consecutive_losses=3):
    if not all(isinstance(v,datetime) and v.utcoffset() is not None and
               v.utcoffset().total_seconds()==0 for v in (day_start_utc,now_utc)):
        raise ValueError("Explicit UTC session boundary required")
    if now_utc<day_start_utc or now_utc-day_start_utc>=__import__("datetime").timedelta(days=1):
        raise ValueError("Time must be within a single session")
    start=_amount(day_start_equity);current=_amount(current_equity)
    existing=_amount(existing_stop_risk);proposed=_amount(proposed_stop_risk)
    daily=_amount(daily_limit_fraction);basket=_amount(basket_limit_fraction)
    if start<=0 or current<=0 or min(existing,proposed)<0 or not 0<daily<=.05 or not 0<basket<=.05:
        raise ValueError("Invalid account and risk bounds")
    if type(consecutive_losses) is not int or consecutive_losses<0 or type(maximum_consecutive_losses) is not int or maximum_consecutive_losses<1:
        raise ValueError("Invalid loss count")
    daily_drawdown=max(0.,start-current)
    remaining_daily=start*daily-daily_drawdown
    projected_at_stops=current-existing-proposed
    reasons=[]
    if consecutive_losses>=maximum_consecutive_losses:reasons.append("LOSS_STREAK_STOP")
    if daily_drawdown>=start*daily:reasons.append("DAILY_DRAWDOWN_STOP")
    if existing+proposed>start*basket+1e-9:reasons.append("BASKET_RISK_CAP")
    if proposed>0 and existing+proposed>max(0.,remaining_daily)+1e-9:reasons.append("DAILY_REMAINING_RISK")
    if projected_at_stops<=0:reasons.append("PROJECTED_NONPOSITIVE_EQUITY")
    return dict(status="BLOCKED" if reasons else "RESEARCH_WITHIN_LIMITS",
                reasons=reasons,remaining_daily_risk=max(0.,remaining_daily),
                total_stop_risk=existing+proposed,
                projected_equity_at_stops=projected_at_stops,
                execution_allowed=False,
                caveat="Requires account-complete equity, validated stop exposure and authoritative loss-streak history.")
