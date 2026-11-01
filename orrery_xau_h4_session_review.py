# SPDX-License-Identifier: GPL-3.0-only
"""Replay pinned public H4 diagnostics only after calendar publication."""
import hashlib,json,math
from pathlib import Path
from lsr04_tick_quality import _time
from lsr05_session_clock import evidence_sha256
from lsr03_h4_session_history import inspect_prices
from orrery_real_bars_lsr_bridge import load


def review(bars, candidates, calendar, *, published_at, document_sha256):
    start=math.ceil(_time(published_at)/1000/14400)*14400
    rows=[]
    for c in candidates:
        at=c['first_poi_touch_close']; end=at//14400*14400
        if end<=start:
            rows.append(dict(at=at,status='BLOCKED_CALENDAR_NOT_PREKNOWN'));continue
        intervals=[]
        from datetime import datetime,timezone
        def iso(t):return datetime.fromtimestamp(t,timezone.utc).isoformat()
        for part in calendar['intervals']:
            a=max(start,_time(part['start_utc'])/1000);b=min(end,_time(part['end_utc'])/1000)
            if a<b:intervals.append(dict(start_utc=iso(a),end_utc=iso(b),state=part['state']))
        if not intervals or _time(intervals[0]['start_utc'])/1000!=start or _time(intervals[-1]['end_utc'])/1000!=end:
            rows.append(dict(at=at,status='BLOCKED_CALENDAR_COVERAGE'));continue
        evidence=dict(symbol='XAUUSD',data_source='PUBLIC_WEEKLY_UNVERIFIED',
            known_at_utc=published_at,source_document_sha256=document_sha256,
            calendar=dict(source=calendar['source'],intervals=intervals))
        result=inspect_prices([b for b in bars if start<b['close_time']<=end],
            as_of=at,minimum_bars=12,symbol='XAUUSD',data_source='PUBLIC_WEEKLY_UNVERIFIED',
            evidence=evidence,expected_evidence_sha256=evidence_sha256(evidence))
        rows.append(dict(at=at,status=result['status'],diagnostic=result))
    return dict(status='PUBLIC_H4_SESSION_REVIEW_ONLY',rows=rows,
        broker_verified=False,out_of_sample=False,execution_allowed=False)


def run(root=Path('.')):
    folder=root/'public_xau_session_coverage'
    raw=(folder/'report.json').read_bytes(); report=json.loads(raw)
    path=folder/'H4_WEEKLY_SCHEDULE_UNVERIFIED.csv'
    calpath=folder/'weekly_calendar_hypothesis.json'
    def pin(p):return hashlib.sha256(p.read_bytes()).hexdigest()
    calendar=json.loads(calpath.read_text())
    calendar_pin=hashlib.sha256(json.dumps(calendar,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    if pin(path)!=report['h4_file_sha256'] or calendar_pin!=report['h4_aggregation']['calendar_sha256']:
        raise ValueError('H4 or calendar changed since source audit')
    calendar=json.loads(calpath.read_text())
    # The exporter pins canonical calendar JSON rather than file bytes.
    candidates=json.loads((root/'public_xau_sequence_report.json').read_text())['retouch_evidence']
    from orrery_xau_h4_alignment import START,END
    candidates=[c for c in candidates if START<=c['first_poi_touch_close']<END]
    result=review(load(path,'H4')['bars'],candidates,calendar,
        published_at=report['published_report_utc'],document_sha256=hashlib.sha256(raw).hexdigest())
    result['source_audit_sha256']=hashlib.sha256(raw).hexdigest()
    (root/'public_xau_h4_session_review.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'status':result['status'],'statuses':[r['status'] for r in result['rows']],
                      'execution_allowed':False}))
    return result

if __name__=='__main__':run()
