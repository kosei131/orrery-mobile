"""Small DEMO history intake only. No costs, signals, PnL or trading calls."""
import argparse
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from uuid import uuid4
from hashlib import sha256
from lsr03_mt5_pilot import _account, _spec
from lsr04_mt5_ticks import read_ticks, MAX_TICKS
from lsr04_tick_archive import _encode, _write_exclusive, save_tick_archive, verify_tick_archive


def check_history(mt5, *, output, symbol, start, end, now):
    # Whole-second UTC, at most ten minutes; never a six-month coverage claim.
    for value in (start, end, now):
        if (not isinstance(value, datetime) or value.utcoffset() != timedelta(0)
                or value.microsecond):
            raise ValueError('Whole-second UTC required')
    if not start < end <= now or end-start > timedelta(minutes=10):
        raise ValueError('Historical window <=10 minutes required')
    if symbol not in ('XAUUSD', 'USDJPY'):
        raise ValueError('Canonical symbol required')
    identity = _account(mt5)
    spec = _spec(mt5, symbol)
    result = read_ticks(mt5, account_is_demo=True, symbol=symbol,
                        start_utc=start, end_utc=end)
    if _account(mt5) != identity or _spec(mt5, symbol) != spec:
        raise ValueError('Account or specification changed')
    if not 0 < result['count'] < MAX_TICKS:
        raise ValueError('Empty or saturated history')
    # Archive intervals are half open. Intake includes the right boundary.
    rows = [r for r in result['ticks'] if r['time_msc'] < int(end.timestamp()*1000)]
    if not rows:
        raise ValueError('No ticks inside requested interval')
    root = Path(output)
    root.mkdir()  # fresh folder only; failures never overwrite a previous run
    settings = dict(symbol=symbol, start_utc=start, end_utc=end,
                    audit_policy='diagnostic_only_not_entry_permission',
                    max_spread_points=100, max_gap_seconds=60,
                    commission_verified=False, costs_required=False)
    # Trace intake/audit source bytes; not a signed Git revision attestation.
    names = ('orrery_mt5_history_check.py', 'lsr03_mt5_pilot.py',
             'lsr04_mt5_account_sync.py', 'lsr04_mt5_ticks.py',
             'lsr04_tick_archive.py', 'lsr04_tick_quality.py')
    settings['source_sha256'] = {name: sha256(
        Path(__file__).with_name(name).read_bytes()).hexdigest() for name in names}
    request_bytes = _encode(settings)
    _write_exclusive(root/'request.json', request_bytes)
    saved = save_tick_archive(root/'archive', rows, audit_options=dict(
        symbol=symbol, start_utc=start, end_utc=end, source='MT5_DEMO_READ_ONLY',
        broker_spec=spec, max_spread_points=100, max_gap_seconds=60,
        max_ticks=MAX_TICKS, windows=[dict(start=start, end=end, count=len(rows))]))
    verified = verify_tick_archive(root/'archive',
        expected_manifest_sha256=saved['manifest_sha256'],
        expected_audit_config_sha256=saved['audit_config_sha256'], max_ticks=MAX_TICKS)
    if _account(mt5) != identity or _spec(mt5, symbol) != spec:
        raise ValueError('Account or specification changed during persistence')
    receipt = dict(status='HISTORY_SAVED_REVIEW_REQUIRED', symbol=symbol,
                   rows=len(rows), quality_status=verified['audit']['status'],
                   request_sha256=sha256(request_bytes).hexdigest(),
                   review_reasons=verified['audit']['review_reasons'],
                   manifest_sha256=saved['manifest_sha256'],
                   audit_config_sha256=saved['audit_config_sha256'],
                   completeness_verified=False, backtest_ready=False,
                   profitability_evaluated=False, execution_allowed=False)
    if receipt['quality_status'] == 'BLOCKED_TICK_QUALITY':
        receipt['status'] = 'BLOCKED_HISTORY_QUALITY'
    _write_exclusive(root/'history_check.json', _encode(receipt))  # last marker
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--symbol', choices=('XAUUSD', 'USDJPY'), default='XAUUSD')
    parser.add_argument('--terminal-path', default=r'C:\Program Files\MetaTrader 5\terminal64.exe')
    args = parser.parse_args()
    mt5 = None
    try:
        if sys.platform != 'win32' or sys.version_info[:2] != (3, 12):
            raise ValueError('Windows Python 3.12 required')
        import MetaTrader5 as mt5
        if not mt5.initialize(args.terminal_path, timeout=30000):
            raise ValueError('Terminal unavailable')
        now = datetime.now(timezone.utc).replace(microsecond=0)
        end = now-timedelta(minutes=2)
        parent = Path(os.environ['LOCALAPPDATA'])/'ORRERYFX'/'history-checks'
        parent.mkdir(parents=True, exist_ok=True)
        output = parent/str(uuid4())
        result = check_history(mt5, output=output, symbol=args.symbol,
                               start=end-timedelta(minutes=10), end=end, now=now)
        print(_encode(result).decode(), end='')
        print('LOCAL_OUTPUT:', output)
        return 2 if result['status'].startswith('BLOCKED') else 0
    except Exception:
        print('BLOCKED: History unavailable or validation failed. No backtest ran.')
        return 1
    finally:
        if mt5 is not None:
            mt5.shutdown()


if __name__ == '__main__':
    raise SystemExit(main())
