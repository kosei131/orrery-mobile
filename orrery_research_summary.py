"""Offline, receipt-pinned artifact re-audit and allowlisted research summary.
No MT5, orders, network listener, live-status claim or broker-PnL recomputation.
"""
import argparse
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from math import isclose, isfinite
from pathlib import Path
import re
from uuid import UUID
from lsr04_tick_archive import _decode, _encode, _pin, _read_metadata, _write_exclusive
from lsr03_mt5_account_pilot import verify_pilot_bundle, _settings
from lsr03_mt5_pilot import _config
from lsr03_tick_study import load_catalog_ticks
from lsr02_risk_plan import performance

PINS = ('config_sha256', 'code_manifest_sha256', 'capture_run_sha256', 'account_run_sha256')
FALSE_FLAGS = ('execution_allowed', 'market_edge_verified', 'historical_broker_conditions_verified')
STATES = {'VALIDATING', 'CAPTURING', 'COMPARING', 'COMPLETED_RESEARCH', 'BLOCKED_CONFIG',
          'BLOCKED_DATA', 'FAILED', 'INTERRUPTED'}
BASIS = 'CURRENT_MT5_ENVIRONMENT_USD_ESTIMATE_NOT_HISTORICAL_CONDITION_PROOF'


def _hash(data): return sha256(data).hexdigest()


def _clock(value):
    if not isinstance(value, str): raise ValueError('UTC clock required')
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None or dt.utcoffset() != timedelta(0): raise ValueError('UTC clock required')
    return dt.isoformat()


def _uuid(value):
    if not isinstance(value, str) or str(UUID(value)) != value: raise ValueError('Canonical UUID required')
    return value


def _number(value):
    if type(value) not in (int, float) or not isfinite(value): raise ValueError('Finite number required')
    return value


def _same(a, b):
    if not isclose(_number(a), _number(b), rel_tol=1e-10, abs_tol=1e-8):
        raise ValueError('Accounting mismatch')


def _int(value):
    if type(value) is not int or value < 0: raise ValueError('Nonnegative count required')
    return value


