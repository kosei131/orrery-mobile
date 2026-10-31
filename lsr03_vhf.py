"""LSR-VHF 03: independent standard close-based VHF research.

Uses only confirmed historical closes supplied by caller; validates ordered
close_time when provided. Standard VHF has NO BUY/SELL direction or colors.
Thresholds and custom-video color logic are unresolved; no orders.
"""
from math import isfinite

def calculate(bars, *, period=28, as_of=None, interval=None):
    if type(period) is not int or not 2 <= period <= 200:
        raise ValueError("VHF period out of bounds")
    if not isinstance(bars,list):
        raise ValueError("Ordered closed bars required")
    if (as_of is None) != (interval is None):
        raise ValueError("Both as_of and interval required together")
    if as_of is not None:
        if type(as_of) not in (int,float) or not isfinite(as_of) or type(interval) is not int or interval<1:
            raise ValueError("Invalid timing parameters")
    prior_time=None
    closes=[]
    for bar in bars:
        if not isinstance(bar,dict):
            raise ValueError("Invalid bar")
        price=bar.get("close")
        if type(price) not in (float,int) or not isfinite(price) or price<=0:
            raise ValueError("Invalid close")
        closes.append(price)
        if as_of is not None:
            t=bar.get("close_time")
            if type(t) not in (int,float) or not isfinite(t) or t>as_of or (prior_time is not None and t-prior_time!=interval):
                raise ValueError("Unconfirmed, out-of-order or gapped bar")
            prior_time=t
    result=dict(status="INSUFFICIENT_HISTORY",value=None,previous_value=None,
                slope="UNKNOWN",period=period,direction="UNDEFINED",
                custom_colors="UNVERIFIED",execution_allowed=False)
    # n price changes require n+1 closes; extremes use most recent n closes.
    if len(closes)<period+2:
        return result
    def vhf(end):
        recent=closes[end-period+1:end+1]
        denom=sum(abs(closes[j]-closes[j-1]) for j in range(end-period+1,end+1))
        return (max(recent)-min(recent))/denom if denom else 0.0
    previous=vhf(len(closes)-2);current=vhf(len(closes)-1)
    result.update(status="OK",value=current,previous_value=previous,
                  slope="RISING" if current>previous else "FALLING" if current<previous else "FLAT")
    return result

def confirm_structure(bars, *, breakout_side, breakout_level, period=28,
                      min_vhf=0.4, as_of=None, interval=None):
    """One optional research hypothesis, NOT reconstructed custom VHF color."""
    if breakout_side not in ("BUY","SELL") or type(breakout_level) not in (int,float) or not isfinite(breakout_level) or breakout_level<=0:
        raise ValueError("Breakout direction and level required")
    if type(min_vhf) not in (int,float) or not isfinite(min_vhf) or not 0<=min_vhf<=1:
        raise ValueError("Research threshold invalid")
    v=calculate(bars,period=period,as_of=as_of,interval=interval)
    result=dict(**v,decision="WAIT",reason="VHF_HISTORY_MISSING",
                hypothesis="STANDARD_VHF_WITH_PRICE_CLOSE_BREAK_RESEARCH")
    if v["status"]!="OK":
        return result
    previous=bars[-2]["close"];last=bars[-1]["close"]
    crossed=(previous<=breakout_level<last if breakout_side=="BUY"
             else previous>=breakout_level>last)
    if not crossed:
        result.update(reason="NO_CONFIRMED_CLOSE_CROSS")
    elif v["value"]<min_vhf:
        result.update(reason="TREND_STRENGTH_BELOW_RESEARCH_THRESHOLD")
    elif v["slope"]!="RISING":
        result.update(reason="VHF_NOT_RISING")
    else:
        result.update(decision="REVIEW",reason="PRICE_BREAK_AND_VHF_STRENGTH_COINCIDE")
    # REVIEW cannot be READY and is NOT tradeable.
    result["execution_allowed"]=False
    return result
