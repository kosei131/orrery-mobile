"""Offline price-barrier outcome research. No execution, forecast or profit claim.

After a confirmed signal bar, check the first subsequent completed OHLC bar
that touches either structural SL or TP. Both touched in one bar = ambiguous,
not a fabricated win or loss. Bars must be contiguous and strictly causal.
"""
from math import isfinite

def _positive(x):
    return type(x) in (float,int) and isfinite(x) and x>0

def evaluate(bars, *, side, decision_at, entry_reference, sl, tp, interval=300,
             max_future_bars=12):
    if (side not in ('BUY','SELL') or type(decision_at) is not int or
        type(interval) is not int or interval not in (300,900,14400) or
        type(max_future_bars) is not int or not 1<=max_future_bars<=288 or
        not all(_positive(v) for v in (entry_reference,sl,tp)) or
        not ((side=='BUY' and sl<entry_reference<tp) or
             (side=='SELL' and tp<entry_reference<sl))):
        raise ValueError('Explicit structural barrier inputs required')
    if not isinstance(bars,list) or len(bars)>max_future_bars:
        raise ValueError('Bounded future closed bars required')
    previous=decision_at
    for b in bars:
        at=b.get('close_time')
        prices=[b.get(k) for k in ('open','high','low','close')]
        if (type(at) is not int or at!=previous+interval or
            not all(_positive(v) for v in prices) or
            not prices[2]<=min(prices[0],prices[3])<=max(prices[0],prices[3])<=prices[1]):
            raise ValueError('Noncontiguous or invalid future OHLC')
        previous=at
        stop_hit=b['low']<=sl if side=='BUY' else b['high']>=sl
        target_hit=b['high']>=tp if side=='BUY' else b['low']<=tp
        if stop_hit or target_hit:
            state='AMBIGUOUS_SAME_BAR' if stop_hit and target_hit else ('TP_FIRST' if target_hit else 'SL_FIRST')
            return dict(status=state,observed_at=at,bars_seen=(at-decision_at)//interval,
                resolved=state!='AMBIGUOUS_SAME_BAR',realized_net_usd=None,
                execution_allowed=False)
    return dict(status='CENSORED_HORIZON',observed_at=previous if bars else None,
        bars_seen=len(bars),resolved=False,realized_net_usd=None,execution_allowed=False)

def summarize(results):
    if not isinstance(results,list) or len(results)>100000:
        raise ValueError('Bounded barrier results required')
    allowed={'TP_FIRST','SL_FIRST','AMBIGUOUS_SAME_BAR','CENSORED_HORIZON'}
    if any(not isinstance(r,dict) or r.get('status') not in allowed or
           r.get('execution_allowed') is not False for r in results):
        raise ValueError('Only offline barrier results allowed')
    wins=sum(r['status']=='TP_FIRST' for r in results)
    losses=sum(r['status']=='SL_FIRST' for r in results)
    ambiguous=sum(r['status']=='AMBIGUOUS_SAME_BAR' for r in results)
    censored=sum(r['status']=='CENSORED_HORIZON' for r in results)
    count=wins+losses
    return dict(status='GROSS_BARRIER_OBSERVATIONS_ONLY',n=len(results),tp_first=wins,
        sl_first=losses,ambiguous=ambiguous,censored=censored,
        resolved_win_fraction=wins/count if count else None,
        full_cohort_win_rate=wins/len(results) if results and not ambiguous and not censored else None,
        net_expectancy_usd=None,pf_net=None,execution_allowed=False)