def audit_completed_run(folder, receipt):
    """Fail closed; receipt must be retained separately at trusted worker completion.

    Verifies stored bytes/lineage and reruns existing global tick quality. Does
    not attest broker authenticity, source execution, historical costs or PnL.
    """
    root = Path(folder)
    if root.is_symlink() or not root.is_dir(): raise ValueError('Regular run directory required')
    run_id = _uuid(root.name)
    if not isinstance(receipt, dict) or receipt.get('run_id') != run_id or receipt.get('state') != 'COMPLETED_RESEARCH':
        raise ValueError('Separately retained completion receipt required')
    for key in PINS: _pin(receipt[key])
    for key in FALSE_FLAGS:
        if receipt.get(key) is not False: raise ValueError('Read-only research receipt required')
    # Nested artifact readers must not traverse links to outside the run root.
    for name in ('capture', 'capture/ticks', 'account'):
        path = root / name
        if path.is_symlink() or not path.is_dir(): raise ValueError('Regular artifact directory required')
    def read(name, pin=None):
        data = _read_metadata(root / name)
        if pin is not None and _hash(data) != pin: raise ValueError('Artifact pin mismatch')
        return _decode(data)
    status = read('status.json'); complete = read('job_complete.json')
    for record in (status, complete):
        if record.get('run_id') != run_id or record.get('state') != 'COMPLETED_RESEARCH':
            raise ValueError('Completion state required')
        for key in PINS:
            if record.get(key) != receipt[key]: raise ValueError('Receipt lineage mismatch')
        for key in FALSE_FLAGS:
            if record.get(key) is not False: raise ValueError('Research-only flags required')
        if record.get('reason') is not None: raise ValueError('Unresolved completion reason')
    created = _clock(receipt['created_at_utc']); updated = _clock(status['updated_at_utc'])
    if status['created_at_utc'] != receipt['created_at_utc'] or complete['created_at_utc'] != receipt['created_at_utc']:
        raise ValueError('Creation clock mismatch')
    if datetime.fromisoformat(updated) < datetime.fromisoformat(created): raise ValueError('Clock order')
    cfg = read('settings.json', receipt['config_sha256'])
    if set(cfg) != {'enabled', 'terminal_path', 'stage_timeout_seconds', 'pilot', 'account'} or cfg['enabled'] is not True:
        raise ValueError('Fixed settings required')
    pilot = _config(cfg['pilot'], datetime.fromisoformat(created)); _settings(cfg['account'])
    if pilot['symbol'] != 'XAUUSD' or cfg['pilot']['round_trip_cost_per_unit'] <= 0 or cfg['account']['round_trip_cost_per_lot_usd'] <= 0:
        raise ValueError('Supported positive-cost research required')
    code = read('code_manifest.json', receipt['code_manifest_sha256'])
    revision = code['declared_revision']
    if not isinstance(revision, str) or not re.fullmatch('[0-9a-f]{40}', revision): raise ValueError('Declared revision required')
    if any(record.get('declared_revision') != revision for record in (receipt, status, complete)):
        raise ValueError('Code revision mismatch')
    if not isinstance(code['files_sha256'], dict) or not code['files_sha256']: raise ValueError('Source inventory required')
    for name, pin in code['files_sha256'].items():
        if Path(name).name != name or not name.endswith('.py'): raise ValueError('Source inventory path')
        _pin(pin)
    capture, files = verify_pilot_bundle(root / 'capture', receipt['capture_run_sha256'])
    if capture['report_status'] != 'MATCHED_TICK_CANDIDATE_RESEARCH': raise ValueError('Capture quality status')
    if files['settings.json'] != _decode(_encode(pilot)): raise ValueError('Capture settings mismatch')
    if read('pilot_settings.json') != cfg['pilot'] or read('account_settings.json') != cfg['account']:
        raise ValueError('Stage input settings mismatch')
    account = read('account/account_run.json', receipt['account_run_sha256'])
    if (account.get('status') != 'DEMO_ACCOUNT_PILOT_CURRENT_SPEC_ESTIMATE_ONLY'
        or account.get('report_status') != 'CONFIRMATION_RETEST_INDEPENDENT_ACCOUNT_RESEARCH'
        or account.get('input_pilot_run_sha256') != receipt['capture_run_sha256']
        or account.get('catalog_sha256') != capture['catalog_sha256']
        or set(account['files_sha256']) != {'account_settings.json', 'sequence.json', 'account_report.json'}):
        raise ValueError('Account marker lineage')
    for key in FALSE_FLAGS:
        if account.get(key) is not False: raise ValueError('Account flags')
    saved = {}
    for name, pin in account['files_sha256'].items():
        _pin(pin); saved[name] = read('account/' + name, pin)
    if saved['account_settings.json'] != cfg['account']: raise ValueError('Account settings mismatch')
    report = saved['account_report.json']; sequence = saved['sequence.json']
    if report.get('status') != 'CONFIRMATION_RETEST_INDEPENDENT_ACCOUNT_RESEARCH' or report.get('valuation_basis') != BASIS:
        raise ValueError('Account report basis')
    for key in (*FALSE_FLAGS, 'six_month_backtest_complete', 'cost_assumptions_verified'):
        if report.get(key) is not False: raise ValueError('Unverified claims required')
    if report.get('no_carry_interval_caller_asserted') is not True: raise ValueError('Carry assertion required')
    expected_input = _hash(json.dumps([sequence['confirmation_evidence'], sequence['retest_observations'],
        files['bars.json']['5m']], sort_keys=True, allow_nan=False).encode())
    if report.get('input_sha256') != expected_input or report.get('catalog_sha256') != capture['catalog_sha256']:
        raise ValueError('Report input mismatch')
    start, end = (int(pilot[k].timestamp()) for k in ('tick_start_utc', 'end_utc'))
    if (start-36000)//86400 != (end-1-36000)//86400: raise ValueError('Hawaii risk interval')
    for key in ('fixed_distance', 'target_r', 'entry_delay_msc', 'entry_window_msc',
                'max_holding_msc', 'round_trip_cost_per_lot_usd', 'slippage', 'cost_source'):
        if report['config'][key] != cfg['account'][key]: raise ValueError('Account plan config')
    for key in ('volume_min', 'volume_max', 'volume_step'):
        if report['config'][key] != capture['broker_valuation_spec'][key]: raise ValueError('Volume spec mismatch')
    if report['config']['daily_boundary_utc_hour'] != 10 or report['config']['carry_source'] is not None:
        raise ValueError('Intraday account rules mismatch')
    if report['config']['cohort_start'] != start or report['config']['cohort_end'] != end:
        raise ValueError('Cohort mismatch')
    loaded = load_catalog_ticks(root / 'capture' / 'ticks', expected_catalog_sha256=capture['catalog_sha256'],
        bar_source=pilot['source'], as_of=end, max_ticks=pilot['max_ticks'])
    if loaded['blocked'] or loaded['symbol'] != 'XAUUSD' or loaded['start_msc'] != start*1000:
        raise ValueError('Tick quality blocked')
    if set(report['accounts']) != {'CONFIRMATION', 'RETEST'}: raise ValueError('Exact comparison modes required')
    accounts = {mode: _account_summary(value) for mode,value in report['accounts'].items()}
    universe = _int(report['universe'])
    if set(report['omitted']) != set(accounts): raise ValueError('Omitted modes mismatch')
    for mode,item in report['omitted'].items():
        if not isinstance(item['no_entry'], list) or not isinstance(item['outside_tick_horizon'], list):
            raise ValueError('Omission lists required')
        accounts[mode]['omitted_candidates'] = dict(no_entry=len(item['no_entry']),
            outside_tick_horizon=len(item['outside_tick_horizon']), submitted_plans=_int(item['submitted_plans']))
    # Recheck root/leaf pins after the potentially long tick scan; sampled, not atomic.
    read('settings.json', receipt['config_sha256']); read('code_manifest.json', receipt['code_manifest_sha256'])
    verify_pilot_bundle(root / 'capture', receipt['capture_run_sha256'])
    read('account/account_run.json', receipt['account_run_sha256'])
    for name,pin in account['files_sha256'].items(): read('account/' + name, pin)
    if read('status.json') != status or read('job_complete.json') != complete:
        raise ValueError('Completion changed during audit')
    return dict(schema_version=1, run_id=run_id, audit_status='CONSISTENT_RESEARCH_ARTIFACTS',
        recorded_state='COMPLETED_RESEARCH', recorded_stage_updated_at_utc=updated,
        declared_revision=revision, period_start_utc=pilot['tick_start_utc'].isoformat(),
        period_end_utc=pilot['end_utc'].isoformat(), symbol='XAUUSD', candidate_universe=universe, accounts=accounts,
        execution_allowed=False, market_edge_verified=False, historical_broker_conditions_verified=False,
        six_month_backtest_complete=False, cost_assumptions_verified=False, valuation_basis=BASIS,
        pnl_recomputed=False, worker_liveness_verified=False, code_execution_attested=False)


