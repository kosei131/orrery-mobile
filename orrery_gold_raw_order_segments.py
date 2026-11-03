# SPDX-License-Identifier: GPL-3.0-only
"""Bounded raw-order clock segment audit; no price bars, sorting or fill assumptions."""
import argparse
from datetime import datetime,timezone,timedelta
from hashlib import sha256
import json
from pathlib import Path
import re
import stat
import zipfile

from orrery_histdata_tick_audit import clock, price

MAX_BYTES=384*1024*1024
MAX_RECORDS=8_000_000
MAX_SEGMENTS=100_000


def analyze(source, *, expected_sha256, month, now):
    source=Path(source)
    if source.is_symlink() or not source.is_file():
        raise ValueError('Regular input required')
    if not re.fullmatch(r'20\d{4}',month) or not re.fullmatch(r'[a-f0-9]{64}',expected_sha256):
        raise ValueError('Pinned source month and SHA256 required')
    datetime.strptime(month,'%Y%m')
    if not isinstance(now,datetime) or now.utcoffset()!=timedelta(0):
        raise ValueError('UTC review clock required')
    if source.stat().st_size>32*1024*1024 or sha256(source.read_bytes()).hexdigest()!=expected_sha256:
        raise ValueError('Original ZIP bound/hash mismatch')
    member='DAT_ASCII_XAUUSD_T_'+month+'.csv'
    segments=[];prev=None;first=None;count=0;tied=0;reversals=0;gaps=0;raw_hash=sha256();total_bytes=0
    current=None
    def flush():
        if current is not None:
            segments.append(current.copy())
            if len(segments)>MAX_SEGMENTS:
                raise ValueError('Too many unverified segments')
    with zipfile.ZipFile(source) as z:
        infos=z.infolist()
        if not 1<=len(infos)<=4 or len({i.filename for i in infos})!=len(infos):
            raise ValueError('Unique bounded ZIP members required')
        for i in infos:
            if ('/' in i.filename or '\\' in i.filename or i.is_dir()
                or i.flag_bits&1 or stat.S_ISLNK(i.external_attr>>16)
                or not i.filename.endswith(('.csv','.txt'))):
                raise ValueError('Unsafe ZIP member')
            if i.filename.endswith('.txt') and i.file_size>1024*1024:
                raise ValueError('Metadata limit')
        entries=[i for i in infos if i.filename.endswith('.csv')]
        if len(entries)!=1 or entries[0].filename!=member or entries[0].file_size>MAX_BYTES:
            raise ValueError('Exact bounded Gold source CSV required')
        if sum(i.file_size for i in infos)>MAX_BYTES:
            raise ValueError('Expanded limit')
        with z.open(member) as stream:
            while True:
                line=stream.readline(129)
                if not line:break
                if len(line)>128:raise ValueError('Bounded tick line')
                count+=1;total_bytes+=len(line);raw_hash.update(line)
                if count>MAX_RECORDS or total_bytes>MAX_BYTES:
                    raise ValueError('Bounded raw rows')
                fields=line.rstrip(b'\r\n').split(b',')
                if len(fields)!=4:raise ValueError('Four tick fields expected')
                t=clock(fields[0],month);b=price(fields[1]);a=price(fields[2])
                if b>a or t>=int(now.timestamp()*1000):
                    raise ValueError('Invalid historic quote')
                # A row-order reversal or an unobserved 60+ second interval
                # closes the current segment. Neither is silently repaired.
                reversal=prev is not None and t<prev
                discontinuity=prev is not None and t-prev>60000
                if reversal or discontinuity:
                    flush()
                    reversals+=int(reversal);gaps+=int(discontinuity)
                    current=None
                if current is None:
                    current=dict(first_row=count,first_utc_ms=t,last_row=count,last_utc_ms=t,
                                 quotes=0,same_second_pairs=0)
                current['quotes']+=1;current['last_row']=count;current['last_utc_ms']=t
                if prev is not None and not reversal and not discontinuity and t==prev:
                    tied+=1;current['same_second_pairs']+=1
                prev=t
        if total_bytes!=entries[0].file_size:raise ValueError('Expanded byte mismatch')
    if not count:raise ValueError('Empty source')
    flush()
    if sha256(source.read_bytes()).hexdigest()!=expected_sha256:
        raise ValueError('Source changed during audit')
    # Segment duration is an upper-bound clock span, NOT proof of every observed
    # second/minute or a valid broker execution timeline.
    spans=[(s['last_utc_ms']-s['first_utc_ms'])//1000 for s in segments]
    ranked=sorted(segments,key=lambda s:(-s['quotes'],s['first_row']))[:10]
    distribution=dict(
        one_quote_segments=sum(s['quotes']==1 for s in segments),
        segments_with_same_second_pairs=sum(s['same_second_pairs']>0 for s in segments),
        spans_at_least_5m=sum(v>=300 for v in spans),
        spans_at_least_15m=sum(v>=900 for v in spans),
        spans_at_least_4h=sum(v>=14400 for v in spans),
        longest_clock_span_seconds=max(spans,default=0),
        largest_segments_by_quotes=ranked,
        span_thresholds_are_not_data_completeness=True,
        segment_chronology_is_not_broker_certified=True)
    return dict(status='RAW_ORDER_SEGMENT_DIAGNOSTIC_ONLY',
        source_zip_sha256=expected_sha256,source_csv_sha256=raw_hash.hexdigest(),
        source_ticks=count,segments=len(segments),clock_reversal_pairs=reversals,
        gaps_over_60s=gaps,same_second_adjacent_pairs=tied,
        segment_inventory=segments,distribution=distribution,raw_order_preserved=True,quotes_reordered=False,
        bid_ask_bar_exported=False,verified_execution_chronology=False,
        valid_broker_backtest=False,actual_profit_usd=None,
        execution_allowed=False)


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',required=True)
    p.add_argument('--source-sha256',required=True)
    p.add_argument('--month',required=True)
    p.add_argument('--output',required=True)
    a=p.parse_args(argv);out=Path(a.output)
    if out.exists() or out.is_symlink():
        p.error('Output must not already exist')
    report=analyze(a.source,expected_sha256=a.source_sha256,month=a.month,now=datetime.now(timezone.utc))
    with out.open('x',encoding='utf-8') as f:
        json.dump(report,f,ensure_ascii=False,indent=2,allow_nan=False)
    print(json.dumps({k:report[k] for k in ('source_ticks','segments','clock_reversal_pairs',
                                            'gaps_over_60s')},ensure_ascii=False))

if __name__=='__main__':
    main()
