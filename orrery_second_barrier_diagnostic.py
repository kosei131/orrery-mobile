# SPDX-License-Identifier: GPL-3.0-only
"""Whole-second Bid/Ask first-touch research diagnostic; never actual fills.

The input must already be strictly nondecreasing in time. For whole-second
sources, do not infer event ordering within a second. No quote sorting,
missing-quote interpolation, or profitability/automated trading claims.
"""
from itertools import groupby

def first_touch(quotes, side, stop, target):
    if side not in ('BUY','SELL'):
        raise ValueError('BUY or SELL required')
    if any(type(v) is not int or v<=0 for v in (stop,target)):
        raise ValueError('Positive scaled integer barriers required')
    if (side=='BUY' and stop>=target) or (side=='SELL' and stop<=target):
        raise ValueError('Directionally consistent barriers required')
    if not isinstance(quotes,(list,tuple)) or len(quotes)>2000000:
        raise ValueError('Bounded sequence required')
    prev=None
    for tick in quotes:
        if not isinstance(tick,(list,tuple)) or len(tick)!=3:
            raise ValueError('Exact clock, bid, ask tuple required')
        ts,bid,ask=tick
        if (any(type(v) is not int for v in tick) or ts<0 or ts%1000
            or bid<=0 or ask<bid):
            raise ValueError('Whole-second noncrossed quotes required')
        if prev is not None and ts<prev:
            raise ValueError('Clock reversal blocks first-touch inference')
        prev=ts
    def result(status,t=None,n=None):
        return dict(status=status,at_utc_ms=t,observed_quotes_in_second=n,
            intrasecond_order_verified=False,broker_fill_verified=False,
            actual_profit_usd=None,backtest_ready=False,execution_allowed=False)
    for stamp,records in groupby(quotes,key=lambda x:x[0]):
        prices=[bid if side=='BUY' else ask for _,bid,ask in records]
        sl=any(p<=stop for p in prices) if side=='BUY' else any(p>=stop for p in prices)
        tp=any(p>=target for p in prices) if side=='BUY' else any(p<=target for p in prices)
        if sl and tp:return result('AMBIGUOUS_SAME_SECOND',stamp,len(prices))
        if sl:return result('STOP_OBSERVED',stamp,len(prices))
        if tp:return result('TARGET_OBSERVED',stamp,len(prices))
    return result('UNRESOLVED')
