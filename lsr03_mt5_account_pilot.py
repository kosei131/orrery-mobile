"""Read-only Windows DEMO pilot bundle -> two current-spec USD estimates.
Never historical-conversion proof; restricted to USD-account/USD-profit XAU.
"""
import argparse
from datetime import datetime
from hashlib import sha256
from math import isfinite
from pathlib import Path
from lsr04_tick_archive import _decode, _encode, _write_exclusive, _read_metadata, _pin
from lsr03_mt5_pilot import _account, _valuation_spec, _scope
from lsr04_tick_quality import _time
from orrery_public_xau_sequence_study import report_from_bars
from lsr03_confirmation_accounts import compare_confirmation_accounts

REQUIRED={'fixed_distance','target_r','entry_delay_msc','entry_window_msc','max_holding_msc',
          'round_trip_cost_per_lot_usd','slippage','cost_source',
          'no_carry_interval_confirmed','no_carry_evidence_source','max_profit_calls'}


def _settings(value):
    if not isinstance(value,dict) or set(value)!=REQUIRED:
        raise ValueError('Exact account pilot settings required')
    config=_decode(_encode(value))
    for key in ('fixed_distance','target_r','round_trip_cost_per_lot_usd','slippage'):
        v=config[key]
        if type(v) not in (int,float) or not isfinite(v) or v<0 or (key in ('fixed_distance','target_r') and v==0):
            raise ValueError('Explicit finite prices/costs required; no defaults')
    for key in ('entry_delay_msc','entry_window_msc','max_holding_msc','max_profit_calls'):
        if type(config[key]) is not int or config[key]<=0:raise ValueError('Explicit positive integer settings required')
    if config['entry_delay_msc']>=config['entry_window_msc'] or config['max_profit_calls']>20000:
        raise ValueError('Invalid entry or broker calculation budget')
    for key in ('cost_source','no_carry_evidence_source'):
        if not isinstance(config[key],str) or not config[key].strip():raise ValueError('Documented cost/carry source required')
    if config['no_carry_interval_confirmed'] is not True:
        raise ValueError('Short capture must explicitly exclude broker rollover; historical carry otherwise required')
    return config


def verify_pilot_bundle(root, expected_run_sha256):
    """Fixed file names, independently pinned completion marker, bounded reads."""
    _pin(expected_run_sha256)
    root=Path(root)
    raw=_read_metadata(root/'run.json')
    if sha256(raw).hexdigest()!=expected_run_sha256:raise ValueError('Pilot run pin mismatch')
    manifest=_decode(raw)
    if manifest.get('status')!='DEMO_PILOT_RESEARCH_ONLY' or manifest.get('execution_allowed') is not False:
        raise ValueError('Read-only DEMO pilot completion marker required')
    _pin(manifest['catalog_sha256']);_pin(manifest['demo_account_scope_sha256'])
    if set(manifest['files_sha256'])!={'settings.json','bars.json','report.json'}:
        raise ValueError('Unexpected bundle file list')
    files={}
    for name,digest in manifest['files_sha256'].items():
        _pin(digest);data=_read_metadata(root/name)
        if sha256(data).hexdigest()!=digest:raise ValueError('Pilot file hash mismatch')
        files[name]=_decode(data)
    return manifest,files


def current_demo_valuation(mt5, *, captured_scope, captured_spec, max_calls):
    identity=_account(mt5)
    if identity[2]!='USD' or _scope(identity)!=captured_scope:
        raise ValueError('Same captured USD DEMO account required')
    if (not isinstance(captured_spec,dict) or captured_spec.get('symbol')!='XAUUSD'
            or captured_spec.get('currency_profit')!='USD'
            or _valuation_spec(mt5,'XAUUSD')!=captured_spec):
        raise ValueError('Captured/current USD-profit XAUUSD specification must match')
    if type(max_calls) is not int or not 1<=max_calls<=20000:raise ValueError('Bounded broker call budget required')
    state={'profit_calculations':0}
    def check():
        if _account(mt5)!=identity or _valuation_spec(mt5,'XAUUSD')!=captured_spec:
            raise ValueError('DEMO identity/specification changed')
    def quote(symbol,side,lots,entry,close,at_msc):
        if symbol!='XAUUSD' or side not in ('BUY','SELL'):
            raise ValueError('No historical FX conversion supported')
        if any(type(v) not in (int,float) or not isfinite(v) or v<=0 for v in (lots,entry,close)) or type(at_msc) is not int:
            raise ValueError('Explicit finite valuation inputs required')
        check()
        if state['profit_calculations']>=max_calls:raise ValueError('Broker profit-call budget exceeded')
        action=getattr(mt5,'ORDER_TYPE_BUY' if side=='BUY' else 'ORDER_TYPE_SELL',None)
        if action is None:raise ValueError('Broker order-type constants absent')
        state['profit_calculations']+=1
        result=mt5.order_calc_profit(action,symbol,lots,entry,close)
        check()
        if type(result) not in (int,float) or not isfinite(result):raise ValueError('Broker profit estimate failed')
        return float(result)
    check()
    return quote,check,state


