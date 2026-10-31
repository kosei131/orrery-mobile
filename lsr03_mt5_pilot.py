"""Windows terminal -> DEMO-only historical pilot -> matched price-R report.

Uses the already logged-in terminal. No login, password, trade or order calls.
run_pilot accepts an initialized MT5 object for testing/injection; main owns
initialize/shutdown. Unknown history/cost assumptions never become real PnL.
"""
import argparse
from datetime import datetime, timezone, timedelta
from hashlib import sha256
from math import isfinite
from pathlib import Path
from lsr04_tick_archive import _decode, _encode, _write_exclusive
from lsr04_tick_quality import _time
from lsr04_mt5_account_sync import _identity
from lsr04_mt5_adaptive import capture_adaptive
from lsr04_tick_catalog import save_tick_catalog
from lsr03_tick_study import study_catalog
from lsr02_structure import detect
from lsr02_mt5_bridge import validate_aggregation

REQUIRED={'symbol','source','h4_start_utc','structure_start_utc','tick_start_utc','end_utc',
          'chunk_seconds','max_ticks','buffer','target_r','round_trip_cost_per_unit',
          'slippage','cost_assumption_source','max_spread_points','max_gap_seconds',
          'period','min_vhf'}


def _config(config, now_utc):
    if not isinstance(config,dict) or set(config)!=REQUIRED:
        raise ValueError('Exact explicit pilot settings required; no cost defaults')
    result=_decode(_encode(config))
    if result['symbol'] not in ('XAUUSD','USDJPY'):
        raise ValueError('Canonical symbol required; suffixes are not guessed')
    for key in ('source','cost_assumption_source'):
        if not isinstance(result[key],str) or not result[key].strip():raise ValueError('Explicit source/cost assumption required')
    for key in ('h4_start_utc','structure_start_utc','tick_start_utc','end_utc'):
        _time(result[key]);result[key]=datetime.fromisoformat(result[key])
        if result[key].microsecond:raise ValueError('Whole-second pilot boundaries required')
    _time(now_utc)
    h,l,s,e=(result[k] for k in ('h4_start_utc','structure_start_utc','tick_start_utc','end_utc'))
    if not h<=l<=s<e<=now_utc or e-s>timedelta(days=1) or e-h>timedelta(days=14):
        raise ValueError('Historical pilot <=1 day, warmup <=14 days required')
    if type(result['chunk_seconds']) is not int or not 60<=result['chunk_seconds']<=3600:
        raise ValueError('Explicit 60-3600 second chunk size required')
    if type(result['max_ticks']) is not int or not 1<=result['max_ticks']<=500000:
        raise ValueError('Pilot <=500000 ticks required')
    if type(result['period']) is not int or not 2<=result['period']<=100:
        raise ValueError('Explicit VHF period required')
    for key in ('buffer','target_r','max_spread_points','max_gap_seconds','round_trip_cost_per_unit','slippage','min_vhf'):
        value=result[key]
        if type(value) not in (int,float) or not isfinite(value):raise ValueError('Finite pilot parameter required')
        if value<0 or (key in ('buffer','target_r','max_spread_points','max_gap_seconds') and value==0):
            raise ValueError('Invalid pilot parameter')
    if not 0<=result['min_vhf']<=1:raise ValueError('Invalid VHF cutoff')
    return result


def _account(mt5):
    account=mt5.account_info()
    demo=getattr(mt5,'ACCOUNT_TRADE_MODE_DEMO',None)
    if account is None or demo is None or getattr(account,'trade_mode',None)!=demo:
        raise ValueError('Broker-reported DEMO required')
    return _identity(account)


def _spec(mt5,symbol):
    info=mt5.symbol_info(symbol)
    if info is None or getattr(info,'name',None)!=symbol:raise ValueError('Exact broker symbol unavailable')
    result=dict(symbol=symbol,point=float(info.point),trade_contract_size=float(info.trade_contract_size),digits=info.digits)
    if any(not isfinite(result[k]) or result[k]<=0 for k in ('point','trade_contract_size')) or type(result['digits']) is not int:
        raise ValueError('Broker specification unavailable')
    return result


def _valuation_spec(mt5,symbol):
    """Optional snapshot; incomplete specs cannot enable account valuation."""
    info=mt5.symbol_info(symbol)
    if info is None:return None
    names=('volume_min','volume_max','volume_step','currency_profit','trade_calc_mode')
    if any(not hasattr(info,k) for k in names):return None
    result={k:getattr(info,k) for k in names}
    for k in ('volume_min','volume_max','volume_step'):
        if type(result[k]) not in (int,float) or not isfinite(result[k]) or result[k]<=0:return None
    if result['volume_min']>result['volume_max'] or not isinstance(result['currency_profit'],str) or not result['currency_profit'] or type(result['trade_calc_mode']) is not int:
        return None
    return dict(_spec(mt5,symbol),**result)


def _scope(identity):
    return sha256(_encode(list(identity))).hexdigest()


