"""TradingView closed OHLC -> existing LSR02/VHF03 plans and optional tick accounts.
No inferred ticks, TradingView login, Pine strategy equivalence or live orders.
"""
import argparse
import csv
from datetime import datetime
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from io import StringIO
from math import isfinite
from pathlib import Path
from lsr04_tick_archive import _encode,_decode,_pin,_write_exclusive
from lsr03_account_study import build_account_plans,compare_catalog_accounts

INTERVALS={'M5':300,'M15':900,'H4':14400}
CONFIG={'symbol','data_source','chart_type','price_basis','time_format','column_map','as_of_s','strategy'}
STRATEGY={'buffer','target_r','period','min_vhf','left','right','lifetime'}


def _number(cell):
    if not isinstance(cell,str) or not 0<len(cell)<=100 or cell!=cell.strip():raise ValueError('Bounded decimal cell required')
    try:v=Decimal(cell)
    except InvalidOperation:raise ValueError('Invalid decimal') from None
    if not v.is_finite() or abs(v)>Decimal('1e12'):raise ValueError('Invalid numeric range')
    return v


def normalize(raw, *, timeframe, settings):
    if not isinstance(raw,bytes) or len(raw)>32*1024*1024:raise ValueError('Bounded CSV bytes required')
    interval=INTERVALS[timeframe];columns=settings['column_map'];asof=settings['as_of_s']
    reader=csv.reader(StringIO(raw.decode('utf-8-sig'),newline=''),strict=True)
    headers=next(reader,None)
    if (not headers or len(headers)>128 or len(set(headers))!=len(headers)
            or any(not h or len(h)>200 for h in headers) or not set(columns.values())<=set(headers)):
        raise ValueError('Missing or duplicate CSV headers')
    positions={k:headers.index(v) for k,v in columns.items()}
    bars=[];gaps=[];previous=None;deferred=0;raw_rows=0;segments=[];segment_rows=0
    for cells in reader:
        raw_rows+=1
        if raw_rows>200000 or len(cells)!=len(headers) or deferred:raise ValueError('Ragged/excessive CSV or row after unfinished bar')
        row={k:cells[v] for k,v in positions.items()}
        if settings['time_format']=='UNIX_SECONDS':
            n=_number(row['time'])
            if n!=n.to_integral_value():raise ValueError('Whole UTC seconds required')
            at=int(n)
        else:
            t=datetime.fromisoformat(row['time'].replace('Z','+00:00'))
            if t.tzinfo is None or t.microsecond:raise ValueError('Explicit timezone and whole seconds required')
            at=int(t.timestamp())
        if at<0 or at>asof or (previous is not None and (at<=previous or (at-previous)%interval)):
            raise ValueError('Future, unordered or inconsistent timeframe clocks')
        prices={k:float(_number(row[k])) for k in ('open','high','low','close')}
        if not 0<prices['low']<=min(prices['open'],prices['close'])<=max(prices['open'],prices['close'])<=prices['high']:
            raise ValueError('Invalid OHLC')
        prior=previous
        previous=at
        if at+interval>asof:deferred+=1;continue
        if prior is not None and at-prior>interval:
            gaps.append(dict(after_open=prior,before_open=at,missing_grid_bars=(at-prior)//interval-1))
            segments.append(segment_rows);segment_rows=0
        segment_rows+=1
        bars.append(dict(close_time=at+interval,**prices))
    if not bars:raise ValueError('Confirmed history required')
    segments.append(segment_rows)
    return bars,dict(raw_sha256=sha256(raw).hexdigest(),confirmed_rows=len(bars),
        deferred_unconfirmed_rows=deferred,first_close_s=bars[0]['close_time'],last_close_s=bars[-1]['close_time'],
        first_open_s=bars[0]['close_time']-interval,contiguous_segment_count=len(segments),
        longest_contiguous_rows=max(segments),
        gap_count=len(gaps),missing_grid_bars=sum(x['missing_grid_bars'] for x in gaps),gap_examples=gaps[:20])


def _readiness(audit):
    """Report every import blocker without equating range overlap with usable history."""
    start=max(a['first_open_s'] for a in audit.values())
    end=min(a['last_close_s'] for a in audit.values())
    overlap=start<end
    blockers=[]
    for frame,a in audit.items():
        if a['gap_count']:blockers.append(dict(timeframe=frame,reason='SESSION_OR_HISTORY_GAPS',count=a['gap_count']))
        if a['confirmed_rows']>2000:blockers.append(dict(timeframe=frame,reason='REPLAY_WORK_BUDGET',rows=a['confirmed_rows'],limit=2000))
    if not overlap:blockers.append(dict(timeframe=None,reason='NO_SHARED_TIME_RANGE'))
    return dict(shared_range_start_s=start if overlap else None,shared_range_end_s=end if overlap else None,
        shared_range_seconds=end-start if overlap else 0,shared_range_is_gap_free_verified=False,
        strategy_warmup_verified=False,blockers=blockers)


def study(raw_csvs, settings, *, account_inputs=None):
    if not isinstance(settings,dict) or set(settings)!=CONFIG:raise ValueError('Exact TradingView study settings required')
    if (settings['symbol'] not in ('XAUUSD','USDJPY') or settings['chart_type']!='STANDARD'
            or settings['price_basis'] not in ('BID','ASK','MID','LAST','UNKNOWN')
            or settings['time_format'] not in ('UNIX_SECONDS','ISO8601')
            or type(settings['as_of_s']) is not int or settings['as_of_s']<=0
            or not isinstance(settings['data_source'],str) or not 0<len(settings['data_source'])<=200):
        raise ValueError('Explicit symbol/feed/standard chart/UTC clock required')
    columns=settings['column_map']
    if (not isinstance(columns,dict) or set(columns)!={'time','open','high','low','close'}
            or any(not isinstance(v,str) or not 0<len(v)<=200 for v in columns.values()) or len(set(columns.values()))!=5):
        raise ValueError('Explicit unique OHLC columns required')
    st=settings['strategy']
    if not isinstance(st,dict) or set(st)!=STRATEGY:raise ValueError('Explicit current strategy parameters required')
    if (any(type(st[k]) is not int or not 1<=st[k]<=100 for k in ('left','right'))
            or type(st['period']) is not int or not 2<=st['period']<=100
            or any(type(st[k]) not in (int,float) or not isfinite(st[k]) or st[k]<=0 for k in ('buffer','target_r','lifetime'))
            or type(st['min_vhf']) not in (int,float) or not isfinite(st['min_vhf']) or not 0<=st['min_vhf']<=1):
        raise ValueError('Invalid strategy parameters')
    if not isinstance(raw_csvs,dict) or set(raw_csvs)!=set(INTERVALS):raise ValueError('M5 M15 H4 exports required')
    bars={};audit={}
    for frame in INTERVALS:bars[frame],audit[frame]=normalize(raw_csvs[frame],timeframe=frame,settings=settings)
    readiness=_readiness(audit)
    base=dict(symbol=settings['symbol'],data_source=settings['data_source'],audit=audit,import_readiness=readiness,
        settings_sha256=sha256(_encode(settings)).hexdigest(),initial_equity_usd=3000,
        strategy_scope='EXISTING_LSR02_AND_VHF03_RETEST_STRUCTURAL_SL_FIXED_TARGET_R',
        excluded_modules=['REVERSAL04','HALFTREND05','UNDEFINED_2_6'],
        imported_chart_standardness_verified=False,bar_provenance_verified=False,
        historical_broker_costs_verified=False,market_edge_verified=False,execution_allowed=False,
        modelled_accounts=None,modelled_account_summary=None,verified_profit_usd=None,
        six_month_backtest_complete=False)
    # Existing structure engine forbids gaps. Do not bridge weekends or missing bars.
    if any(a['gap_count'] for a in audit.values()):return dict(base,status='BLOCKED_SESSION_OR_HISTORY_GAPS',plans=None)
    if any(len(b)>2000 for b in bars.values()):return dict(base,status='BLOCKED_REPLAY_WORK_BUDGET',plans=None)
    if readiness['shared_range_seconds']==0:return dict(base,status='BLOCKED_NO_SHARED_TIME_RANGE',plans=None)
    args=dict(h4=bars['H4'],m15=bars['M15'],m5=bars['M5'],as_of=settings['as_of_s'],**st)
    compiled=build_account_plans(settings['symbol'],**args)
    if account_inputs is None:return dict(base,status='STRATEGY_PLANS_READY_BID_ASK_AND_VALUATION_REQUIRED',plans=compiled)
    if (not isinstance(account_inputs,dict) or {'h4','m15','m5','as_of','bar_source','buffer','target_r','period','min_vhf','left','right','lifetime','entry_delay_msc','max_candidates','daily_boundary_utc_hour'} & account_inputs.keys()):
        raise ValueError('Account input cannot override pinned bars or strategy')
    account=compare_catalog_accounts(bar_source=settings['data_source'],**args,**account_inputs)
    summaries=None
    if account['accounts'] is not None:
        summaries={name:{k:a[k] for k in ('initial_equity_usd','ending_balance_usd','ending_equity_usd',
            'balance_change_usd','equity_change_usd','closed_trade_net_usd','max_sampled_equity_drawdown_usd',
            'max_consecutive_losses','closed_statistics','open_position')} for name,a in account['accounts'].items()}
    return dict(base,status='TRADINGVIEW_BARS_ACCOUNT_MODEL_RESEARCH' if summaries is not None else account['status'],
        plans=compiled,modelled_accounts=account,modelled_account_summary=summaries)


def _code_pins():
    root=Path(__file__).resolve().parent
    names=(Path(__file__).name,'lsr03_account_study.py','lsr03_adapter.py','lsr02_replay.py','lsr03_account_replay.py')
    return {name:sha256((root/name).read_text(encoding='utf-8').encode()).hexdigest() for name in names}


def prepare(paths,settings_path,output):
    def read(path,limit):
        p=Path(path)
        if p.is_symlink() or not p.is_file():raise ValueError('Regular input file required')
        with p.open('rb') as stream:data=stream.read(limit+1)
        if len(data)>limit:raise ValueError('Input exceeds read budget')
        return data
    raw={frame:read(paths[frame],32*1024*1024) for frame in INTERVALS}
    config_raw=read(settings_path,65536);settings=_decode(config_raw)
    result=study(raw,settings)
    files={frame+'.csv':value for frame,value in raw.items()}
    files.update({'settings.json':config_raw,'study.json':_encode(result)})
    receipt=_encode(dict(files={name:sha256(data).hexdigest() for name,data in files.items()},code_sha256=_code_pins()))
    root=Path(output);root.mkdir()
    for name,data in files.items():_write_exclusive(root/name,data)
    _write_exclusive(root/'complete.json',receipt)
    return dict(status=result['status'],receipt_sha256=sha256(receipt).hexdigest(),execution_allowed=False)


def verify(folder,expected_receipt_sha256):
    _pin(expected_receipt_sha256);root=Path(folder)
    expected={'M5.csv','M15.csv','H4.csv','settings.json','study.json','complete.json'}
    if root.is_symlink() or not root.is_dir() or {p.name for p in root.iterdir()}!=expected:raise ValueError('Incomplete or unexpected study files')
    raw={}
    for name in expected:
        p=root/name
        if p.is_symlink() or not p.is_file() or p.stat().st_size>32*1024*1024:raise ValueError('Bounded regular study file required')
        raw[name]=p.read_bytes()
    if sha256(raw['complete.json']).hexdigest()!=expected_receipt_sha256:raise ValueError('Receipt changed')
    receipt=_decode(raw['complete.json'])
    if receipt!={'files':{n:sha256(raw[n]).hexdigest() for n in expected-{'complete.json'}},'code_sha256':_code_pins()}:
        raise ValueError('Study input or implementation changed')
    result=study({f:raw[f+'.csv'] for f in INTERVALS},_decode(raw['settings.json']))
    if _encode(result)!=raw['study.json']:raise ValueError('Study recomputation differs')
    return dict(status=result['status'],recomputed=True,execution_allowed=False)


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
    run=sub.add_parser('run')
    for name in ('m5','m15','h4','settings','output'):run.add_argument('--'+name,required=True)
    check=sub.add_parser('verify');check.add_argument('--folder',required=True);check.add_argument('--receipt-sha256',required=True)
    a=p.parse_args(argv)
    result=(prepare({f:getattr(a,f.lower()) for f in INTERVALS},a.settings,a.output) if a.command=='run'
            else verify(a.folder,a.receipt_sha256))
    print(_encode(result).decode(),end='');return 0

if __name__=='__main__':raise SystemExit(main())
