# SPDX-License-Identifier: GPL-3.0-only
"""Bounded, byte-preserving Gold ZIP partitioning and existing diagnostic audits."""
from collections import Counter
from datetime import datetime,timezone
from hashlib import sha256
import json,math,stat,zipfile
from pathlib import Path
from tempfile import TemporaryDirectory
import orrery_histdata_tick_audit as tick

MAX_TOTAL=384*1024*1024
MAX_ROWS=8_000_000
CHUNK_BYTES=48*1024*1024
CHUNK_ROWS=1_500_000


def run(source,out,*,expected_sha256,month,now):
    source=Path(source);out=Path(out)
    if out.exists():raise FileExistsError('New output directory required')
    if not out.parent.exists():raise ValueError('Existing output parent required')
    datetime.strptime(month,'%Y%m')
    if now.utcoffset()!=tick.timedelta(0):raise ValueError('UTC audit clock required')
    if source.stat().st_size>tick.MAX_ZIP:raise ValueError('Original compressed limit exceeded')
    if sha256(source.read_bytes()).hexdigest()!=expected_sha256:raise ValueError('Original ZIP hash mismatch')
    member=f'DAT_ASCII_XAUUSD_T_{month}.csv';spreads=Counter();hours={h:Counter() for h in range(24)};minutes=set()
    n=used=rev=tied=subsec=backstep=0;first=last=prev=None;digest=sha256();chunk_receipts=[]
    with TemporaryDirectory(dir=out.parent) as temp:
        temp=Path(temp);buffer=bytearray();chunk_n=0;paths=[]
        def flush():
            nonlocal chunk_n
            if not buffer:return
            p=temp/f'chunk_{len(paths):03d}.zip'
            with zipfile.ZipFile(p,'x',zipfile.ZIP_DEFLATED) as z:z.writestr(member,buffer)
            paths.append(p);chunk_receipts.append(dict(path=p.name,rows=chunk_n,csv_bytes=len(buffer),zip_sha256=sha256(p.read_bytes()).hexdigest()))
            buffer.clear();chunk_n=0
        with zipfile.ZipFile(source) as z:
            infos=z.infolist();files=[i for i in infos if i.filename.endswith('.csv')]
            if not 1<=len(infos)<=4 or len({i.filename for i in infos})!=len(infos):raise ValueError('Unique bounded members required')
            if len(files)!=1 or files[0].filename!=member:raise ValueError('Exact single Gold source month required')
            for i in infos:
                if '/' in i.filename or '\\' in i.filename or i.is_dir() or i.flag_bits&1 or stat.S_ISLNK(i.external_attr>>16):raise ValueError('Flat regular members required')
                if not i.filename.endswith(('.csv','.txt')) or i.file_size>MAX_TOTAL:raise ValueError('Unexpected member/budget')
                if i.filename.endswith('.txt') and i.file_size>1024*1024:raise ValueError('Metadata budget exceeded')
            if sum(i.file_size for i in infos)>MAX_TOTAL:raise ValueError('Original expanded budget exceeded')
            with z.open(files[0]) as f:
                while True:
                    line=f.readline(129)
                    if not line:break
                    if len(line)>128:raise ValueError('Tick line budget exceeded')
                    if buffer and (len(buffer)+len(line)>CHUNK_BYTES or chunk_n>=CHUNK_ROWS):flush()
                    n+=1;used+=len(line)
                    if n>MAX_ROWS or used>MAX_TOTAL:raise ValueError('Original total row/byte budget exceeded')
                    fields=line.rstrip(b'\r\n').split(b',')
                    if len(fields)!=4:raise ValueError('Tick schema required')
                    t=tick.clock(fields[0],month);b=tick.price(fields[1]);a=tick.price(fields[2]);v=float(fields[3])
                    if a<b or not math.isfinite(v) or v<0 or t>=int(now.timestamp()*1000):raise ValueError('Observed valid historical quote required')
                    if prev is not None:
                        rev+=t<prev;tied+=t==prev;backstep=max(backstep,prev-t)
                    prev=t;first=t if first is None else min(first,t);last=t if last is None else max(last,t)
                    subsec+=t%1000!=0;minutes.add(t//60000*60000);spreads[a-b]+=1;hours[(t//3600000)%24][a-b]+=1
                    digest.update(line);buffer.extend(line);chunk_n+=1
            if not n or used!=files[0].file_size:raise ValueError('Original expanded byte count mismatch')
            text_hashes={i.filename:sha256(z.read(i)).hexdigest() for i in infos if i.filename.endswith('.txt')}
        flush();reconstructed=sha256();parts=[]
        for p,receipt in zip(paths,chunk_receipts):
            r=tick.audit(p,temp/(p.stem+'_audit'),expected_sha256=receipt['zip_sha256'],symbol='XAUUSD',month=month,now=now,mode='DIAGNOSTIC_ONLY')
            if r['ticks']!=receipt['rows'] or r['source_csv_bytes']!=receipt['csv_bytes'] or r['output_sha256']:
                raise ValueError('Chunk accounting or isolation mismatch')
            with zipfile.ZipFile(p) as z:
                with z.open(member) as f:
                    while raw:=f.read(1024*1024):reconstructed.update(raw)
            parts.append(dict(**receipt,ticks=r['ticks'],out_of_order_pairs=r['out_of_order_pairs'],
                              same_timestamp_adjacent_pairs=r['same_timestamp_adjacent_pairs'],
                              first_tick_utc=r['first_tick_utc'],last_tick_utc=r['last_tick_utc'],
                              source_csv_sha256=r['source_csv_sha256'],chronological_bar_exported=r['chronological_bar_exported']))
            print(f'Diagnostic chunk {len(parts)}/{len(paths)}: {r["ticks"]} quotes',flush=True)
        if reconstructed.hexdigest()!=digest.hexdigest() or sum(p['ticks'] for p in parts)!=n:
            raise ValueError('Byte-exact reconstruction failed')
        if sha256(source.read_bytes()).hexdigest()!=expected_sha256:raise ValueError('Original changed during audit')
        stamps=sorted(minutes);gaps=[dict(first_missing_msc=a+60000,reopen_msc=z,missing_minutes=(z-a)//60000-1) for a,z in zip(stamps,stamps[1:]) if z-a>60000]
        iso=lambda t:datetime.fromtimestamp(t/1000,timezone.utc).isoformat()
        coverage={}
        for label,size in (('M1',1),('M5',5),('M15',15),('H4',240)):
            groups=Counter(t//(size*60000) for t in stamps)
            coverage[label]=dict(observed_complete_slots=sum(n==size for n in groups.values()),partial_slots=sum(n!=size for n in groups.values()))
        report=dict(status='GOLD_CHUNKED_DIAGNOSTIC_NO_BAR_EXPORT',symbol='XAUUSD',source_month_fixed_est=month,
            original_zip_sha256=expected_sha256,original_csv_sha256=digest.hexdigest(),original_csv_bytes=used,
            reconstructed_csv_sha256=reconstructed.hexdigest(),byte_exact_reconstruction_verified=True,
            ticks=n,chunk_count=len(parts),chunks=parts,chunk_csv_byte_limit=CHUNK_BYTES,chunk_row_limit=CHUNK_ROWS,
            first_tick_utc=iso(first),last_tick_utc=iso(last),out_of_order_pairs=rev,maximum_backward_step_msc=backstep,
            same_timestamp_adjacent_pairs=tied,subsecond_nonzero_ticks=subsec,observed_whole_second_timestamps_only=subsec==0,
            paired_m1_minutes=len(minutes),missing_internal_minutes=sum(g['missing_minutes'] for g in gaps),minute_gaps=gaps,
            source_text_sha256=text_hashes,observed_slot_coverage=coverage,
            synchronous_tick_spread_price=dict(min=min(spreads)/tick.UNIT,median=tick.quantile(spreads,.5),p95=tick.quantile(spreads,.95),
                                               max=max(spreads)/tick.UNIT,mean=sum(p*c for p,c in spreads.items())/n/tick.UNIT),
            spread_by_declared_utc_hour={str(h):dict(ticks=sum(v.values()),median=tick.quantile(v,.5),p95=tick.quantile(v,.95),max=max(v)/tick.UNIT) for h,v in hours.items() if v},
            engine_code_sha256={p.name:sha256(p.read_bytes()).hexdigest() for p in (Path(__file__),Path(tick.__file__))},
            chronological_bar_exported=False,strategy_replay_allowed=False,raw_ticks_reordered=False,
            source_authenticity_verified=False,market_session_completeness_verified=False,execution_allowed=False,
            win_rate_pct=None,net_expectancy_r=None,account_return_pct=None,account_max_dd_usd=None,
            limitations=['Source month and UTC use publisher fixed EST declaration, not independently authenticated clock.',
                        'Partition boundaries are processing boundaries, not market/session boundaries.',
                        'Whole-second ties and reversals remain; no ordering repair or TP/SL replay.',
                        'Observed quote spreads are tick weighted and not guaranteed execution costs.'])
        (temp/'audit.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n',encoding='utf-8')
        temp.rename(out)
    return report


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('out',type=Path)
    p.add_argument('--sha256',required=True);p.add_argument('--month',required=True)
    a=p.parse_args();r=run(a.source,a.out,expected_sha256=a.sha256,month=a.month,now=datetime.now(timezone.utc))
    print(json.dumps({k:v for k,v in r.items() if k not in ('minute_gaps','chunks','spread_by_declared_utc_hour')}))