def _account_summary(account):
    if account.get('status') != 'INTRADAY_SINGLE_SYMBOL_ACCOUNT_RESEARCH' or account.get('symbol') != 'XAUUSD':
        raise ValueError('Supported account required')
    for key in ('execution_allowed', 'market_edge_verified', 'six_month_backtest_complete'):
        if account.get(key) is not False: raise ValueError('Account claim')
    stats = performance(account['trades'], initial_equity=3000)
    for key,value in account['closed_statistics'].items():
        if key not in {'trades','wins','losses','breakeven','win_rate','expectancy_r','profit_factor'}:
            raise ValueError('Unknown closed statistic')
    for key in ('trades','wins','losses','breakeven','win_rate','expectancy_r','profit_factor'):
        actual = account['closed_statistics'][key]
        if stats[key] is None:
            if actual is not None: raise ValueError('Undefined statistic must be null')
        elif key in ('trades','wins','losses','breakeven'):
            if _int(actual) != stats[key]: raise ValueError('Trade count mismatch')
        else: _same(actual, stats[key])
    for trade in account['trades']: _same(trade['net_usd'], trade['gross_pnl']-trade['cost'])
    _same(account['closed_trade_net_usd'], stats['net_pnl_usd'])
    _same(account['initial_equity_usd'], 3000)
    _same(account['balance_change_usd'], _number(account['ending_balance_usd'])-3000)
    _same(account['equity_change_usd'], _number(account['ending_equity_usd'])-3000)
    dd = _number(account['max_sampled_equity_drawdown_usd'])
    if dd < 0: raise ValueError('Negative drawdown')
    for key in ('daily_stop_held', 'streak_stop_held'):
        if type(account[key]) is not bool: raise ValueError('Boolean stop flag')
    decisions = dict(RESEARCH_ENTRY=0, SKIP=0, NO_ENTRY=0)
    for value in account['decisions']:
        if value.get('status') not in decisions: raise ValueError('Unknown decision status')
        decisions[value['status']] += 1
    if account['open_position'] is not None and not isinstance(account['open_position'], dict):
        raise ValueError('Open position representation')
    return dict(initial_equity_usd=3000, ending_balance_usd=account['ending_balance_usd'],
        ending_equity_usd=account['ending_equity_usd'], equity_change_usd=account['equity_change_usd'],
        closed_trade_net_usd=stats['net_pnl_usd'], max_sampled_equity_drawdown_usd=dd,
        closed_trades=stats['trades'], wins=stats['wins'], losses=stats['losses'], breakeven=stats['breakeven'],
        win_rate_fraction=stats['win_rate'], expectancy_r=stats['expectancy_r'], profit_factor=stats['profit_factor'],
        open_positions=int(account['open_position'] is not None), decision_status_counts=decisions,
        max_consecutive_losses=_int(account['max_consecutive_losses']), daily_stop_held=account['daily_stop_held'],
        streak_stop_held=account['streak_stop_held'])


def build_summary(folder, receipt):
    """Sanitized failure object; no exception, source label, account or path text."""
    try: return audit_completed_run(folder, receipt)
    except Exception:
        return dict(schema_version=1, audit_status='AUDIT_BLOCKED', accounts=None,
            execution_allowed=False, market_edge_verified=False, worker_liveness_verified=False)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', required=True); parser.add_argument('--receipt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args(argv)
    try:
        receipt = _decode(_read_metadata(Path(args.receipt)).decode('utf-8-sig'))
        result = build_summary(args.run, receipt)
        _write_exclusive(Path(args.output), _encode(result))
        print(result['audit_status'])
        return 0 if result['audit_status'] == 'CONSISTENT_RESEARCH_ARTIFACTS' else 2
    except Exception:
        print('SUMMARY_NOT_WRITTEN'); return 1


if __name__ == '__main__': raise SystemExit(main())
