"""ORRERY FX ultra-short scalp sizing gate — research only, never sends orders.
Evaluate user-preferred 1-2 lots against independently verified MT5 specs.
Prices and contract parameters must be supplied by a separate trusted reader.
"""
from decimal import Decimal, InvalidOperation

def D(x):
    if isinstance(x,bool): raise ValueError("Boolean numeric")
    try: v=Decimal(str(x))
    except (InvalidOperation,TypeError): raise ValueError("Bad numeric")
    if not v.is_finite(): raise ValueError("Nonfinite numeric")
    return v

def evaluate(*, side, entry, stop, target, lots, contract_units, usd_per_quote_unit,
             spread_price, slippage_price, commission_usd_per_lot_roundtrip,
             equity_usd, max_risk_fraction, max_open_risk_usd,
             existing_open_risk_usd, max_hold_seconds, quote_age_seconds,
             is_demo, spec_verified, human_approved=False):
    if side not in ("BUY","SELL") or is_demo is not True: raise ValueError("DEMO-only direction/account required")
    if human_approved is not False: raise ValueError("Research mode rejects execution approval")
    keys=(entry,stop,target,lots,contract_units,usd_per_quote_unit,spread_price,
          slippage_price,commission_usd_per_lot_roundtrip,equity_usd,max_risk_fraction,
          max_open_risk_usd,existing_open_risk_usd,max_hold_seconds,quote_age_seconds)
    e,s,t,l,u,c,sp,slip,fee,eq,fraction,cap,existing,hold,age=map(D,keys)
    if min(e,s,t,l,u,c,eq,fraction,cap,hold)<=0 or min(sp,slip,fee,existing,age)<0:
        raise ValueError("Invalid amounts")
    if side=="BUY" and not s<e<t or side=="SELL" and not t<e<s: raise ValueError("Invalid price structure")
    if not 1<=l<=2 or l.as_tuple().exponent < -2: raise ValueError("Only 1-2 lots in 0.01 steps")
    if hold>180 or age>3: return dict(status="SKIP",reason="TIME_OR_QUOTE_STALE",execution_allowed=False)
    if spec_verified is not True: return dict(status="SKIP",reason="UNVERIFIED_CONTRACT_SPECS",execution_allowed=False)
    point_value=l*u*c
    # Conservative spread and adverse slippage charged on both outcomes.
    friction=point_value*(sp+slip)+l*fee
    gross_win=abs(t-e)*point_value
    gross_loss=abs(e-s)*point_value
    net_win=gross_win-friction
    stop_loss=gross_loss+friction
    risk_cap=min(eq*fraction,cap-existing)
    ok=net_win>0 and stop_loss<=risk_cap
    return dict(status="RESEARCH_CANDIDATE" if ok else "SKIP",
        reason="WITHIN_RISK_BUDGET" if ok else "RISK_OR_COST_REJECTED",
        lots=str(l),net_target_usd=str(net_win),estimated_stop_loss_usd=str(stop_loss),
        cost_estimate_usd=str(friction),gross_rr=str(gross_win/gross_loss),
        net_rr=str(net_win/stop_loss),risk_budget_usd=str(risk_cap),
        max_hold_seconds=str(hold),human_approval_required=True,
        execution_allowed=False)
