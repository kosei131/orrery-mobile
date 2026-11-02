"""Causal indicator diagnostics for ORRERY FX research. Not trade signals.

Use *completed*, contiguous equal-spacing candles only. No future candles,
probabilities, account PnL, automatic trading, or strategy promotion.
"""
from math import isfinite

def _sma(v): return sum(v)/len(v)

def diagnostics(bars, *, as_of, interval, atr_period=14, adx_period=14,
                ema_fast=20, ema_slow=50, cloud=(9,26,52), donchian=20):
    if (type(as_of) is not int or type(interval) is not int or interval not in (300,900,14400)
            or any(type(n) is not int or n<2 or n>300 for n in
                   (atr_period,adx_period,ema_fast,ema_slow,donchian,*cloud))
            or not cloud[0]<cloud[1]<cloud[2] or not ema_fast<ema_slow):
        raise ValueError('Invalid as-of clock or indicator configuration')
    if not isinstance(bars,list) or not 2<=len(bars)<=10000:
        raise ValueError('Bounded completed candles required')
    previous=None
    for b in bars:
        t=b.get('close_time')
        o,h,l,c=(b.get(k) for k in ('open','high','low','close'))
        if (type(t) is not int or t>as_of or
            previous is not None and t-previous!=interval or
            any(type(v) not in (int,float) or not isfinite(v) or v<=0 for v in (o,h,l,c))
            or not l<=min(o,c)<=max(o,c)<=h):
            raise ValueError('Noncausal, gapped or invalid OHLC')
        previous=t
    close=[b['close'] for b in bars]
    high=[b['high'] for b in bars]
    low=[b['low'] for b in bars]
    def ema(p):
        if len(close)<p:return None
        value=_sma(close[:p])
        k=2/(p+1)
        for c in close[p:]: value+=k*(c-value)
        return value
    def midpoint(p):
        return (max(high[-p:])+min(low[-p:]))/2
    tr=[]; plus=[]; minus=[]
    for i in range(1,len(bars)):
        tr.append(max(high[i]-low[i], abs(high[i]-close[i-1]), abs(low[i]-close[i-1])))
        up=high[i]-high[i-1];down=low[i-1]-low[i]
        plus.append(up if up>down and up>0 else 0)
        minus.append(down if down>up and down>0 else 0)
    def wilder(values,p):
        if len(values)<p:return []
        output=[sum(values[:p])]
        for v in values[p:]: output.append(output[-1]-output[-1]/p+v)
        return output
    smtr=wilder(tr,adx_period)
    smplus=wilder(plus,adx_period)
    smminus=wilder(minus,adx_period)
    dx=[]
    for t,p,m in zip(smtr,smplus,smminus):
        total=p+m
        dx.append(100*abs(p-m)/total if total else 0.0)
    adx_values=wilder(dx,adx_period)
    adx=adx_values[-1]/adx_period if adx_values else None
    atr_values=wilder(tr,atr_period)
    atr=atr_values[-1]/atr_period if atr_values else None
    cloud_out=None
    if len(bars)>=cloud[2]:
        tenkan=midpoint(cloud[0]);kijun=midpoint(cloud[1]);span_b=midpoint(cloud[2])
        cloud_out=dict(tenkan=tenkan,kijun=kijun,
                       span_a=(tenkan+kijun)/2,span_b=span_b,
                       displacement_bars=cloud[1],
                       note='Plot shift is not future-price prediction')
    dc=None
    if len(bars)>=donchian+1:
        dc=dict(previous_upper=max(high[-donchian-1:-1]),
                previous_lower=min(low[-donchian-1:-1]))
    return dict(status='DIAGNOSTICS_ONLY_NO_FORECAST',as_of=as_of,
        latest_closed_at=bars[-1]['close_time'],samples=len(bars),
        ema_fast=ema(ema_fast),ema_slow=ema(ema_slow),
        atr=atr,adx=adx,plus_di=(100*smplus[-1]/smtr[-1] if smtr and smtr[-1] else None),
        minus_di=(100*smminus[-1]/smtr[-1] if smtr and smtr[-1] else None),
        ichimoku=cloud_out,donchian=dc,
        forecast_candles=None,up_probability=None,down_probability=None,
        execution_allowed=False)
