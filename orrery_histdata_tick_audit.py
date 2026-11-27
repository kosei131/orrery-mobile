# SPDX-License-Identifier: GPL-3.0-only
"""Pinned HistData ASCII tick ZIP -> observed paired UTC bars, no filled gaps."""
from collections import Counter
from datetime import datetime,timedelta,timezone
from hashlib import sha256
import csv,json,math,re,stat,zipfile
from pathlib import Path
from tempfile import TemporaryDirectory

UNIT=100_000_000
EST=timezone(timedelta(hours=-5))
MAX_ZIP=32*1024*1024
MAX_CSV=256*1024*1024
MAX_TICKS=5_000_000
NAME=re.compile(r'DAT_ASCII_(USDJPY|XAUUSD)_T_(20\d{4})\.csv')


def price(raw):
    s=raw.decode('ascii')
    if not re.fullmatch(r'\d{1,8}(?:\.\d{1,8})?',s):raise ValueError('Positive decimal price required')
    whole,_,frac=s.partition('.');n=int(whole)*UNIT+int(frac.ljust(8,'0'))
    if n<=0:raise ValueError('Positive price required')
    return n


def clock(raw,month):
    s=raw.decode('ascii')
    if not re.fullmatch(r'\d{8} \d{9}',s) or s[:6]!=month:raise ValueError('Exact source-month millisecond clock required')
    d=datetime(int(s[:4]),int(s[4:6]),int(s[6:8]),int(s[9:11]),int(s[11:13]),int(s[13:15]),int(s[15:18])*1000,tzinfo=EST)
    elapsed=d-datetime(1970,1,1,tzinfo=timezone.utc)
    return elapsed.days*86400000+elapsed.seconds*1000+elapsed.microseconds//1000


def quantile(hist,q):
    target=max(1,math.ceil(sum(hist.values())*q));n=0
    for value,count in sorted(hist.items()):
        n+=count
        if n>=target:return value/UNIT


def write_bars(path,rows):
    with path.open('x',newline='',encoding='utf-8') as f:
        w=csv.writer(f,lineterminator='\n');w.writerow(('timestamp','open','high','low','close'))
        for t,b in rows:w.writerow((t,*(v/UNIT for v in b)))


