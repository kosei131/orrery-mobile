"""Pin-bound H4 interruption evidence requests. No repair, price fill or orders."""
import csv
from datetime import datetime,timedelta,timezone
from hashlib import sha256
import json
from math import isfinite
from pathlib import Path
from orrery_m1_complete_bars import calendar_minutes
from orrery_real_bars_lsr_bridge import load
from orrery_tradingview_window_replay import _groups


def _read(path,pin,limit):
    path=Path(path)
    if (not isinstance(pin,str) or len(pin)!=64 or any(c not in '0123456789abcdef' for c in pin)
            or path.is_symlink() or not path.is_file() or path.stat().st_size>limit):
        raise ValueError('Bounded regular pinned source required')
    raw=path.read_bytes()
    if sha256(raw).hexdigest()!=pin:raise ValueError('Input pin mismatch')
    return raw


def _iso(stamp):return datetime.fromtimestamp(stamp,timezone.utc).isoformat()


def requests(normalized,h4,calendar_path,*,normalized_sha256,h4_sha256,calendar_sha256,
             start,end,published_at):
    for v in (start,end,published_at):
        if type(v) not in (int,float) or not isfinite(v) or v<0:
            raise ValueError('Explicit finite UTC horizon required')
    if start%14400 or end%14400 or not published_at<=start<end or end-start>366*86400:
        raise ValueError('Post-publication bounded H4 horizon required')
    _read(normalized,normalized_sha256,100_000_000)
    _read(h4,h4_sha256,10_000_000)
    calendar=json.loads(_read(calendar_path,calendar_sha256,10_000_000))
    expected=calendar_minutes(calendar,240)
    first=datetime.fromisoformat(calendar['intervals'][0]['start_utc']).timestamp()
    last=datetime.fromisoformat(calendar['intervals'][-1]['end_utc']).timestamp()
    if not first<=start<end<=last:raise ValueError('Calendar does not cover study horizon')
    observed=set();previous=None
    with Path(normalized).open(encoding='utf-8-sig',newline='') as stream:
        for row in csv.DictReader(stream):
            at=datetime.fromisoformat(row['timestamp_utc'].replace('Z','+00:00'))
            if at.utcoffset()!=timedelta(0) or at.second or at.microsecond:
                raise ValueError('UTC minute source required')
            stamp=int(at.timestamp())
            if previous is not None and stamp<=previous:raise ValueError('Ordered unique minutes required')
            observed.add(stamp);previous=stamp
            if len(observed)>500000:raise ValueError('M1 row budget exceeded')
    if not observed:raise ValueError('Nonempty M1 source required')
    bars=[b for b in load(h4,'H4')['bars'] if start<=b['open_time'] and b['close_time']<=end]
    present={b['open_time'] for b in bars}
    first_observed=min(observed);last_observed=max(observed)
    missing_by_slot={}
    edge_slots=[]
    # Require generated H4 availability to match the same pinned M1/calendar.
    for slot in range(int(start),int(end),14400):
        wanted=expected.get(slot,[])
        missing=sorted(set(wanted)-observed)
        if (slot in present)!=(bool(wanted) and not missing):
            raise ValueError('H4 availability does not reconcile with pinned M1/calendar')
        missing_by_slot[slot]=missing
        if missing and (min(wanted)<first_observed or max(wanted)>last_observed):
            edge_slots.append(slot)
    boundary_slots=[dict(open_utc=_iso(s),unexplained_open_minutes=len(missing))
        for s,missing in missing_by_slot.items() if missing and
        (not present or s<min(present) or s>max(present))]
    groups=_groups(bars,14400);rows=[]
    for left,right in zip(groups,groups[1:]):
        a=left[-1]['open_time']+14400;b=right[0]['open_time']
        slots=list(range(a,b,14400))
        closed=[s for s in slots if not expected.get(s)]
        unknown=sorted(t for s in slots for t in missing_by_slot[s])
        intervals=[]
        for t in unknown:
            if not intervals or intervals[-1]['end_s']!=t:
                intervals.append(dict(start_s=t,end_s=t+60))
            else:intervals[-1]['end_s']=t+60
        intervals=[dict(start_utc=_iso(x['start_s']),end_utc_exclusive=_iso(x['end_s'])) for x in intervals]
        eligible=bool(unknown) and not closed and not any(s in edge_slots for s in slots)
        rows.append(dict(gap_start_utc=_iso(a),gap_end_utc_exclusive=_iso(b),
            absent_h4_slots=len(slots),weekly_closed_h4_slots=len(closed),
            unexplained_open_minutes=len(unknown),missing_open_intervals=intervals,
            prior_contiguous_h4_bars=len(left),following_contiguous_h4_bars=len(right),
            adjacent_observed_h4_bars=len(left)+len(right),
            source_edge_truncation=any(s in edge_slots for s in slots),
            review_class='M1_OR_EXCEPTION_EVIDENCE_NEEDED' if eligible else 'CALENDAR_OR_EDGE_REVIEW_ONLY',
            quote_retrieval_priority_eligible=eligible,calendar_authenticated=False,
            continuity_restoration_claimed=False))
    rows.sort(key=lambda r:(not r['quote_retrieval_priority_eligible'],
        -r['adjacent_observed_h4_bars'],r['unexplained_open_minutes'],r['gap_start_utc']))
    for i,r in enumerate(rows,1):r['evidence_review_rank']=i
    # Recheck exact bytes; an intake plan cannot silently pin another version.
    _read(normalized,normalized_sha256,100_000_000);_read(h4,h4_sha256,10_000_000)
    return dict(status='H4_INTERRUPTION_EVIDENCE_PRIORITY_ONLY',start_open_utc=_iso(start),
        end_close_utc=_iso(end),rows=rows,interruption_count=len(rows),
        quote_evidence_targets=sum(r['quote_retrieval_priority_eligible'] for r in rows),
        source_edge_slots=[_iso(s) for s in edge_slots],
        study_boundary_open_slots=boundary_slots,
        all_absent_expected_open_h4_slots=sum(bool(v) for v in missing_by_slot.values()),
        ranking_basis='ELIGIBLE_THEN_OBSERVED_ADJACENT_BARS_DESC_THEN_MISSING_MINUTES_ASC',
        input_sha256=dict(normalized=normalized_sha256,h4=h4_sha256,calendar=calendar_sha256),
        skipped_market_closures_filled=False,history_acquired=False,
        continuity_restored=False,profit_improvement_estimated=False,
        actual_profit_usd=None,execution_allowed=False)
