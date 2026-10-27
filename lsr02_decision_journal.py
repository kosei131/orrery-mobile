"""ORRERY FX decision journal: deterministic research-only wait/trade/defend gates.
No prediction of future prices, no account connection, no orders.
The hypotheses and thresholds are ORRERY research settings, not any trader's rules.
"""
from math import isfinite

MODES=("SCALP","RANGE","STRUCTURE")
def valid(x):
    return type(x) in (int,float) and isfinite(x)

def decide(*, market_regime, data_fresh, spread_ok, news_clear,
           risk_budget_ok, loss_halt, candidates, timestamp):
    """Each candidate: mode, direction, entry, stop, target, signal_confirmed,
    expected_net_rr, invalidation, note. Never infer missing fields.
    """
    if market_regime not in ("TREND","RANGE","UNCLEAR","VOLATILE") or not valid(timestamp) or timestamp<0:
        raise ValueError("Explicit market regime and timestamp required")
    if not isinstance(candidates,list) or len(candidates)>20:
        raise ValueError("Invalid candidates")
    checks=(data_fresh,spread_ok,news_clear,risk_budget_ok,loss_halt)
    if any(type(x) is not bool for x in checks):
        raise ValueError("Explicit boolean guards required")
    result=dict(status="WAIT",reason_codes=[],candidates=[],selected=None,
                as_of=timestamp,execution_allowed=False,human_approval_required=True)
    if not data_fresh: result.update(status="DEFENSE",reason_codes=["STALE_DATA"]);return result
    if loss_halt: result.update(status="DEFENSE",reason_codes=["LOSS_HALT"]);return result
    if not risk_budget_ok: result.update(status="DEFENSE",reason_codes=["RISK_BUDGET_EXCEEDED"]);return result
    if not spread_ok or not news_clear:
        result["reason_codes"]=["SPREAD_UNACCEPTABLE" if not spread_ok else "NEWS_RISK"];return result
    for c in candidates:
        if not isinstance(c,dict) or c.get("mode") not in MODES or c.get("direction") not in ("BUY","SELL"):
            raise ValueError("Invalid candidate")
        if type(c.get("signal_confirmed")) is not bool:
            raise ValueError("Missing signal confirmation")
        nums=[c.get(k) for k in ("entry","stop","target","expected_net_rr","invalidation")]
        if not all(valid(x) for x in nums):
            raise ValueError("Invalid candidate price/ratio")
        entry,stop,target,rr,_=nums
        if min(entry,stop,target)<=0 or not ((stop<entry<target) if c["direction"]=="BUY" else (target<entry<stop)):
            raise ValueError("Invalid price geometry")
        if not isinstance(c.get("note"),str) or not c["note"].strip():
            raise ValueError("Missing rationale")
        compatible=(market_regime=="TREND" and c["mode"] in ("SCALP","STRUCTURE")
                    or market_regime=="RANGE" and c["mode"] in ("SCALP","RANGE"))
        reason=("REGIME_MISMATCH" if not compatible else
                "CONFIRMATION_PENDING" if not c["signal_confirmed"] else
                "NET_EDGE_INSUFFICIENT" if rr<1.2 else "ELIGIBLE_FOR_HUMAN_REVIEW")
        result["candidates"].append(dict(mode=c["mode"],direction=c["direction"],
            entry=entry,stop=stop,target=target,invalidation=c["invalidation"],
            expected_net_rr=rr,reason=reason,note=c["note"]))
    eligible=[x for x in result["candidates"] if x["reason"]=="ELIGIBLE_FOR_HUMAN_REVIEW"]
    if eligible:
        # This rank is a deterministic display policy, not an estimate of win probability.
        selected=max(eligible,key=lambda x:(x["expected_net_rr"],MODES.index(x["mode"])*-1))
        result.update(status="REVIEW",selected=selected,reason_codes=["HUMAN_CONFIRMATION_REQUIRED"])
    else:
        result["reason_codes"]=["NO_VALIDATED_SETUP" if market_regime in ("TREND","RANGE") else "REGIME_NOT_TRADEABLE"]
    return result
