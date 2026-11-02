"""Offline verification of pinned candidate-probe folders, never MT5 access.

Expected request and probe pins must be retained separately from returned data.
Matching hashes prove local consistency, not broker authenticity or profitability.
"""
import argparse
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path

from lsr04_tick_archive import _decode, _encode, _pin, verify_tick_archive
from orrery_mt5_candidate_probe import _request

PROBE_SOURCES = {'orrery_mt5_candidate_probe.py','orrery_mt5_history_check.py','lsr04_mt5_ticks.py',
                 'lsr03_mt5_pilot.py','lsr04_tick_archive.py','lsr04_tick_quality.py'}
HISTORY_SOURCES = {'orrery_mt5_history_check.py','lsr03_mt5_pilot.py','lsr04_mt5_account_sync.py',
                   'lsr04_mt5_ticks.py','lsr04_tick_archive.py','lsr04_tick_quality.py'}
PROBE_KEYS = {'status','candidate_id','start_utc','end_utc','selection','request_sha256',
    'reference_report_sha256','history_receipt_sha256','demo_scope_sha256','current_symbol_spec',
    'current_valuation_spec','source_sha256','history','mt5_feed_matches_tradingview_verified',
    'commission_per_lot_usd','slippage','carry_cost_usd','historical_usd_valuation_verified',
    'full_trade_history_complete','backtest_ready','actual_profit_usd','profitability_evaluated','execution_allowed'}
HISTORY_KEYS = {'status','symbol','rows','quality_status','request_sha256','review_reasons',
    'manifest_sha256','audit_config_sha256','completeness_verified','backtest_ready',
    'profitability_evaluated','execution_allowed'}


def _meta(path, expected=None):
    if expected is not None:
        _pin(expected)
    if path.is_symlink() or not path.is_file():
        raise ValueError('Regular metadata required')
    with path.open('rb') as stream:
        raw = stream.read(1024*1024+1)
    if len(raw)>1024*1024 or (expected is not None and sha256(raw).hexdigest()!=expected):
        raise ValueError('Metadata budget or pin mismatch')
    value=_decode(raw)
    if not isinstance(value,dict):
        raise ValueError('Object metadata required')
    return raw, value


def _directory(path, names):
    if path.is_symlink() or not path.is_dir() or {p.name for p in path.iterdir()}!=set(names):
        raise ValueError('Exact complete probe directory required')


def _source_pins(actual, expected, names):
    if not isinstance(actual,dict) or set(actual)!=names:
        raise ValueError('Exact source pin set required')
    for name in names:
        _pin(actual[name]); _pin(expected.get(name))
        if actual[name]!=expected[name]:
            raise ValueError('Source implementation differs from expected request')