def _bars(mt5,symbol,enum,seconds,start,end):
    raw=mt5.copy_rates_range(symbol,enum,start,end)
    if raw is None or not 2<=len(raw)<=10000:raise ValueError('Bounded broker OHLC history required')
    bars=[];excluded=0;previous_open=None
    for row in raw:
        opened=float(row['time'])
        if not isfinite(opened) or not opened.is_integer() or not start.timestamp()<=opened<=end.timestamp():
            raise ValueError('Invalid broker bar opening time')
        if previous_open is not None and opened<=previous_open:raise ValueError('Unordered broker bars')
        previous_open=opened
        close=int(opened)+seconds
        if close>end.timestamp():excluded+=1;continue
        bars.append(dict(close_time=close,**{k:float(row[k]) for k in ('open','high','low','close')}))
    detect(bars,as_of=end.timestamp(),interval=seconds,left=1,right=1)
    if len(bars)<2 or bars[0]['close_time']-seconds-start.timestamp()>=seconds or end.timestamp()-bars[-1]['close_time']>=seconds:
        raise ValueError('Truncated or stale OHLC history; do not invent missing bars')
    return bars,excluded


def run_pilot(mt5,config,output,*,now_utc):
    settings=_config(config,now_utc)
    identity=_account(mt5);symbol=settings['symbol'];spec=_spec(mt5,symbol)
    valuation_spec=_valuation_spec(mt5,symbol)
    root=Path(output);root.mkdir()
    def check():
        if _account(mt5)!=identity or _spec(mt5,symbol)!=spec or _valuation_spec(mt5,symbol)!=valuation_spec:
            raise ValueError('Account or broker specification changed during capture')
    streams={};excluded={}
    for label,enum,seconds,key in (('4H','TIMEFRAME_H4',14400,'h4_start_utc'),
                                   ('15m','TIMEFRAME_M15',900,'structure_start_utc'),
                                   ('5m','TIMEFRAME_M5',300,'structure_start_utc')):
        check()
        streams[label],excluded[label]=_bars(mt5,symbol,getattr(mt5,enum),seconds,
                                            settings[key],settings['end_utc'])
        check()
    validate_aggregation(streams)
    def chunks():
        cursor=settings['tick_start_utc']
        while cursor<settings['end_utc']:
            check();until=min(cursor+timedelta(seconds=settings['chunk_seconds']),settings['end_utc'])
            capture=capture_adaptive(mt5,symbol=symbol,start_utc=cursor,end_utc=until,
                                     min_window_seconds=60,max_windows=256)
            check()
            # All conditions are explicit. Unknown broker calendar is not invented.
            options=dict(symbol=symbol,source=settings['source'],start_utc=cursor,end_utc=until,
                broker_spec=spec,max_spread_points=settings['max_spread_points'],
                max_gap_seconds=settings['max_gap_seconds'],windows=capture['windows'],
                max_ticks=settings['max_ticks'])
            yield dict(ticks=capture['ticks'],audit_options=options)
            cursor=until
    saved=save_tick_catalog(root/'ticks',chunks(),start_utc=settings['tick_start_utc'],
        end_utc=settings['end_utc'],max_chunks=1500,max_total_ticks=settings['max_ticks'])
    check()
    report=study_catalog(root/'ticks',expected_catalog_sha256=saved['catalog_sha256'],
        h4=streams['4H'],m15=streams['15m'],m5=streams['5m'],bar_source=settings['source'],
        as_of=settings['end_utc'].timestamp(),buffer=settings['buffer'],target_r=settings['target_r'],
        round_trip_cost_per_unit=settings['round_trip_cost_per_unit'],slippage=settings['slippage'],
        period=settings['period'],min_vhf=settings['min_vhf'],max_ticks=settings['max_ticks'])
    check()
    artifacts=dict(settings=settings,bars=streams,report=report)
    hashes={}
    for name,value in artifacts.items():
        data=_encode(value);_write_exclusive(root/(name+'.json'),data)
        hashes[name+'.json']=sha256(data).hexdigest()
    manifest=dict(schema_version=1,status='DEMO_PILOT_RESEARCH_ONLY',
        report_status=report['status'],catalog_sha256=saved['catalog_sha256'],
        demo_account_scope_sha256=_scope(identity),broker_valuation_spec=valuation_spec,
        files_sha256=hashes,excluded_unfinished_bars=excluded,
        source_consistency_checked=True,broker_authenticity_verified=False,
        cost_basis='EXPLICIT_PRICE_UNIT_ASSUMPTIONS_NOT_BROKER_CURRENCY',
        execution_allowed=False,market_edge_verified=False)
    data=_encode(manifest);_write_exclusive(root/'run.json',data)
    return dict(manifest,run_sha256=sha256(data).hexdigest())


def main(argv=None):
    parser=argparse.ArgumentParser(description='ORRERY read-only MT5 DEMO historical pilot')
    parser.add_argument('--config',required=True)
    parser.add_argument('--output',required=True)
    parser.add_argument('--terminal-path',required=True)
    args=parser.parse_args(argv)
    mt5=None
    try:
        import sys
        if sys.platform!='win32':raise RuntimeError('Windows MT5 terminal required')
        config=_decode(Path(args.config).read_bytes())
        import MetaTrader5 as mt5
        if not mt5.initialize(args.terminal_path):raise RuntimeError('Terminal initialization failed')
        result=run_pilot(mt5,config,args.output,now_utc=datetime.now(timezone.utc))
        print(_encode(result).decode('utf-8'),end='')
        return 0 if result['report_status']=='MATCHED_TICK_CANDIDATE_RESEARCH' else 2
    except Exception:
        print('{"status":"BLOCKED_PILOT_CAPTURE_OR_STUDY","execution_allowed":false}')
        return 1
    finally:
        if mt5 is not None:mt5.shutdown()


if __name__=='__main__':
    raise SystemExit(main())