def aggregate(minutes,size):
    groups={}
    for t,b in sorted(minutes.items()):groups.setdefault(t//(size*60000)*(size*60000),[]).append((t,b))
    out=[]
    for t,rows in sorted(groups.items()):
        if [x[0] for x in rows]!=list(range(t,t+size*60000,60000)):continue
        out.append((t,[rows[0][1][0],max(x[1][1] for x in rows),min(x[1][2] for x in rows),rows[-1][1][3]]))
    return out,len(groups)-len(out)


def audit(source,out,*,expected_sha256,symbol,month,now,mode='STRICT_ORDER'):
    source=Path(source);out=Path(out)
    if symbol not in ('USDJPY','XAUUSD') or not re.fullmatch(r'20\d{4}',month):raise ValueError('Supported symbol and source month required')
    datetime.strptime(month,'%Y%m')
    if mode not in ('STRICT_ORDER','DIAGNOSTIC_ONLY'):raise ValueError('Explicit audit mode required')
    if not isinstance(now,datetime) or now.utcoffset()!=timedelta(0):raise ValueError('Explicit UTC audit clock required')
    if not re.fullmatch(r'[a-f0-9]{64}',expected_sha256):raise ValueError('Explicit SHA256 required')
    if out.exists():raise FileExistsError('New output directory required')
    if source.stat().st_size>MAX_ZIP:raise ValueError('Compressed budget exceeded')
    if sha256(source.read_bytes()).hexdigest()!=expected_sha256:raise ValueError('Source hash mismatch')
    bid={};ask={};spread=Counter();prev=None;previous=None;ticks=sameclock=identical=zero_volume=0;long_gaps=[]
    raw_hash=sha256();byte_count=0;now_ms=int(now.timestamp()*1000);first=last=None
    backwards=0;backstep=0;bad_examples=[];subsecond=0
    hourly={h:Counter() for h in range(24)};cross_minute_reversals=0
    with zipfile.ZipFile(source) as z:
        infos=z.infolist()
        if not 1<=len(infos)<=4 or len({i.filename for i in infos})!=len(infos):raise ValueError('Bounded unique members required')
        for i in infos:
            if ('/' in i.filename or '\\' in i.filename or i.is_dir() or i.flag_bits&1 or stat.S_ISLNK(i.external_attr>>16)):
                raise ValueError('Flat regular unencrypted members required')
            if i.file_size>MAX_CSV or not i.filename.endswith(('.csv','.txt')):raise ValueError('Unexpected member or expanded size')
            if i.filename.endswith('.txt') and i.file_size>1024*1024:raise ValueError('Text metadata budget exceeded')
        if sum(i.file_size for i in infos)>MAX_CSV:raise ValueError('Expanded archive budget exceeded')
        files=[i for i in infos if i.filename.endswith('.csv')]
        if len(files)!=1 or files[0].filename!=f'DAT_ASCII_{symbol}_T_{month}.csv':raise ValueError('Exact single symbol/month tick CSV required')
        with z.open(files[0]) as f:
            while True:
                line=f.readline(129)
                if not line:break
                byte_count+=len(line);ticks+=1
                if len(line)>128 or byte_count>MAX_CSV or ticks>MAX_TICKS:raise ValueError('CSV/line/row budget exceeded')
                raw_hash.update(line);fields=line.rstrip(b'\r\n').split(b',')
                if len(fields)!=4:raise ValueError('Four comma-delimited tick columns required')
                t=clock(fields[0],month);b=price(fields[1]);a=price(fields[2]);v=float(fields[3])
                if a<b or not math.isfinite(v) or v<0:raise ValueError('Noncrossed quote and finite nonnegative volume required')
                if t>=now_ms:raise ValueError('Observed historical ticks required')
                if prev is not None and t<prev:
                    if mode=='STRICT_ORDER':raise ValueError('Observed ordered historical ticks required')
                    backwards+=1;backstep=max(backstep,prev-t)
                    cross_minute_reversals+=prev//60000!=t//60000
                    if len(bad_examples)<20:bad_examples.append(dict(row=ticks,previous_msc=prev,current_msc=t))
                if prev is not None:
                    sameclock+=t==prev
                    if t-prev>60000:long_gaps.append((t-prev,prev,t))
                same=(t,b,a,fields[3]);identical+=same==previous;previous=same;prev=t
                first=t if first is None else min(first,t);last=t if last is None else max(last,t);subsecond+=t%1000!=0
                zero_volume+=v==0;spread[a-b]+=1;minute=t//60000*60000
                hourly[(t//3600000)%24][a-b]+=1
                for dest,p in ((bid,b),(ask,a)):
                    if minute not in dest:dest[minute]=[p,p,p,p]
                    else:
                        dest[minute][1]=max(dest[minute][1],p);dest[minute][2]=min(dest[minute][2],p);dest[minute][3]=p
        if not ticks:raise ValueError('Empty tick CSV')
        if byte_count!=files[0].file_size:raise ValueError('Expanded byte count mismatch')
        member=files[0].filename
        text_receipts={i.filename:sha256(z.read(i)).hexdigest() for i in infos if i.filename.endswith('.txt')}
    if sha256(source.read_bytes()).hexdigest()!=expected_sha256:raise ValueError('Source changed during audit')
    stamps=sorted(bid);gaps=[dict(first_missing_msc=a+60000,reopen_msc=z,missing_minutes=(z-a)//60000-1) for a,z in zip(stamps,stamps[1:]) if z-a>60000]
    iso=lambda t:datetime.fromtimestamp(t/1000,timezone.utc).isoformat()
    r=dict(status='DIAGNOSTIC_ONLY_BAR_EXPORT_BLOCKED' if mode=='DIAGNOSTIC_ONLY' else 'OBSERVED_PAIRED_TICKS_AUDITED_NOT_SESSION_CERTIFIED',
        audit_mode=mode,chronological_bar_exported=mode=='STRICT_ORDER',strategy_replay_allowed=False,
        out_of_order_pairs=backwards,maximum_backward_step_msc=backstep,order_violation_examples=bad_examples,
        cross_minute_order_reversals=cross_minute_reversals,
        subsecond_nonzero_ticks=subsecond,observed_whole_second_timestamps_only=subsecond==0,
        symbol=symbol,source_month_fixed_est=month,
        source_zip_sha256=expected_sha256,source_csv_member=member,source_csv_sha256=raw_hash.hexdigest(),source_csv_bytes=byte_count,
        timestamp_rule='HistData fixed EST UTC-05:00 without DST; add five hours to UTC',
        first_tick_utc=iso(first),last_tick_utc=iso(last),ticks=ticks,same_timestamp_adjacent_pairs=sameclock,
        consecutive_identical_records=identical,zero_volume_ticks=zero_volume,
        paired_m1_minutes=len(stamps),minute_gaps=gaps,missing_internal_minutes=sum(g['missing_minutes'] for g in gaps),
        positive_file_order_tick_gaps_over_60s=len(long_gaps),maximum_positive_file_order_tick_gap_seconds=max((g[0]/1000 for g in long_gaps),default=0),
        largest_positive_file_order_tick_gaps=[dict(seconds=d/1000,after_utc=iso(a),before_utc=iso(z)) for d,a,z in sorted(long_gaps,reverse=True)[:20]],
        synchronous_tick_spread_price=dict(min=min(spread)/UNIT,median=quantile(spread,.5),p95=quantile(spread,.95),max=max(spread)/UNIT,
                                          mean=sum(v*n for v,n in spread.items())/ticks/UNIT,zero_spread_ticks=spread[0]),
        spread_by_declared_utc_hour={str(h):dict(ticks=sum(v.values()),median=quantile(v,.5),p95=quantile(v,.95),max=max(v)/UNIT)
                                     for h,v in hourly.items() if v},
        source_text_sha256=text_receipts,code_sha256=sha256(Path(__file__).read_bytes()).hexdigest(),
        source_authenticity_verified=False,market_session_completeness_verified=False,missing_minutes_filled=False,
        source_is_user_mt5=False,execution_allowed=False,adopted=False,win_rate_pct=None,
        net_expectancy_r=None,account_return_pct=None,account_max_dd_usd=None,
        limitations=['Quotes in supplied public archive, not proof of complete broker ticks or actual fills.',
                    'Observed M1 slots only; tick count/zero volume do not certify traded volume.',
                    'Diagnostic mode counts clock reversals without sorting, deleting ticks or exporting OHLC bars.',
                    'Millisecond format does not establish subsecond time precision or quote ordering within ties.',
                    'Source month uses fixed EST; UTC boundaries can differ from calendar UTC month.',
                    'No market closure guessed; all internal minute gaps retained.',
                    'Higher bars require every nominal M1 slot, not certified session coverage.',
                    'No strategy, commissions, swaps, further slippage, lot/margin or account return evaluated.'])
    if not out.parent.exists():raise ValueError('Existing output parent required')
    with TemporaryDirectory(dir=out.parent) as tmp:
        tmp=Path(tmp);files={};bars={}
        for side,minutes in (('bid',bid),('ask',ask)):
            for label,size in (('M1',1),('M5',5),('M15',15),('H4',240)):
                rows,incomplete=aggregate(minutes,size);name=f'{side}_{label}.csv'
                if mode=='STRICT_ORDER':
                    write_bars(tmp/name,rows);files[name]=sha256((tmp/name).read_bytes()).hexdigest()
                bars[side+'_'+label]=dict(observed_complete_slot_bars=len(rows),rejected_partial_slots=incomplete)
        r.update(output_sha256=files,aggregations=bars)
        (tmp/'audit.json').write_text(json.dumps(r,indent=2,allow_nan=False)+'\n',encoding='utf-8')
        tmp.rename(out)
    return r


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('out',type=Path)
    p.add_argument('--sha256',required=True);p.add_argument('--symbol',required=True,choices=('USDJPY','XAUUSD'));p.add_argument('--month',required=True)
    p.add_argument('--mode',choices=('STRICT_ORDER','DIAGNOSTIC_ONLY'),default='STRICT_ORDER')
    a=p.parse_args();r=audit(a.source,a.out,expected_sha256=a.sha256,symbol=a.symbol,month=a.month,now=datetime.now(timezone.utc),mode=a.mode)
    print(json.dumps({k:v for k,v in r.items() if k not in ('minute_gaps','largest_tick_gaps')}))