def verify_probe(folder, *, probe_sha256, expected_request, expected_request_sha256, reference, now):
    root=Path(folder)
    _, expected=_meta(Path(expected_request),expected_request_sha256)
    code=expected.get('required_python_source_sha256')
    if not isinstance(code,dict) or not (PROBE_SOURCES|HISTORY_SOURCES)<=code.keys():
        raise ValueError('Independently pinned expected source files required')
    refpin=expected['reference_report_sha256']; _pin(refpin)
    request=_request(reference,refpin,now)
    if any(expected.get(k)!=v for k,v in request.items()):
        raise ValueError('Prepared request differs from pinned reference')
    _directory(root, {'request.json','probe.json','history'})
    _directory(root/'history', {'request.json','history_check.json','archive'})
    _, probe=_meta(root/'probe.json',probe_sha256)
    if not isinstance(probe,dict) or set(probe)!=PROBE_KEYS:
        raise ValueError('Supported probe receipt required')
    for key in ('mt5_feed_matches_tradingview_verified','historical_usd_valuation_verified',
                'full_trade_history_complete','backtest_ready','profitability_evaluated','execution_allowed'):
        if probe[key] is not False:
            raise ValueError('Probe must retain unverified status')
    if any(probe[k] is not None for k in ('commission_per_lot_usd','slippage','carry_cost_usd','actual_profit_usd')):
        raise ValueError('Unverified costs and profit must remain unknown')
    _pin(probe['demo_scope_sha256'])
    raw_request,_=_meta(root/'request.json',probe['request_sha256'])
    if raw_request!=_encode(request):
        raise ValueError('Returned candidate, source or time request differs')
    if (probe['reference_report_sha256']!=refpin
            or any(probe[k]!=request[k] for k in ('candidate_id','start_utc','end_utc','selection'))):
        raise ValueError('Receipt/request binding mismatch')
    _source_pins(probe['source_sha256'],code,PROBE_SOURCES)
    _, history=_meta(root/'history/history_check.json',probe['history_receipt_sha256'])
    if not isinstance(history,dict) or set(history)!=HISTORY_KEYS or history!=probe['history']:
        raise ValueError('Nested history receipt mismatch')
    if any(history[k] is not False for k in ('completeness_verified','backtest_ready','profitability_evaluated','execution_allowed')):
        raise ValueError('History is not an execution permission')
    _, settings=_meta(root/'history/request.json',history['request_sha256'])
    expected_settings=dict(symbol='XAUUSD',start_utc=request['start_utc'],end_utc=request['end_utc'],
        audit_policy='diagnostic_only_not_entry_permission',max_spread_points=100,max_gap_seconds=60,
        commission_verified=False,costs_required=False,source_sha256=settings.get('source_sha256'))
    if _encode(settings)!=_encode(expected_settings):
        raise ValueError('History request/policy differs')
    _source_pins(settings['source_sha256'],code,HISTORY_SOURCES)
    archive=root/'history/archive'
    _directory(archive, {'manifest.json','audit.json','ticks.jsonl'})
    for name in ('manifest.json','audit.json'):
        _meta(archive/name)
    ticks=archive/'ticks.jsonl'
    if ticks.is_symlink() or not ticks.is_file() or ticks.stat().st_size>64*1024*1024:
        raise ValueError('Bounded regular tick stream required')
    verified=verify_tick_archive(archive,expected_manifest_sha256=history['manifest_sha256'],
        expected_audit_config_sha256=history['audit_config_sha256'],max_ticks=300000)
    options=verified['audit_options']; audit=verified['audit']
    if (type(history['rows']) is not int or not 0<history['rows']<300000
            or history['rows']!=verified['row_count'] or history['symbol']!='XAUUSD'
            or history['quality_status']!=audit['status'] or history['review_reasons']!=audit['review_reasons']):
        raise ValueError('History count/quality differs from recomputation')
    if (options['source']!='MT5_DEMO_READ_ONLY' or options['symbol']!='XAUUSD'
            or options['start_utc']!=request['start_utc'] or options['end_utc']!=request['end_utc']
            or options['broker_spec']!=probe['current_symbol_spec']
            or options['max_spread_points']!=100 or options['max_gap_seconds']!=60
            or options['max_ticks']!=300000 or options['sessions'] is not None or options['session_source'] is not None
            or options['windows']!=[dict(start=request['start_utc'],end=request['end_utc'],count=history['rows'])]):
        raise ValueError('Pinned archive source/symbol/window/policy mismatch')
    blocked=audit['status']=='BLOCKED_TICK_QUALITY'
    if (history['status']!=('BLOCKED_HISTORY_QUALITY' if blocked else 'HISTORY_SAVED_REVIEW_REQUIRED')
            or probe['status']!=('BLOCKED_CANDIDATE_PROBE_QUALITY' if blocked else 'DEMO_CANDIDATE_PROBE_SAVED_REVIEW_REQUIRED')):
        raise ValueError('Blocked quality cannot be relabelled as successful capture')
    return dict(status='BLOCKED_LOCAL_PROBE_QUALITY' if blocked else 'VERIFIED_LOCAL_PROBE_ONLY_REVIEW_REQUIRED',
        probe_sha256=probe_sha256,expected_request_sha256=expected_request_sha256,
        reference_report_sha256=refpin,candidate_id=request['candidate_id'],
        start_utc=request['start_utc'],end_utc=request['end_utc'],rows=history['rows'],
        quality_status=audit['status'],review_reasons=audit['review_reasons'],
        local_bytes_recomputed=True,expected_source_pins_match=True,
        broker_authenticity_verified=False,live_demo_account_verified=False,
        mt5_feed_matches_tradingview_verified=False,full_trade_history_complete=False,
        commission_per_lot_usd=None,slippage=None,carry_cost_usd=None,
        actual_profit_usd=None,backtest_ready=False,execution_allowed=False)


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    for flag in ('folder','probe-sha256','expected-request','expected-request-sha256','reference','output'):
        p.add_argument('--'+flag,required=True)
    a=p.parse_args(argv)
    target=Path(a.output).resolve(); source=Path(a.folder).resolve()
    if target==source or source in target.parents:
        raise ValueError('Verification output must be outside input bundle')
    result=verify_probe(a.folder,probe_sha256=a.probe_sha256,expected_request=a.expected_request,
        expected_request_sha256=a.expected_request_sha256,reference=a.reference,
        now=datetime.now(timezone.utc).replace(microsecond=0))
    with target.open('xb') as stream:
        stream.write(_encode(result))
    print(result['status'])
    return 2 if result['status'].startswith('BLOCKED') else 0


if __name__=='__main__':
    raise SystemExit(main())
