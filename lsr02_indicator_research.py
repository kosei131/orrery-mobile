"""Research-only ATR and Wilder ADX from confirmed candles; no orders.
Outputs UNKNOWN instead of inventing trend strength with too little history.
"""
from math import isfinite

def metrics(bars, *, period=14):
    if type(period) is not int or not 2<=period<=100 or not isinstance(bars,list):
        raise ValueError("Invalid indicator settings")
    for b in bars:
        if not isinstance(b,dict) or any(type(b.get(k)) not in (int,float) or not isfinite(b[k]) for k in ("high","low","close")):
            raise ValueError("Invalid OHLC")
        if b["low"]<=0 or b["high"]<b["low"] or not b["low"]<=b["close"]<=b["high"]:
            raise ValueError("Bad candle bounds")
    out=dict(status="INSUFFICIENT_HISTORY",atr=None,adx=None,plus_di=None,minus_di=None,
             period=period,execution_allowed=False)
    if len(bars)<2*period+1:return out
    tr=[];plus=[];minus=[]
    for i in range(1,len(bars)):
        curr,prev=bars[i],bars[i-1]
        up=curr["high"]-prev["high"];down=prev["low"]-curr["low"]
        plus.append(up if up>down and up>0 else 0.)
        minus.append(down if down>up and down>0 else 0.)
        tr.append(max(curr["high"]-curr["low"],abs(curr["high"]-prev["close"]),abs(curr["low"]-prev["close"])))
    sm_tr=sum(tr[:period]);sm_plus=sum(plus[:period]);sm_minus=sum(minus[:period])
    dx=[]
    def directional():
        p=100*sm_plus/sm_tr if sm_tr else 0.
        m=100*sm_minus/sm_tr if sm_tr else 0.
        return p,m,100*abs(p-m)/(p+m) if p+m else 0.
    dx.append(directional()[2])
    for i in range(period,len(tr)):
        sm_tr=sm_tr-sm_tr/period+tr[i]
        sm_plus=sm_plus-sm_plus/period+plus[i]
        sm_minus=sm_minus-sm_minus/period+minus[i]
        dx.append(directional()[2])
    adx=sum(dx[:period])/period
    for value in dx[period:]:
        adx=(adx*(period-1)+value)/period
    p,m,_=directional()
    out.update(status="OK",atr=sm_tr/period,adx=adx,plus_di=p,minus_di=m)
    return out

def filter_trend(bars, *, period=14, min_adx=25):
    if type(min_adx) not in (int,float) or not isfinite(min_adx) or not 0<min_adx<=100:
        raise ValueError("Invalid ADX cutoff")
    m=metrics(bars,period=period)
    if m["status"]!="OK":decision="WAIT_HISTORY"
    elif m["adx"]<min_adx:decision="WAIT_WEAK_TREND"
    elif m["plus_di"]>m["minus_di"]:decision="UP_TREND_CANDIDATE"
    elif m["minus_di"]>m["plus_di"]:decision="DOWN_TREND_CANDIDATE"
    else:decision="WAIT_NO_DIRECTION"
    return dict(**m,decision=decision,
        caution="ADX strength is not a buy/sell signal; test threshold out of sample.")