def run_account_pilot(mt5,pilot_path,expected_run_sha256,config,output):
    config=_settings(config)
    manifest,files=verify_pilot_bundle(pilot_path,expected_run_sha256)
    settings=files['settings.json'];bars=files['bars.json']
    if settings['symbol']!='XAUUSD':raise ValueError('USDJPY requires historical conversion; unsupported in this pilot')
    _time(settings['tick_start_utc']);_time(settings['end_utc'])
    start=datetime.fromisoformat(settings['tick_start_utc'])
    end=datetime.fromisoformat(settings['end_utc'])
    if start.microsecond or end.microsecond or not start<end:
        raise ValueError('Whole-second ordered pilot bounds required')
    s,e=int(start.timestamp()*1000),int(end.timestamp()*1000)
    if ((s-36000000)//86400000!=(e-1-36000000)//86400000):
        raise ValueError('One Hawaii risk session required; no daily carry inference')
    quote,check,state=current_demo_valuation(mt5,captured_scope=manifest['demo_account_scope_sha256'],
        captured_spec=manifest['broker_valuation_spec'],max_calls=config['max_profit_calls'])
    root=Path(output);root.mkdir()
    sequence=report_from_bars(bars['15m'],bars['5m'])
    spec=manifest['broker_valuation_spec']
    report=compare_confirmation_accounts(Path(pilot_path)/'ticks',
        expected_catalog_sha256=manifest['catalog_sha256'],bar_source=settings['source'],
        as_of=end.timestamp(),confirmations=sequence['confirmation_evidence'],
        observations=sequence['retest_observations'],m5=bars['5m'],
        fixed_distance=config['fixed_distance'],target_r=config['target_r'],
        entry_delay_msc=config['entry_delay_msc'],entry_window_msc=config['entry_window_msc'],
        max_holding_msc=config['max_holding_msc'],volume_min=spec['volume_min'],
        volume_max=spec['volume_max'],volume_step=spec['volume_step'],pnl_quote=quote,
        round_trip_cost_per_lot_usd=config['round_trip_cost_per_lot_usd'],
        cost_source=config['cost_source'],slippage=config['slippage'],max_ticks=settings['max_ticks'],
        cohort_start=s//1000,cohort_end=e//1000)
    check();verify_pilot_bundle(pilot_path,expected_run_sha256)
    report.update(valuation_basis='CURRENT_MT5_ENVIRONMENT_USD_ESTIMATE_NOT_HISTORICAL_CONDITION_PROOF',
        historical_broker_conditions_verified=False,cost_assumptions_verified=False,
        no_carry_interval_caller_asserted=True,execution_allowed=False)
    hashes={}
    for name,value in (('account_settings.json',config),('sequence.json',sequence),('account_report.json',report)):
        data=_encode(value);_write_exclusive(root/name,data);hashes[name]=sha256(data).hexdigest()
    check()
    result=dict(status='DEMO_ACCOUNT_PILOT_CURRENT_SPEC_ESTIMATE_ONLY',report_status=report['status'],
        input_pilot_run_sha256=expected_run_sha256,catalog_sha256=manifest['catalog_sha256'],
        files_sha256=hashes,profit_calculations=state['profit_calculations'],
        historical_broker_conditions_verified=False,market_edge_verified=False,execution_allowed=False)
    data=_encode(result);_write_exclusive(root/'account_run.json',data)
    return dict(result,account_run_sha256=sha256(data).hexdigest())


def main(argv=None):
    p=argparse.ArgumentParser(description='Read-only DEMO captured-history account estimate')
    p.add_argument('--pilot',required=True);p.add_argument('--pilot-run-sha256',required=True)
    p.add_argument('--config',required=True);p.add_argument('--output',required=True)
    p.add_argument('--terminal-path',required=True)
    args=p.parse_args(argv);mt5=None
    try:
        import sys
        if sys.platform!='win32':raise RuntimeError('Windows MT5 required')
        config=_settings(_decode(Path(args.config).read_bytes()))
        import MetaTrader5 as mt5
        if not mt5.initialize(args.terminal_path):raise RuntimeError('Terminal initialization failed')
        r=run_account_pilot(mt5,args.pilot,args.pilot_run_sha256,config,args.output)
        print(_encode(r).decode(),end='')
        return 0 if r['report_status']=='CONFIRMATION_RETEST_INDEPENDENT_ACCOUNT_RESEARCH' else 2
    except Exception:
        print('{"status":"BLOCKED_DEMO_ACCOUNT_PILOT","execution_allowed":false}')
        return 1
    finally:
        if mt5 is not None:mt5.shutdown()

if __name__=='__main__':raise SystemExit(main())
