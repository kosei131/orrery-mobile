"""Research-only basket risk snapshot: unrealized P/L and total stop exposure.
USD quote conversion and MT5 contract units must be externally verified.
No broker access, orders, margin model, or prediction.
"""
from decimal import Decimal, InvalidOperation

def d(x):
    if type(x) not in (str,int,float,Decimal): raise ValueError("Invalid numeric input")
    try: v=Decimal(str(x))
    except InvalidOperation as exc: raise ValueError("Invalid numeric input") from exc
    if not v.is_finite(): raise ValueError("Nonfinite input")
    return v

def evaluate(positions, *, bid, ask, contract_units, usd_per_quote_unit,
             equity_usd, balance_usd, risk_cap_usd, estimated_exit_cost_usd=0):
    if not isinstance(positions,list) or len(positions)>50: raise ValueError("0-50 positions required")
    bid,ask,units,conversion,equity,balance,cap,exit_cost=map(d,(
        bid,ask,contract_units,usd_per_quote_unit,equity_usd,balance_usd,
        risk_cap_usd,estimated_exit_cost_usd))
    if min(bid,ask,units,conversion,equity,balance,cap)<=0 or ask<bid or exit_cost<0:
        raise ValueError("Bad price/spec/account fields")
    current=Decimal(0); worst=Decimal(0); gross_lots=Decimal(0); rows=[]
    for p in positions:
        if not isinstance(p,dict) or p.get("side") not in ("BUY","SELL"):raise ValueError("Invalid position")
        side=p["side"];entry,lots,sl=map(d,(p.get("entry"),p.get("lots"),p.get("stop")))
        if min(entry,lots,sl)<=0:raise ValueError("Nonpositive position fields")
        if (side=="BUY" and sl>=entry) or (side=="SELL" and sl<=entry):
            raise ValueError("Invalid protective stop")
        size=lots*units*conversion; mark=bid if side=="BUY" else ask
        sign=Decimal(1) if side=="BUY" else Decimal(-1)
        mark_pnl=(mark-entry)*size*sign
        # Aggregate STOP SCENARIO: all independent stops hit; net of exit cost.
        stop_pnl=(sl-entry)*size*sign
        current+=mark_pnl
        worst+=stop_pnl-exit_cost
        gross_lots+=lots
        rows.append(dict(side=side,lots=str(lots),mark_pnl_usd=str(mark_pnl),
                         stop_pnl_usd=str(stop_pnl-exit_cost)))
    stop_loss=-worst
    # equity is assumed to reflect current MTM incl open positions, so total stop
    # incremental loss from current equity = marked basket P/L minus stop P/L.
    incremental=current-worst
    projected_equity=equity-incremental
    return dict(status="RESEARCH_ONLY",execution_allowed=False,
      lots_total=str(gross_lots),unrealized_pnl_usd=str(current),
      aggregate_stop_pnl_from_entries_usd=str(worst),
      incremental_loss_to_stops_usd=str(incremental),
      projected_equity_at_stops_usd=str(projected_equity),
      floating_drawdown_from_balance_usd=str(max(Decimal(0),balance-equity)),
      risk_cap_ok=incremental<=cap and projected_equity>0,
      positions=rows,
      caveats=["Independent stop levels may be filled worse due to gaps.",
               "Spread included through bid/ask mark; funding/commission must be accounted externally.",
               "Margin, hedging/netting broker rules and other positions not modeled."])
