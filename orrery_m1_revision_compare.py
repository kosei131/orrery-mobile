"""Compare pinned GetData M1 revisions without repairing, merging or trading."""
import argparse
import csv
from datetime import datetime,timedelta,timezone
from decimal import Decimal
from hashlib import sha256
import io
import json
from pathlib import Path

PREFIX='https://raw.githubusercontent.com/getdata-finance/xauusd-1m-ohlcv-metals-historical-data/'


def _raw(path,pin,limit=100_000_000):
    p=Path(path)
    if (not isinstance(pin,str) or len(pin)!=64 or any(c not in '0123456789abcdef' for c in pin)
            or p.is_symlink() or not p.is_file() or p.stat().st_size>limit):
        raise ValueError('Bounded pinned file required')
    raw=p.read_bytes()
    if sha256(raw).hexdigest()!=pin:raise ValueError('File pin mismatch')
    return raw


def _clock(value):
    t=datetime.fromisoformat(value.replace('Z','+00:00'))
    if t.utcoffset()!=timedelta(0) or t.second or t.microsecond:
        raise ValueError('Explicit UTC minute clock required')
    return int(t.timestamp())


def _rows(raw):
    rows={};previous=None
    reader=csv.DictReader(io.StringIO(raw.decode('utf-8-sig')))
    fields=reader.fieldnames or []
    if (len(fields)!=len(set(fields)) or
            not {'datetime','open','high','low','close'}.issubset(fields)):
        raise ValueError('Explicit original M1 schema required')
    for row in reader:
        at=_clock(row['datetime'])
        if previous is not None and at<=previous:raise ValueError('Ordered unique M1 required')
        values=tuple(Decimal(row[k]) for k in ('open','high','low','close'))
        o,h,l,c=values
        if not all(v.is_finite() for v in values) or not 0<l<=min(o,c)<=max(o,c)<=h:
            raise ValueError('Finite valid OHLC required')
        volume=Decimal(row['volume']) if 'volume' in fields else None
        if volume is not None and (not volume.is_finite() or volume<0):raise ValueError('Invalid volume')
        rows[at]=values+(volume,);previous=at
        if len(rows)>500000:raise ValueError('M1 row budget exceeded')
    if not rows or max(rows)-min(rows)>366*86400:raise ValueError('Bounded nonempty M1 horizon required')
    return rows


def compare(original,candidate,*,original_sha256,candidate_sha256,candidate_revision,
            candidate_url,target_intervals):
    if (not isinstance(candidate_revision,str) or len(candidate_revision)!=40
            or any(c not in '0123456789abcdef' for c in candidate_revision)
            or candidate_url!=PREFIX+candidate_revision+'/XAUUSD_1m.csv'):
        raise ValueError('Exact retained provider revision URL required')
    a=_raw(original,original_sha256);b=_raw(candidate,candidate_sha256)
    left=_rows(a);right=left if a==b else _rows(b)
    if not isinstance(target_intervals,list) or not 1<=len(target_intervals)<=1000:
        raise ValueError('Bounded explicit missing-minute requests required')
    targets=set()
    for interval in target_intervals:
        start=_clock(interval['start_utc']);end=_clock(interval['end_utc_exclusive'])
        if not min(left)<start<end<=max(left)+60 or end-start>10000*60:
            raise ValueError('Requests must be inside original observed horizon')
        minutes=set(range(start,end,60))
        if targets&minutes or minutes&left.keys():raise ValueError('Requests overlap or were already observed')
        targets.update(minutes)
        if len(targets)>10000:raise ValueError('Requested minute budget exceeded')
    common=left.keys()&right.keys();changed=[];volume_changes=0
    for at in sorted(common):
        if left[at][:4]!=right[at][:4]:changed.append(at)
        volume_changes+=left[at][4]!=right[at][4]
    def iso(t):return datetime.fromtimestamp(t,timezone.utc).isoformat()
    added=sorted(targets&right.keys());missing=sorted(targets-right.keys())
    return dict(status='PINNED_M1_REVISION_COMPARISON_ONLY',candidate_revision=candidate_revision,
        candidate_url=candidate_url,original_sha256=original_sha256,candidate_sha256=candidate_sha256,
        byte_identical=a==b,original_rows=len(left),candidate_rows=len(right),
        overlapping_rows=len(common),changed_overlap_ohlc_rows=len(changed),
        changed_overlap_volume_rows=volume_changes,changed_overlap_examples_utc=[iso(t) for t in changed[:20]],
        added_rows=len(right.keys()-left.keys()),removed_rows=len(left.keys()-right.keys()),
        requested_minutes=len(targets),requested_minutes_present=len(added),
        requested_minutes_still_absent=len(missing),present_requested_utc=[iso(t) for t in added],
        absent_requested_utc=[iso(t) for t in missing],
        no_update_or_missing_cause='UNRESOLVED',source_identity_authenticated=False,
        repaired_history_accepted=False,history_merged=False,continuity_restored=False,
        actual_profit_usd=None,execution_allowed=False)


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('original','candidate','targets','output'):p.add_argument('--'+name,required=True,type=Path)
    for name in ('original-sha256','candidate-sha256','targets-sha256','candidate-revision','candidate-url'):
        p.add_argument('--'+name,required=True)
    a=p.parse_args(argv)
    plan=json.loads(_raw(a.targets,a.targets_sha256,1_000_000))
    if plan['original_source_sha256']!=a.original_sha256:raise ValueError('Request plan is for another source')
    targets=[i for row in plan['rows'] if row['quote_retrieval_priority_eligible']
             for i in row['missing_open_intervals']]
    r=compare(a.original,a.candidate,original_sha256=a.original_sha256,candidate_sha256=a.candidate_sha256,
        candidate_revision=a.candidate_revision,candidate_url=a.candidate_url,target_intervals=targets)
    r['targets_sha256']=a.targets_sha256
    with a.output.open('x',encoding='utf-8') as f:json.dump(r,f,indent=2,allow_nan=False);f.write('\n')
    print(json.dumps({k:r[k] for k in ('byte_identical','changed_overlap_ohlc_rows','requested_minutes','requested_minutes_present','requested_minutes_still_absent')}))
    return 0

if __name__=='__main__':raise SystemExit(main())
