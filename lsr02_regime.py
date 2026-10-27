"""Experimental ORRERY regime research, not a reproduction of a trader's rules.
Thresholds are required caller parameters, uncalibrated and never order authority.
"""
from lsr02_structure import detect
from lsr02_sequence import number


def classify(bars, *, as_of, interval, lookback, trend_efficiency,
             range_efficiency, left=2, right=2):
    if type(lookback) is not int or lookback<3:
        raise ValueError('lookback must be at least 3')
    if not all(number(x) for x in (trend_efficiency,range_efficiency)) or not 0<=range_efficiency<trend_efficiency<=1:
        raise ValueError('Invalid research thresholds')
    detect(bars,as_of=as_of,interval=interval,left=left,right=right)
    result=dict(regime='UNKNOWN',reason='INSUFFICIENT_HISTORY',known_at=bars[-1]['close_time'] if bars else None,
                efficiency=None,atr_sma=None,band=None,execution_allowed=False)
    if len(bars)<lookback:
        return result
    if as_of-bars[-1]['close_time']>=interval:
        result['reason']='STALE_DATA';return result
    window=bars[-lookback:]
    structural=detect(window,as_of=as_of,interval=interval,left=left,right=right)
    closes=[b['close'] for b in window]
    travel=sum(abs(b-a) for a,b in zip(closes,closes[1:]))
    efficiency=abs(closes[-1]-closes[0])/travel if travel else 0
    true_ranges=[max(b['high']-b['low'],abs(b['high']-window[i-1]['close']),abs(b['low']-window[i-1]['close'])) for i,b in enumerate(window) if i]
    atr=sum(true_ranges)/len(true_ranges)
    result.update(efficiency=efficiency,atr_sma=atr,
                  band=(min(b['low'] for b in window),max(b['high'] for b in window)))
    enough=all(sum(p['kind']==kind for p in structural['pivots'])>=2 for kind in ('HIGH','LOW'))
    if not travel or atr<=0:
        result['reason']='NO_DIRECTIONAL_INFORMATION'
    elif not enough:
        result['reason']='INSUFFICIENT_CONFIRMED_SWINGS'
    elif structural['trend'] in ('UP','DOWN') and efficiency>=trend_efficiency:
        result.update(regime=structural['trend'],reason='STRUCTURE_AND_EFFICIENCY_AGREE')
    elif structural['trend']=='RANGE' and efficiency<=range_efficiency:
        result.update(regime='RANGE_CANDIDATE',reason='MIXED_SWINGS_LOW_EFFICIENCY')
    else:
        result['reason']='CONFLICTING_EVIDENCE'
    return result


def review_transition(previous, current):
    """Candidate lifecycle advice only. Never closes positions or changes orders."""
    allowed=('UNKNOWN','UP','DOWN','RANGE_CANDIDATE')
    if previous not in allowed or current not in allowed:
        raise ValueError('Unknown regime')
    if current=='UNKNOWN':
        return 'CANCEL_CANDIDATE_AND_WAIT'
    if previous!=current:
        return 'CANCEL_CANDIDATE_AND_REVIEW'
    return 'RECHECK_RISK_NO_AUTO_RESUME'
