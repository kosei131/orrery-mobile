"""ORRERY FX: conservative research-only TP/SL P&L preview.

Not an MT5 broker contract-spec reader or order planner. Currency must be USD;
contract_units_per_lot must be supplied from a VERIFIED MT5 symbol specification.
No execution APIs. Costs (spread/slippage/commissions/swap) are an explicit
round-trip estimate PER POSITION, denominated in USD.
"""
from decimal import Decimal, InvalidOperation

def dec(v):
    if isinstance(v, bool) or not isinstance(v, (str, int, float, Decimal)):
        raise ValueError("Invalid numeric input")
    try:
        n = Decimal(str(v))
    except InvalidOperation as exc:
        raise ValueError("Invalid decimal input") from exc
    if not n.is_finite():
        raise ValueError("Non-finite numeric input")
    return n

def preview(positions, *, take_profit, stop_loss, contract_units_per_lot,
            usd_per_quote_unit, estimated_round_trip_cost_usd, max_total_stop_loss_usd):
    """Identical shared TP/SL and verified contract basis, one side at a time.

    All inputs are hypothetical, except where caller independently verifies specs.
    Does not model margin, hedging/netting rules, stop gaps or fills.
    """
    if not isinstance(positions, list) or not 1 <= len(positions) <= 50:
        raise ValueError("Require 1-50 positions")
    tp, sl, units, conversion, cost, cap = map(dec, (take_profit, stop_loss,
        contract_units_per_lot, usd_per_quote_unit, estimated_round_trip_cost_usd,
        max_total_stop_loss_usd))
    if not (tp>0 and sl>0 and units>0 and conversion>0 and cost>=0 and cap>0):
        raise ValueError("Invalid trade settings")
    sides=set()
    totals={"lots":Decimal(0),"gross_tp_usd":Decimal(0),
            "gross_sl_usd":Decimal(0)}
    rows=[]
    for p in positions:
        if not isinstance(p,dict) or p.get("side") not in ("BUY","SELL"):
            raise ValueError("Invalid position")
        side=p["side"];sides.add(side)
        entry,lots=map(dec,(p.get("entry"),p.get("lots")))
        if entry<=0 or lots<=0: raise ValueError("Invalid entry or lot")
        if side=="BUY" and not sl<entry<tp or side=="SELL" and not tp<entry<sl:
            raise ValueError("TP and SL must bracket each entry")
        multiplier=Decimal(1) if side=="BUY" else Decimal(-1)
        weight=lots*units*conversion
        gross_tp=(tp-entry)*weight*multiplier
        gross_sl=(sl-entry)*weight*multiplier
        totals["lots"]+=lots
        totals["gross_tp_usd"]+=gross_tp
        totals["gross_sl_usd"]+=gross_sl
        rows.append(dict(side=side,entry=str(entry),lots=str(lots),
                         gross_tp_usd=str(gross_tp),gross_sl_usd=str(gross_sl)))
    if len(sides)!=1:
        raise ValueError("Mixed BUY/SELL baskets require a different risk model")
    net_tp=totals["gross_tp_usd"]-cost
    net_sl=totals["gross_sl_usd"]-cost
    stop_risk=-net_sl
    return {"status":"RESEARCH_ESTIMATE_ONLY", "execution_allowed":False,
        "risk_budget_ok":stop_risk<=cap, "lots":str(totals["lots"]),
        "net_tp_usd":str(net_tp),"net_sl_usd":str(net_sl),
        "estimated_stop_risk_usd":str(stop_risk),
        "expected_net_rr":str(net_tp/stop_risk) if stop_risk>0 else None,
        "positions":rows,
        "warnings":["Assumes exact TP/SL fills; gaps may increase losses.",
                    "Does not model broker margin, hedging restrictions, swaps changing over time.",
                    "Conversion and contract specifications must be verified from MT5."]}
