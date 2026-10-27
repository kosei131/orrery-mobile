"""Offline, conservative 4H/15m/5m evidence adapter. No READY or orders.
All inputs are closed UTC bars from one caller-verified symbol/feed.
"""
from lsr02_structure import detect
from lsr02_sequence import Candidate, number
from lsr02_regime import classify, review_transition


def replay(symbol, h4, m15, m5, *, as_of, buffer, lifetime=3600, left=2, right=2, regime_config=None):
    if symbol not in ('XAUUSD','USDJPY') or not number(buffer) or buffer<=0 or not number(lifetime) or lifetime<=0:
        raise ValueError('Invalid replay settings')
    # Validate complete inputs, including time order and gaps; never discard unfinished bars silently.
    for bars, interval in ((h4,14400),(m15,900),(m5,300)):
        detect(bars,as_of=as_of,interval=interval,left=left,right=right)
    if regime_config is not None:
        if not isinstance(regime_config,dict) or set(regime_config)!={'lookback','trend_efficiency','range_efficiency'}:
            raise ValueError('Explicit regime research parameters required')
        classify([],as_of=as_of,interval=14400,left=left,right=right,**regime_config)
    candidate=None; trace=[]; used=set(); review_required=False; previous_regime='UNKNOWN' 
    def emit(row):
        if regime_config is not None:
            row.update(regime=regime['regime'],regime_reason=regime['reason'],efficiency=regime['efficiency'])
        trace.append(row)
    for b in m5:
        t=b['close_time']
        context=[x for x in h4 if x['close_time']<=t]
        h=detect(context,as_of=t,interval=14400,left=left,right=right)
        fresh=bool(context) and t-context[-1]['close_time']<14400
        regime=None
        if regime_config is not None:
            regime=classify(context,as_of=t,interval=14400,left=left,right=right,**regime_config)
            action=review_transition(previous_regime,regime['regime'])
            previous_regime=regime['regime']
            if candidate is not None and candidate.state!='INVALID' and action!='RECHECK_RISK_NO_AUTO_RESUME':
                candidate.state='INVALID';review_required=True
                emit(dict(at=t,side=candidate.side,state='INVALID',
                    stop=candidate.sweep_extreme-buffer if candidate.side=='BUY' else candidate.sweep_extreme+buffer,
                    poi=candidate.poi,readiness='BLOCKED_UNVERIFIED_GUARDS',
                    reason='REGIME_REVIEW_REQUIRED',regime=regime['regime'],regime_reason=regime['reason']))
            if review_required:
                continue
        fifteen=[x for x in m15 if x['close_time']<=t]
        s=detect(fifteen,as_of=t,interval=900,left=left,right=right)
        # Only process a 15m event at the same close, never a delayed historical sweep.
        sweeps=[e for e in s['events'] if e['kind']=='SWEEP' and e['known_at']==t]
        if candidate is not None and candidate.state!='INVALID':
            current=detect([x for x in m5 if x['close_time']<=t],as_of=t,interval=300,left=left,right=right)
            direction='UP' if candidate.side=='BUY' else 'DOWN'
            events=[e for e in current['events'] if e['known_at']==t and e['kind'] in ('BOS','CHoCH') and e['direction']==direction and e['poi'] and m5[e['poi']['index']]['close_time']>=candidate.created_at]
            evidence=dict(data_ok=True,context_valid=fresh and h['trend']==candidate.context_direction,
                          news_clear=False,spread_ok=False,risk_checked=False)
            # External guards are deliberately unknown. Use separate structural walk below;
            # this adapter must not certify readiness without actual spread/news/account data.
            old=candidate.state
            stop=candidate.sweep_extreme-buffer if candidate.side=='BUY' else candidate.sweep_extreme+buffer
            hit=b['low']<=stop if candidate.side=='BUY' else b['high']>=stop
            reason=None
            if t>=candidate.expires_at or hit or not evidence['context_valid']:
                reason='EXPIRED' if t>=candidate.expires_at else 'STOP_TOUCHED' if hit else 'HTF_CONTEXT_INVALID'
                candidate.state='INVALID'
            elif old=='SWEEP' and events:
                p=events[0]['poi'];candidate.poi=(p['low'],p['high']);candidate.state='CONFIRM'
            elif old=='CONFIRM' and b['low']<=candidate.poi[1] and b['high']>=candidate.poi[0]:
                candidate.state='RETEST'
            emit(dict(at=t,side=candidate.side,state=candidate.state,stop=stop,poi=candidate.poi,reason=reason,readiness='BLOCKED_UNVERIFIED_GUARDS'))
        # Existing candidate, even invalidated at this close, cannot restart at the same close.
        elif fresh and len(sweeps)==1:
            e=sweeps[0];key=(e['known_at'],e['direction'])
            side='SELL' if e['direction']=='UP' else 'BUY'
            expected='DOWN' if side=='SELL' else 'UP'
            if key not in used and h['trend']==expected and (regime is None or regime['regime']==expected):
                used.add(key);source=fifteen[e['index']]
                extreme=source['high'] if side=='SELL' else source['low']
                candidate=Candidate(symbol,side,t,t+lifetime,context[-1]['close_time'],expected,extreme,buffer)
                candidate.state='SWEEP';candidate.last_at=t
                emit(dict(at=t,side=side,state='SWEEP',stop=extreme+buffer if side=='SELL' else extreme-buffer,poi=None,readiness='BLOCKED_UNVERIFIED_GUARDS'))
    return trace
