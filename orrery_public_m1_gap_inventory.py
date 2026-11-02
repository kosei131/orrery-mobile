"""Offline XAUUSD M1 gap inventory; never infer verified market sessions.

Read the original public-OHLC CSV without changing its content. Report missing
one-minute slots and boundaries for independent broker-calendar verification.
No MT5, network, price interpolation, trading or profitability claims.
"""
import argparse
import csv
from datetime import datetime, timedelta, timezone
import json
from collections import Counter
from hashlib import sha256
from orrery_xau_h4_m1_completeness import classify
from pathlib import Path


def inventory(path, *, max_rows=500000, max_gap_details=10000):
    source=Path(path)
    if source.is_symlink() or not source.is_file() or source.stat().st_size>100_000_000:
        raise ValueError('Bounded regular M1 source file required')
    source_pin=sha256(source.read_bytes()).hexdigest()
    buckets=Counter()
    before=None
    gaps=[]
    total=0
    first=None
    last=None
    with source.open('r',encoding='utf-8-sig',newline='') as stream:
        reader=csv.DictReader(stream)
        if not reader.fieldnames or 'datetime' not in reader.fieldnames:
            raise ValueError('Expected explicit UTC datetime column')
        for line in reader:
            stamp=line['datetime']
            if not isinstance(stamp,str):
                raise ValueError('Missing timestamp')
            at=datetime.fromisoformat(stamp.replace('Z','+00:00'))
            if at.utcoffset()!=timedelta(0) or at.second or at.microsecond:
                raise ValueError('Minute-aligned UTC only')
            if before is not None:
                delta=int((at-before).total_seconds())
                if delta<=0 or delta%60:
                    raise ValueError('Strictly increasing M1 timestamps required')
                if delta>60:
                    if len(gaps)>=max_gap_details:
                        raise ValueError('Too many gaps for bounded report')
                    missing=delta//60-1
                    gaps.append(dict(after_utc=before.isoformat(),
                        before_utc=at.isoformat(),missing_minutes=missing,
                        day_of_week_before=before.strftime('%a'),
                        crosses_weekend=(before.weekday()>=5 or at.weekday()>=5
                                        or (at.date()-before.date()).days>=2),
                        session_reason='UNVERIFIED'))
            first=first or at
            if (at-first).total_seconds()>366*86400:
                raise ValueError("Source horizon exceeds one year")
            buckets[int(at.timestamp())//14400*14400]+=1
            last=at
            before=at
            total+=1
            if total>max_rows:
                raise ValueError('Source row limit exceeded')
    if not total:
        raise ValueError('Nonempty M1 source required')
    if sha256(source.read_bytes()).hexdigest()!=source_pin:
        raise ValueError('Source changed during inventory')
    # Inspect every UTC H4 bucket, including completely absent ones. Edge
    # truncation is distinct from interior missing minutes; never fill either.
    details=[]; edges=[]; complete=0
    begin=int(first.timestamp()); finish=int(last.timestamp())+60
    for slot in range(begin//14400*14400, (finish-1)//14400*14400+14400,14400):
        row=dict(missing_h4_open_utc=datetime.fromtimestamp(slot,timezone.utc).isoformat(),
                 observed_m1_bars_in_slot=buckets[slot])
        if slot<begin or slot+14400>finish:
            edges.append(row)
        elif buckets[slot]==240:
            complete+=1
        else:
            details.append(row)
    h4=classify(dict(details=details))
    h4.update(complete_interior_slots=complete, edge_truncated_slots=edges,
        expected_grid='UTC_FIXED_4H', scope='FULLY_OBSERVED_SOURCE_HORIZON_ONLY',
        calendar_authenticated=False, continuity_restored=False)
    return dict(status='PUBLIC_M1_GAP_INVENTORY_RESEARCH_ONLY',
        source_sha256=source_pin,h4_source_completeness=h4,source_rows=total,first_minute_utc=first.isoformat(),
        last_minute_utc=last.isoformat(),gap_count=len(gaps),
        missing_minute_slots=sum(g['missing_minutes'] for g in gaps),
        largest_gap_minutes=max((g['missing_minutes'] for g in gaps),default=0),
        gaps=gaps,calendar_authenticated=False,
        broker_quote_basis_verified=False,continuity_restored=False,
        backtest_ready=False,actual_profit_usd=None,execution_allowed=False)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args(argv)
    if args.output.exists() or args.output.is_symlink() or args.output.resolve()==args.source.resolve():
        parser.error('New separate output file required')
    report=inventory(args.source)
    with args.output.open('x',encoding='utf-8') as stream:
        json.dump(report,stream,ensure_ascii=False,indent=2,allow_nan=False)
    print(json.dumps({k:report[k] for k in ('source_rows','gap_count','missing_minute_slots','largest_gap_minutes')},ensure_ascii=False))
    return 0


if __name__=='__main__':
    raise SystemExit(main())
