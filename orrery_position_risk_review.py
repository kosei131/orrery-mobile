"""Offline XAUUSD position risk review; no broker connectivity or orders.
Caller must provide exact TP/SL and USD-per-price-unit from broker specification.
Screenshot-derived values must NOT be used as authoritative.
"""
from math import isfinite

def inspect(*, side, entry, current, sl, tp, lots, usd_per_price_unit_per_lot,
            balance, equity, margin, max_risk_fraction=0.0025):
    v=(entry,current,sl,tp,lots,usd_per_price_unit_per_lot,balance,equity,margin,max_risk_fraction)
    if (side not in ('BUY','SELL') or any(type(x) not in (float,int) or not isfinite(x) or x<=0 for x in v)
         or not 0<max_risk_fraction<=0.01):
        raise ValueError('Explicit positive broker-verified inputs required')
    if not ((side=='BUY' and sl<entry<tp) or (side=='SELL' and tp<entry<sl)):
        raise ValueError('SL/TP geometry invalid')
    unit=lots*usd_per_price_unit_per_lot
    gross_stop=abs(entry-sl)*unit
    gross_target=abs(tp-entry)*unit
    open_reference=(current-entry)*unit*(1 if side=='BUY' else -1)
    return dict(status='HYPOTHETICAL_BROKER_SPEC_REVIEW_ONLY',gross_loss_to_sl_usd=gross_stop,
        gross_gain_to_tp_usd=gross_target,reference_open_pnl_usd=open_reference,
        gross_reward_risk=gross_target/gross_stop,risk_fraction_of_balance=gross_stop/balance,
        risk_fraction_of_equity=gross_stop/equity,
        budget_usd=equity*max_risk_fraction,
        exceeds_research_risk_budget=gross_stop>equity*max_risk_fraction,
        free_margin_reference=equity-margin, estimated_fee_usd=None,
        stop_slippage_usd=None,actual_close_profit_usd=None,
        execution_allowed=False)
