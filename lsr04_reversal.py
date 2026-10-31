"""ORRERY Reversal Confirmation 04 — research adapter, no executions.

External indicator observations are UNVERIFIED until source, repaint status
and timestamp semantics have been independently inspected. BUY/SELL marks
are not broker instructions. No substitute for the video's unknown formula.
"""
from math import isfinite

def review(*,side,htf_direction,structure_confirmed,signal,signal_time,
           last_closed_time,now_time,step_seconds=300,max_age_bars=3,
           line_side="UNKNOWN",oscillator_direction="UNKNOWN",
           indicator_verified=False,spread_verified=False,
           risk_verified=False):
    if side not in ("BUY","SELL") or htf_direction not in ("UP","DOWN","RANGE","UNKNOWN"):
        raise ValueError("Invalid structural side/context")
    if signal not in ("BUY","SELL","NONE") or line_side not in ("UP","DOWN","UNKNOWN") or oscillator_direction not in ("UP","DOWN","UNKNOWN"):
        raise ValueError("Unsupported external indicator state")
    for t in (signal_time,last_closed_time,now_time):
        if type(t) not in (int,float) or not isfinite(t):
            raise ValueError("Invalid timing")
    if type(step_seconds) is not int or step_seconds<=0 or type(max_age_bars) is not int or max_age_bars<0:
        raise ValueError("Invalid age parameters")
    if any(type(v) is not bool for v in (structure_confirmed,indicator_verified,spread_verified,risk_verified)):
        raise ValueError("Explicit guards required")
    if signal_time>last_closed_time or last_closed_time>now_time:
        return dict(decision="WAIT",reason="UNCONFIRMED_OR_FUTURE_SIGNAL",
                    execution_allowed=False)
    if (now_time-signal_time)>step_seconds*max_age_bars:
        reason="STALE_SIGNAL"
    elif not structure_confirmed:
        reason="PRICE_STRUCTURE_NOT_CONFIRMED"
    elif signal!=side:
        reason="SIGNAL_MISMATCH"
    elif htf_direction not in (("UP" if side=="BUY" else "DOWN"),):
        reason="COUNTERTREND_SEPARATE_RESEARCH_REQUIRED"
    elif line_side!=htf_direction or oscillator_direction!=htf_direction:
        reason="UNCONFIRMED_LINE_OSCILLATOR"
    elif not indicator_verified:
        reason="INDICATOR_SOURCE_OR_REPAINT_UNVERIFIED"
    elif not (spread_verified and risk_verified):
        reason="BROKER_GUARDS_UNKNOWN"
    else:
        reason="RESEARCH_ALIGNMENT_ONLY"
    return dict(decision="REVIEW" if reason=="RESEARCH_ALIGNMENT_ONLY" else "WAIT",
                reason=reason,execution_allowed=False,
                indicator_origin="EXTERNAL_UNVERIFIED_UNLESS_EXPLICITLY_CHECKED",
                no_auto_orders=True)
