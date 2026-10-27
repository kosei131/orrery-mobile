"""ORRERY research-only time-series equity & basket exposure audit.

Snapshots are supplied in chronological order. Equity and balance must come from
the same complete account (not calculated by adding P/L again). This module does
not authenticate sources, fill missing ticks, or execute orders.
"""
from decimal import Decimal
from lsr02_basket_risk import evaluate, d

def audit(snapshots, *, contract_units, usd_per_quote_unit,
          risk_cap_usd, estimated_exit_cost_usd=0):
    if not isinstance(snapshots,list) or not 2<=len(snapshots)<=100000:
        raise ValueError("Require 2-100000 time-ordered account snapshots")
    peak=None;peak_at=None;max_dd=Decimal(0);max_dd_pct=Decimal(0)
    worst_at=None;max_gross_lots=Decimal(0);max_open_positions=0
    breaches=[];rows=[];prev=None
    for snap in snapshots:
        if not isinstance(snap,dict):raise ValueError("Invalid snapshot")
        ts=d(snap.get("timestamp"))
        if prev is not None and ts<=prev: raise ValueError("Snapshots must be strictly chronological")
        prev=ts
        equity=d(snap.get("equity_usd"))
        balance=d(snap.get("balance_usd"))
        if equity<=0 or balance<=0:raise ValueError("Equity and balance must be positive")
        result=evaluate(snap.get("positions"), bid=snap.get("bid"),ask=snap.get("ask"),
                contract_units=contract_units,usd_per_quote_unit=usd_per_quote_unit,
                equity_usd=equity,balance_usd=balance,risk_cap_usd=risk_cap_usd,
                estimated_exit_cost_usd=estimated_exit_cost_usd)
        if peak is None or equity>peak:peak=equity;peak_at=ts
        dd=peak-equity
        dd_pct=dd/peak
        if dd>max_dd:
            max_dd=dd;worst_at=ts
        max_dd_pct=max(max_dd_pct,dd_pct)
        lots=d(result["lots_total"]);max_gross_lots=max(max_gross_lots,lots)
        max_open_positions=max(max_open_positions,len(snap["positions"]))
        if not result["risk_cap_ok"]:
            breaches.append(dict(at=str(ts),reason="STOP_EXPOSURE_OVER_CAP",
                                 exposure_usd=result["incremental_loss_to_stops_usd"]))
        rows.append(dict(at=str(ts),equity_usd=str(equity),balance_usd=str(balance),
                floating_drawdown_from_balance_usd=result["floating_drawdown_from_balance_usd"],
                running_equity_peak_usd=str(peak),drawdown_usd=str(dd),
                drawdown_pct=str(dd_pct),gross_lots=str(lots),
                open_positions=len(snap["positions"]),
                unrealized_pnl_usd=result["unrealized_pnl_usd"],
                incremental_stop_loss_usd=result["incremental_loss_to_stops_usd"],
                risk_cap_ok=result["risk_cap_ok"]))
    return dict(status="RESEARCH_ONLY",execution_allowed=False,
        samples=len(rows),max_equity_drawdown_usd=str(max_dd),
        max_equity_drawdown_pct=str(max_dd_pct),
        max_drawdown_at=str(worst_at) if worst_at is not None else None,
        max_gross_lots=str(max_gross_lots),
        max_open_positions=max_open_positions,
        risk_breaches=breaches,series=rows,
        warnings=["Drawdown is sampled, not true intratick maximum.",
                  "Account equity must include all current open positions and costs.",
                  "No margin/liquidation model, fills, missed samples or broker provenance."])
