"""Read-only evidence check for the requested $3000 six-month backtest.

This is not an account replay engine. Never turns absent results into $0,
scales independent candidate R into account returns, or runs synthetic data
as a substitute. Reports exactly what is missing before a real-data run.
"""
import argparse
from pathlib import Path
from lsr04_tick_archive import _decode
from lsr04_tick_quality import _time
from lsr04_tick_catalog import verify_tick_catalog

KEYS={'initial_equity_usd','symbols','start_utc','end_utc','period_basis',
      'risk_fraction','daily_loss_fraction','basket_risk_fraction',
      'consecutive_loss_stop','daily_boundary_utc_hour','catalogs'}


def preflight(config):
    if not isinstance(config,dict) or set(config)!=KEYS:
        raise ValueError('Exact backtest specification required')
    if type(config['initial_equity_usd']) not in (int,float) or config['initial_equity_usd']!=3000:
        raise ValueError('Requested initial USD equity must remain $3000')
    if config['symbols']!=['XAUUSD','USDJPY']:
        raise ValueError('Separate XAUUSD and USDJPY evidence required')
    start,end=_time(config['start_utc']),_time(config['end_utc'])
    if start>=end:raise ValueError('Increasing UTC horizon required')
    limits=dict(risk_fraction=.0025,daily_loss_fraction=.01,basket_risk_fraction=.01,
                consecutive_loss_stop=3,daily_boundary_utc_hour=10)
    for key,value in limits.items():
        if type(config[key]) not in (int,float) or config[key]!=value:
            raise ValueError('Research baseline changed; review the specification explicitly')
    if type(config['consecutive_loss_stop']) is not int or type(config['daily_boundary_utc_hour']) is not int:
        raise ValueError('Integer stop/day boundary required')
    if not isinstance(config['period_basis'],str) or not config['period_basis']:
        raise ValueError('Explicit period interpretation required')
    references=config['catalogs']
    if not isinstance(references,dict) or references.keys()-set(config['symbols']):
        raise ValueError('Unexpected market data reference')
    evidence={}
    for symbol in config['symbols']:
        ref=references.get(symbol)
        if ref is None:
            evidence[symbol]=dict(status='MISSING_VERIFIED_TICK_CATALOG');continue
        if not isinstance(ref,dict) or set(ref)!={'path','catalog_sha256'} or not isinstance(ref['path'],str):
            raise ValueError('Explicit catalog path and independent pin required')
        try:
            result=verify_tick_catalog(ref['path'],expected_catalog_sha256=ref['catalog_sha256'])
            # Bind verified source symbol as well as the requested interval.
            from lsr04_tick_archive import _read_metadata
            from hashlib import sha256
            data=_read_metadata(Path(ref['path'])/'catalog.json')
            if sha256(data).hexdigest()!=ref['catalog_sha256']:raise ValueError('Catalog changed')
            catalog=_decode(data)
            reasons=[]
            if catalog['shared_audit_options']['symbol']!=symbol:reasons.append('WRONG_SYMBOL')
            if result['requested_start_msc']!=start or result['requested_end_msc']!=end:
                reasons.append('REQUESTED_SIX_MONTH_HORIZON_NOT_COVERED')
            if result['blocked_quality_chunks']:reasons.append('BLOCKED_QUALITY_CHUNKS')
            if result['review_reasons']:reasons.append('UNRESOLVED_QUALITY_EVIDENCE')
            evidence[symbol]=dict(status='LOCAL_INTEGRITY_ONLY' if not reasons else 'INSUFFICIENT_MARKET_EVIDENCE',
                reasons=reasons,total_rows=result['total_rows'],chunk_count=result['chunk_count'],
                completeness_verified=False)
        except Exception:
            evidence[symbol]=dict(status='INVALID_OR_UNAVAILABLE_TICK_CATALOG')
    blockers=['SIX_MONTH_MULTISYMBOL_OVERNIGHT_ACCOUNT_REPLAY_NOT_IMPLEMENTED',
              'HISTORICAL_BROKER_USD_VALUATION_AND_COSTS_NOT_VERIFIED',
              'CONTINUOUS_SESSION_AWARE_OHLC_REPLAY_NOT_IMPLEMENTED']
    if any(e['status']!='LOCAL_INTEGRITY_ONLY' for e in evidence.values()):
        blockers.insert(0,'REQUESTED_MARKET_HISTORY_NOT_VERIFIED')
    return dict(status='BACKTEST_NOT_RUN',initial_equity_usd=3000,
        start_utc=config['start_utc'],end_utc=config['end_utc'],
        requested_calendar_days=(end-start)//86400000,
        research_rules=limits,initial_planned_risk_usd=7.5,initial_daily_limit_usd=30,
        initial_basket_limit_usd=30,evidence=evidence,blockers=blockers,
        net_profit_usd=None,ending_equity_usd=None,return_fraction=None,
        max_drawdown_usd=None,trade_count=None,execution_allowed=False,
        caveat='No six-month market simulation has run. $3000 is initial capital, not an ending-balance result. No zero-profit or synthetic fallback.')


def main(argv=None):
    parser=argparse.ArgumentParser(description='$3000 real-data backtest evidence check; not a simulation')
    parser.add_argument('--config',default='backtest_3000.json')
    args=parser.parse_args(argv)
    import json
    report=preflight(_decode(Path(args.config).read_bytes()))
    print(json.dumps(report,ensure_ascii=True,indent=2,allow_nan=False))
    return 2


if __name__=='__main__':
    raise SystemExit(main())
