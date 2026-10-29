# SPDX-License-Identifier: GPL-3.0-only
"""Audit bar closing clocks against explicitly pinned session evidence.

Reuses calendar_minutes; no weekly/weekend inference or manufactured OHLC.
Caller-declared schedule evidence is not authenticated broker history.
"""
from hashlib import sha256
from json import dumps, loads
from math import isfinite
from orrery_m1_complete_bars import calendar_minutes
from lsr04_tick_quality import _time


def _bytes(value):
    return dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()


def evidence_sha256(evidence): return sha256(_bytes(evidence)).hexdigest()


def audit_close_times(times, *, as_of, interval, symbol, data_source,
                      evidence, expected_evidence_sha256):
    if (type(interval) is not int or interval not in (300,900)
            or symbol not in ('XAUUSD','USDJPY') or not isinstance(data_source,str) or not data_source.strip()
            or type(as_of) not in (int,float) or not isfinite(as_of) or as_of<0
            or not isinstance(times,list) or len(times)>10000):
        raise ValueError('Explicit bounded bar clock and feed required')
    if (not isinstance(expected_evidence_sha256,str) or len(expected_evidence_sha256)!=64
            or any(c not in '0123456789abcdef' for c in expected_evidence_sha256)):
        raise ValueError('Retained calendar evidence pin required')
    source=loads(_bytes(evidence))
    keys={'symbol','data_source','known_at_utc','source_document_sha256','calendar'}
    if not isinstance(source,dict) or set(source)!=keys or evidence_sha256(source)!=expected_evidence_sha256:
        raise ValueError('Calendar evidence mismatch')
    document=source['source_document_sha256']
    if (source['symbol']!=symbol or source['data_source']!=data_source
            or not isinstance(document,str) or len(document)!=64
            or any(c not in '0123456789abcdef' for c in document)):
        raise ValueError('Calendar is for another symbol/feed or lacks document pin')
    calendar=source['calendar']
    if (not isinstance(calendar,dict) or set(calendar)!={'source','intervals'}
            or not isinstance(calendar['source'],str) or not calendar['source'].strip()
            or len(calendar['source'])>400 or not isinstance(calendar['intervals'],list)
            or not 1<=len(calendar['intervals'])<=10000):
        raise ValueError('Bounded documented calendar required')
    expected=calendar_minutes(calendar,interval//60)
    start=_time(calendar['intervals'][0]['start_utc'])/1000
    end=_time(calendar['intervals'][-1]['end_utc'])/1000
    known=_time(source['known_at_utc'])/1000
    if known>start or end>as_of:
        raise ValueError('Calendar must be known before its horizon; no future horizon')
    previous=None
    for at in times:
        if (type(at) not in (int,float) or not isfinite(at) or at<0 or at>as_of
                or at%interval or (previous is not None and at<=previous)):
            raise ValueError('Ordered UTC-grid confirmed closing clocks required')
        previous=at
    expected_times={opened+interval for opened in expected}
    actual=set(times); missing=sorted(expected_times-actual); extra=sorted(actual-expected_times)
    matched=not missing and not extra
    gaps=[dict(previous_close=a,next_close=b,skipped_bar_slots=int((b-a)//interval)-1)
          for a,b in zip(times,times[1:]) if b-a>interval] if matched else []
    identity={k:source[k] for k in ('symbol','data_source','known_at_utc','source_document_sha256')}
    identity['calendar_source']=calendar['source']
    identity['horizon_start']=start
    return dict(status='SESSION_CLOCK_MATCHED_RESEARCH' if matched else 'BLOCKED_SESSION_HISTORY',
        symbol=symbol,data_source=data_source,evidence_sha256=expected_evidence_sha256,
        calendar_identity_sha256=sha256(_bytes(identity)).hexdigest(),
        horizon_start=start,horizon_end=end,expected_open_bars=len(expected_times),observed_bars=len(times),
        missing_open_bars=len(missing),unexpected_bar_closes=len(extra),
        missing_examples=missing[:100],unexpected_examples=extra[:100],permitted_gaps=gaps,
        closed_bar_slots=int((end-start)//interval)-len(expected_times),
        session_partial_bar_slots=sum(len(minutes)<interval//60 for minutes in expected.values()),
        calendar_broker_verified=False,ohlc_completeness_verified=False,
        market_edge_verified=False,execution_allowed=False)
