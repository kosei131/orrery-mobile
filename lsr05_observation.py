# SPDX-License-Identifier: GPL-3.0-only
"""Observe HalfTrend snapshots using an injected existing SignalJournal.

No imports from the ORRERY core, automatic integration, orders or repaint
certification. The caller owns persistence of the returned observation events.
"""
from hashlib import sha256
from json import dumps, loads
from math import isfinite, isclose
from lsr05_session_clock import audit_close_times


def _bytes(value):
    return dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()


def _finite(value):
    return type(value) in (int,float) and isfinite(value)


def _hex(value,n):
    return isinstance(value,str) and len(value)==n and all(c in '0123456789abcdef' for c in value)


class HalfTrendObserver:
    def __init__(self, signal_journal, *, max_events=100000):
        if not callable(getattr(signal_journal,'observe',None)) or type(max_events) is not int or not 1<=max_events<=500000:
            raise ValueError('Existing signal journal and bounded event capacity required')
        self.journal=signal_journal; self.capacity=max_events
        self._latest={}; self._scopes={}; self._events=[]; self._signals=[]

    def observe(self,snapshot,*,symbol,observed_at,data_source,implementation_version):
        if (symbol not in ('XAUUSD','USDJPY') or not _finite(observed_at) or observed_at<0
                or any(not isinstance(x,str) or not x.strip() or len(x)>200
                       for x in (data_source,implementation_version))):
            raise ValueError('Explicit observation scope and clock required')
        # Freeze caller data and reject nonfinite JSON before journal mutation.
        snap=loads(_bytes(snapshot))
        if (not isinstance(snap,dict) or snap.get('execution_allowed') is not False
                or snap.get('market_edge_verified') is not False):
            raise ValueError('Read-only HalfTrend snapshot required')
        if snap.get('status')=='DISABLED':
            if snap.get('rows')!=[] or snap.get('signals')!=[]: raise ValueError('Invalid disabled snapshot')
            return dict(status='DISABLED',events=[],signal_events=[],execution_allowed=False)
        if (snap.get('status') not in ('HALFTREND_RESEARCH_ONLY','INSUFFICIENT_HISTORY')
                or type(snap.get('amplitude')) is not int or snap['amplitude'] not in (2,4,6,8)
                or type(snap.get('channel_deviation')) is not int or not 0<=snap['channel_deviation']<=100
                or snap.get('atr_period')!=100 or snap.get('interval') not in (300,900)
                or not _hex(snap.get('source_revision'),40) or not _hex(snap.get('source_sha256'),64)
                or not _hex(snap.get('input_sha256'),64)):
            raise ValueError('Supported HalfTrend source and configuration required')
        rows=snap.get('rows')
        if not isinstance(rows,list) or len(rows)>10000: raise ValueError('Bounded rows required')
        if not rows:
            return dict(status='WAIT_NO_HISTORY',events=[],signal_events=[],execution_allowed=False)
        allowed=set(); calendar_identity=None
        calendar_keys={'calendar_evidence','calendar_sha256','calendar_audit'}
        if calendar_keys & snap.keys():
            if not calendar_keys<=snap.keys(): raise ValueError('Complete calendar evidence required')
            if not all(isinstance(row,dict) for row in rows): raise ValueError('Observation rows required')
            audit=audit_close_times([row.get('at') for row in rows],as_of=observed_at,interval=snap['interval'],
                symbol=symbol,data_source=data_source,evidence=snap['calendar_evidence'],
                expected_evidence_sha256=snap['calendar_sha256'])
            if audit['status']!='SESSION_CLOCK_MATCHED_RESEARCH' or _bytes(audit)!=_bytes(snap['calendar_audit']):
                raise ValueError('Calendar clock audit mismatch')
            allowed={(g['previous_close'],g['next_close']) for g in audit['permitted_gaps']}
            calendar_identity=audit['calendar_identity_sha256']
        if (not all(isinstance(r,dict) for r in rows) or snap.get('history_start')!=rows[0].get('at')
                or snap.get('last_closed_at')!=rows[-1].get('at')):
            raise ValueError('History anchor mismatch')
        prior=None
        for index,row in enumerate(rows):
            if (set(row)!={'at','state','line','atr','atr_high','atr_low','signal',
                           'signal_known_at','signal_close','ready','internal_transition'}
                    or not _finite(row.get('at')) or not 0<=row['at']<=observed_at
                    or (prior is not None and row['at']-prior!=snap['interval'] and (prior,row['at']) not in allowed)
                    or row.get('state') not in ('UP','DOWN') or not _finite(row.get('line')) or row['line']<=0
                    or type(row.get('ready')) is not bool or type(row.get('internal_transition')) is not bool):
                raise ValueError('Invalid, future or non-contiguous closed observation')
            prior=row['at']; atr=row.get('atr'); signal=row.get('signal')
            if row['ready'] is not (index>=99) or (atr is None)!=(index<99):
                raise ValueError('HalfTrend ATR warmup disagrees with history')
            if (signal is not None)!=(row['ready'] and row['internal_transition']):
                raise ValueError('Published signal disagrees with confirmed transition')
            if atr is None:
                if row.get('atr_high') is not None or row.get('atr_low') is not None or row['ready']:
                    raise ValueError('ATR warmup must remain unknown')
            else:
                width=snap['channel_deviation']*atr/2 if _finite(atr) else None
                if (not _finite(atr) or atr<0 or any(not _finite(row.get(k)) for k in ('atr_high','atr_low'))
                        or not isclose(row['atr_high'],row['line']+width,rel_tol=1e-10,abs_tol=1e-10)
                        or not isclose(row['atr_low'],row['line']-width,rel_tol=1e-10,abs_tol=1e-10)):
                    raise ValueError('Invalid ATR channel')
            if signal is None:
                if row.get('signal_known_at') is not None or row.get('signal_close') is not None:
                    raise ValueError('Missing signal cannot carry a signal clock/price')
            elif (signal not in ('BUY','SELL') or not row['ready'] or not row['internal_transition']
                    or row.get('signal_known_at')!=row['at'] or not _finite(row.get('signal_close'))
                    or row['signal_close']<=0 or (signal=='BUY')!=(row['state']=='UP')):
                raise ValueError('Unconfirmed or inconsistent signal')
        if _bytes(snap.get('signals'))!=_bytes([r for r in rows if r['signal'] is not None]):
            raise ValueError('Signal list disagrees with row history')
        config={k:snap[k] for k in ('amplitude','channel_deviation','atr_period','interval',
                                    'source_revision','source_sha256','history_start')}
        config.update(data_source=data_source,implementation_version=implementation_version)
        if calendar_identity is not None: config['session_calendar_identity']=calendar_identity
        revision=sha256(_bytes(config)).hexdigest()
        timeframe='M5' if snap['interval']==300 else 'M15'
        scope=(symbol,timeframe,revision)
        old_scope=self._scopes.get(scope)
        if old_scope and (observed_at<old_scope['observed_at'] or snap['last_closed_at']<old_scope['last_closed_at']):
            raise ValueError('Observation clock or history end regressed')
        pending=[]
        for row in rows:
            key=(*scope,row['at']); fingerprint=sha256(_bytes(row)).hexdigest()
            old=self._latest.get(key)
            if old is None or old['fingerprint']!=fingerprint: pending.append((key,row,fingerprint,old))
        if len(self._events)+len(pending)>self.capacity:
            raise ValueError('Observation capacity reached; persist before starting another session')
        new_events=[]; new_signals=[]
        for key,row,fingerprint,old in pending:
            signal_event=None
            if row['ready']:
                signal_event=self.journal.observe(symbol=symbol,timeframe=timeframe,closed_at=row['at'],
                    observed_at=observed_at,signal=row['signal'] or 'NONE',
                    source='HALFTREND05:'+data_source,revision_id=revision)
                self._signals.append(dict(signal_event)); new_signals.append(dict(signal_event))
            event=dict(symbol=symbol,timeframe=timeframe,closed_at=row['at'],observed_at=observed_at,
                revision_id=revision,configuration=config,values=dict(row),
                changed_after_observation=old is not None,
                previous_values=None if old is None else old['values'],
                input_sha256=snap['input_sha256'],execution_allowed=False)
            if calendar_identity is not None: event['calendar_sha256']=snap['calendar_sha256']
            self._events.append(event); new_events.append(event)
            self._latest[key]=dict(fingerprint=fingerprint,values=dict(row))
        self._scopes[scope]=dict(observed_at=observed_at,last_closed_at=snap['last_closed_at'])
        return loads(_bytes(dict(status='HALFTREND_OBSERVATION_ONLY',events=new_events,
            signal_events=new_signals,unchanged_rows=len(rows)-len(pending),revision_id=revision,
            observed_at=observed_at,last_closed_at=snap['last_closed_at'],
            nonrepainting_verified=False,market_edge_verified=False,execution_allowed=False)))

    def report(self):
        return loads(_bytes(dict(status='HALFTREND_OBSERVATIONS_ONLY',events=self._events,
            signal_events=self._signals,value_revision_count=sum(e['changed_after_observation'] for e in self._events),
            signal_revision_count=sum(e['changed_after_observation'] for e in self._signals),
            last_seen_scopes=[dict(symbol=k[0],timeframe=k[1],revision_id=k[2],**v)
                              for k,v in sorted(self._scopes.items())],
            nonrepainting_verified=False,market_edge_verified=False,execution_allowed=False)))
