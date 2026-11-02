"""Causal, descriptive forward-range labels for offline indicator research.

Only past closed bars at each decision time may enter features. Future bars are
used exclusively as labels, never as forecasts. Gaps are rejected. No orders.
"""
from math import isfinite
from orrery_indicator_diagnostics import diagnostics

def study(bars, *, interval=300, lookback=90, horizons=(3,6,12), stride=12):
    if (not isinstance(bars,list) or type(lookback) is not int or lookback<60
        or type(stride) is not int or stride<1 or not isinstance(horizons,tuple)
        or not horizons or any(type(h) is not int or h<1 or h>60 for h in horizons)):
        raise ValueError('Bounded horizons and sufficient lookback required')
    if len(bars)>20000 or len(bars)<lookback+max(horizons):
        raise ValueError('Insufficient or oversized closed candles')
    # Validate the full contiguous observation timeline once.
    diagnostics(bars,as_of=bars[-1]['close_time'],interval=interval)
    rows=[]
    for index in range(lookback-1,len(bars)-max(horizons),stride):
        history=bars[index-lookback+1:index+1]
        observed=diagnostics(history,as_of=history[-1]['close_time'],interval=interval)
        origin=history[-1]['close']
        outcomes={}
        for h in horizons:
            future=bars[index+1:index+1+h]
            top=max(b['high'] for b in future)
            bottom=min(b['low'] for b in future)
            outcomes[str(h)]=dict(max_up_price=top,max_down_price=bottom,
               maximum_favorable_move=top-origin,maximum_adverse_move=origin-bottom,
               closing_change=future[-1]['close']-origin)
        rows.append(dict(decision_at=history[-1]['close_time'],features=observed,
                         future_label_only=outcomes))
    return dict(status='OFFLINE_FORWARD_LABELS_NOT_PREDICTIONS',samples=len(rows),
        horizons=list(horizons),rows=rows,trained_model=False,
        calibrated_probabilities=False,forecast_candles=None,
        net_profit_usd=None,execution_allowed=False)
