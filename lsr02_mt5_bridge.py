"""Read-only research adapter for a completed DEMO dashboard snapshot.
Not an authenticated feed, live service or order gate. No settings are guessed.
"""
from datetime import datetime
from lsr02_structure import detect
from lsr02_replay import replay
from lsr02_sequence import number

INTERVALS={'4H':14400,'15m':900,'5m':300}


def review_snapshot(snapshot, *, symbol, now, buffer, regime_config, halt_store=None):
    if not isinstance(regime_config,dict) or not number(buffer) or buffer<=0:
        raise ValueError('Explicit research settings required')
    result=dict(status='NOT_EVALUATED',execution_allowed=False,trace=[],reason=None)
    if symbol not in ('XAUUSD','USDJPY') or not number(now):
        raise ValueError('Invalid review request')
    if snapshot.get('status')!='READ_ONLY_DEMO':
        result['reason']='DEMO_SNAPSHOT_REQUIRED';return result
    try:
        checked=datetime.fromisoformat(snapshot['checked_at_utc'])
        if checked.utcoffset() is None or checked.utcoffset().total_seconds()!=0:
            raise ValueError('UTC required')
        if not 0<=now-checked.timestamp()<=5:
            raise ValueError('Snapshot stale')
        streams={}
        for tf,seconds in INTERVALS.items():
            matches=[x for x in snapshot['charts'] if x.get('symbol')==symbol and x.get('timeframe')==tf]
            if len(matches)!=1 or matches[0].get('status')!='CLOSED_BARS_AVAILABLE':
                raise ValueError('Missing or ambiguous stream')
            raw=matches[0]['bars']
            if not 2<=len(raw)<=100:raise ValueError('Invalid size')
            bars=[]
            for b in raw:
                if not number(b['time']) or b['time']%seconds:raise ValueError('Invalid UTC grid')
                bars.append(dict(close_time=b['time']+seconds,**{k:b[k] for k in ('open','high','low','close')}))
            detect(bars,as_of=now,interval=seconds)
            if now-bars[-1]['close_time']>=seconds:raise ValueError('Stale stream')
            streams[tf]=bars
        # Compare only complete overlapping lower-timeframe windows, never interpolate.
        for high_tf,low_tf in (('15m','5m'),('4H','15m')):
            checked_windows=0;duration=INTERVALS[high_tf];step=INTERVALS[low_tf]
            for high in streams[high_tf]:
                close=high['close_time'];low=[b for b in streams[low_tf] if close-duration<b['close_time']<=close]
                if len(low)!=duration//step or low[0]['close_time']!=close-duration+step or low[-1]['close_time']!=close:
                    continue
                values=dict(open=low[0]['open'],close=low[-1]['close'],high=max(b['high'] for b in low),low=min(b['low'] for b in low))
                if any(abs(values[k]-high[k])>max(abs(high[k])*1e-10,1e-10) for k in values):
                    raise ValueError('Cross-timeframe mismatch')
                checked_windows+=1
            if not checked_windows:raise ValueError('No complete overlap')
    except (KeyError,TypeError,ValueError,OverflowError):
        result['reason']='INVALID_STALE_OR_INCONSISTENT_DATA';return result
    # Persistence/config failures deliberately propagate; never reset a halt store.
    result['trace']=replay(symbol,streams['4H'],streams['15m'],streams['5m'],as_of=now,
                           buffer=buffer,regime_config=regime_config,halt_store=halt_store)
    result.update(status='RESEARCH_REPLAY_ONLY',reason='NEWS_SPREAD_ACCOUNT_RISK_NOT_CONNECTED')
    return result
