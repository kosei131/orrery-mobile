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
