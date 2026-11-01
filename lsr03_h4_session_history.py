# SPDX-License-Identifier: GPL-3.0-only
"""Opt-in H4 clock selection using pinned, pre-known explicit sessions.

No OHLC synthesis, regime classification or broker-calendar certification.
"""
from lsr05_session_clock import audit_close_times


def select_history(times, *, as_of, minimum_bars, symbol, data_source,
                   evidence, expected_evidence_sha256):
    if type(minimum_bars) is not int or not 3<=minimum_bars<=10000:
        raise ValueError('Bounded explicit H4 lookback required')
    audit=audit_close_times(times,as_of=as_of,interval=14400,symbol=symbol,
        data_source=data_source,evidence=evidence,
        expected_evidence_sha256=expected_evidence_sha256)
    complete=audit['status']=='SESSION_CLOCK_MATCHED_RESEARCH'
    end=audit['horizon_end']
    # A calendar stopping before the candidate cannot authorize the remaining
    # unobserved time. Permit only the current incomplete UTC H4 slot.
    current=end<=as_of<end+14400
    status=('BLOCKED_SESSION_HISTORY' if not complete else
            'BLOCKED_CALENDAR_HORIZON' if not current else
            'INSUFFICIENT_SESSION_HISTORY' if len(times)<minimum_bars else
            'H4_SESSION_CLOCK_SELECTION_ONLY')
    selected=times[-minimum_bars:] if status=='H4_SESSION_CLOCK_SELECTION_ONLY' else []
    return dict(status=status,selected_close_times=selected,
        minimum_bars_required=minimum_bars,
        minimum_additional_bars=max(0,minimum_bars-len(times)) if complete else None,
        calendar_audit=audit,ohlc_verified=False,regime_evaluated=False,
        broker_calendar_verified=False,execution_allowed=False)


def inspect_prices(bars, *, as_of, minimum_bars, symbol, data_source,
                   evidence, expected_evidence_sha256):
    """Preserve reopening gaps; reset structural references at session gaps.

    Selection is opt-in. Structure remains segmented, not a new trading rule.
    """
    from math import isfinite
    from lsr02_structure import detect
    if not isinstance(bars,list) or len(bars)>10000:
        raise ValueError('Bounded explicit OHLC history required')
    for b in bars:
        if not isinstance(b,dict) or any(type(b.get(k)) not in (int,float)
                or not isfinite(b[k]) for k in ('open','high','low','close','close_time')):
            raise ValueError('Finite OHLC and closing time required')
        if not 0<b['low']<=min(b['open'],b['close'])<=max(b['open'],b['close'])<=b['high']:
            raise ValueError('Invalid OHLC range')
    selection=select_history([b['close_time'] for b in bars],as_of=as_of,
        minimum_bars=minimum_bars,symbol=symbol,data_source=data_source,
        evidence=evidence,expected_evidence_sha256=expected_evidence_sha256)
    rows=[]; segments=[]
    if selection['status']=='H4_SESSION_CLOCK_SELECTION_ONLY':
        first=len(bars)-minimum_bars
        for i in range(first,len(bars)):
            b=bars[i]; previous=bars[i-1] if i else None
            gap=previous is not None and b['close_time']-previous['close_time']>14400
            tr=max(b['high']-b['low'],abs(b['high']-previous['close']),
                   abs(b['low']-previous['close'])) if previous else b['high']-b['low']
            if not isfinite(tr): raise ValueError('True range overflow')
            rows.append(dict(close_time=b['close_time'],true_range=tr,
                previous_close=previous['close'] if previous else None,
                opening_price_gap=b['open']-previous['close'] if previous else None,
                follows_session_gap=gap))
            if not segments or gap: segments.append([])
            segments[-1].append(dict(b))
    structures=[dict(first_close=s[0]['close_time'],last_close=s[-1]['close_time'],
                     bars=len(s),structure=detect(s,as_of=as_of,interval=14400))
                for s in segments]
    return dict(status='H4_SESSION_PRICE_DIAGNOSTIC_ONLY' if rows else selection['status'],
        selection=selection,rows=rows,segmented_structure=structures,
        structure_references_reset_at_gaps=True,ohlc_range_checked=True,
        ohlc_source_verified=False,market_edge_verified=False,
        regime_evaluated=False,execution_allowed=False)
