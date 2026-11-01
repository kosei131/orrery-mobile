"""Strict normalized OHLC CSV ingestion. Read-only, no account/market connection.
Every input is USER_PROVIDED_UNVERIFIED, never authenticated market data.
"""
import csv
import hashlib
import io
import re
from datetime import datetime
from pathlib import Path
from lsr02_structure import detect
from lsr02_sequence import number
from lsr02_replay import replay

INTERVALS={'4H':14400,'15m':900,'5m':300}
FIELDS=['symbol','timeframe','source_id','close_time_utc','open','high','low','close']


def load_csv(path, *, symbol, timeframe, as_of):
    if symbol not in ('XAUUSD','USDJPY') or timeframe not in INTERVALS or not number(as_of):
        raise ValueError('Invalid dataset request')
    with Path(path).open('rb') as f:raw=f.read(1024*1024+1)
    if len(raw)>1024*1024:raise ValueError('CSV exceeds 1 MiB limit')
    try:
        reader=csv.DictReader(io.StringIO(raw.decode('utf-8-sig'),newline=''))
        if reader.fieldnames!=FIELDS:raise ValueError('Normalized CSV columns required')
        bars=[];source=None;interval=INTERVALS[timeframe]
        for row in reader:
            if len(bars)>=1000:raise ValueError('Split data into smaller research segments')
            if set(row)!=set(FIELDS) or any(v is None for v in row.values()):raise ValueError('Malformed row')
            if row['symbol']!=symbol or row['timeframe']!=timeframe:raise ValueError('Mixed symbol/timeframe')
            if not re.fullmatch(r'[A-Za-z0-9_.-]{1,64}',row['source_id']):raise ValueError('Invalid source identifier')
            if source is not None and source!=row['source_id']:raise ValueError('Mixed sources')
            source=row['source_id']
            stamp=row['close_time_utc']
            if not re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z',stamp):raise ValueError('Explicit UTC close time required')
            t=datetime.fromisoformat(stamp.replace('Z','+00:00')).timestamp()
            if t%interval:raise ValueError('UTC grid alignment required; do not infer broker timezone')
            bars.append(dict(close_time=t,**{k:float(row[k]) for k in ('open','high','low','close')}))
        if not bars:raise ValueError('Empty dataset')
        detect(bars,as_of=as_of,interval=interval)
        return dict(status='USER_PROVIDED_UNVERIFIED',source_id=source,sha256=hashlib.sha256(raw).hexdigest(),bars=bars)
    except (UnicodeError,ValueError,csv.Error,OverflowError) as exc:
        # Do not include raw input values or file paths in validation errors.
        raise ValueError('CSV rejected: verify normalized columns, UTC closes, OHLC and continuity') from None


def replay_csv(paths, *, symbol, as_of, buffer, regime_config, halt_store=None):
    if set(paths)!=set(INTERVALS):raise ValueError('4H, 15m and 5m files required')
    datasets={tf:load_csv(paths[tf],symbol=symbol,timeframe=tf,as_of=as_of) for tf in INTERVALS}
    if len({d['source_id'] for d in datasets.values()})!=1:raise ValueError('Sources must match across timeframes')
    trace=replay(symbol,datasets['4H']['bars'],datasets['15m']['bars'],datasets['5m']['bars'],
                 as_of=as_of,buffer=buffer,regime_config=regime_config,halt_store=halt_store)
    return dict(status='USER_PROVIDED_UNVERIFIED',execution_allowed=False,
                input_hashes={tf:d['sha256'] for tf,d in datasets.items()},trace=trace)
