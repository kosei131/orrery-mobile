"""Diagnostic-only decomposition of already calculated scenario summaries.

Regime P/L sums are descriptive; removing rows is NOT a valid counterfactual
backtest because capital sizing and trade availability would change. No orders.
"""

def diagnose(results):
    if not isinstance(results,list) or not results:
        raise ValueError("Nonempty scenario summaries required")
    output=[]
    for case in results:
        if not isinstance(case,dict) or not isinstance(case.get("by_regime"),dict):
            raise ValueError("Missing regime breakdown")
        total=case.get("net_profit")
        if type(total) not in (float,int):
            raise ValueError("Missing scenario net PnL")
        by=case["by_regime"]
        if not by or any(not isinstance(v,dict) or type(v.get("net_usd")) not in (int,float)
                         or type(v.get("trades")) is not int or v["trades"]<0
                         for v in by.values()):
            raise ValueError("Invalid regime attribution")
        attributed=sum(v["net_usd"] for v in by.values())
        if abs(attributed-total)>0.5:
            raise ValueError("Regime totals do not reconcile")
        losses=sorted(((k,v["net_usd"],v["trades"]) for k,v in by.items()),
                      key=lambda a:a[1])
        output.append(dict(rr=case.get("rr"),net_profit=total,
                           worst_regime=losses[0][0],
                           worst_regime_net_usd=losses[0][1],
                           worst_regime_trades=losses[0][2],
                           regime_summaries=by))
    return dict(status="DESCRIPTIVE_ONLY",execution_allowed=False,
        scenarios=output,requires_new_replay=True,
        limitations=[
         "Regime labels and trade grouping are supplied by the caller, not independently verified.",
         "Excluding losing regimes cannot be modeled by subtracting their historical PnL.",
         "A real counterfactual must rerun entries, capital, position overlap, costs, and stop rules.",
         "Synthetic market regimes are not evidence of real XAUUSD/USDJPY profitability."
        ])
