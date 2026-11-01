"""Read-only DEMO Bid/Ask probe after the latest pinned reference candidate.

Reuses the bounded 10-minute history intake. This is a connectivity/coverage
probe, not a full trade replay, fee discovery, historical USD proof or order.
"""
import argparse
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
import sys

from lsr04_tick_archive import _decode, _encode, _pin, _write_exclusive
from lsr03_mt5_pilot import _account, _spec, _valuation_spec, _scope
from orrery_mt5_history_check import check_history


def _request(path, expected_sha256, now):
    _pin(expected_sha256)
    if (not isinstance(now, datetime) or now.utcoffset() != timedelta(0) or now.microsecond):
        raise ValueError('Whole-second UTC now required')
    source = Path(path)
    if source.is_symlink() or not source.is_file():
        raise ValueError('Regular pinned reference report required')
    with source.open('rb') as stream:
        raw = stream.read(1024 * 1024 + 1)
    if len(raw) > 1024 * 1024 or sha256(raw).hexdigest() != expected_sha256:
        raise ValueError('Reference report pin or size mismatch')
    r = _decode(raw)
    if (r.get('status') != 'EXPLORATORY_WINDOW_RESET_GROSS_REFERENCE_ONLY'
            or r.get('execution_allowed') is not False or r.get('actual_profit_usd') is not None):
        raise ValueError('Read-only price-reference report required')
    _pin(r['zip_sha256'])
    audit = r['bundle_audit']
    if (audit.get('zip_sha256') != r['zip_sha256']
            or audit.get('source_declared') != 'OANDA:XAUUSD via TradingView MCP'):
        raise ValueError('Explicit reference source required')
    candidates = r.get('candidates')
    if not isinstance(candidates, list) or not 1 <= len(candidates) <= 1000:
        raise ValueError('Bounded nonempty candidates required')
    seen = set()
    for row in candidates:
        p = row['plan']; at = row['entry_reference_at_s']; name = p['id']
        if (p.get('symbol') != 'XAUUSD' or p.get('side') not in ('BUY','SELL')
                or type(at) is not int or at < 0
                or type(p.get('known_at_msc')) is not int or p['known_at_msc'] != at * 1000
                or not isinstance(name, str) or not name.startswith('XAUUSD:')
                or len(name) > 200 or any(ord(c) < 32 for c in name) or name in seen):
            raise ValueError('Unique canonical reference candidates required')
        seen.add(name)
    # Selection depends only on reference time/id, never on winning outcomes.
    row = max(candidates, key=lambda c: (c['entry_reference_at_s'], c['plan']['id']))
    start = datetime.fromtimestamp(row['entry_reference_at_s'], timezone.utc)
    end = start + timedelta(minutes=10)
    if end > now:
        raise ValueError('Historical 10-minute probe required')
    return dict(schema_version=1, reference_report_sha256=expected_sha256,
        reference_zip_sha256=r['zip_sha256'], reference_source=audit['source_declared'],
        candidate_id=row['plan']['id'], symbol='XAUUSD', side=row['plan']['side'],
        selection='LATEST_REFERENCE_CLOCK_NOT_OUTCOME', start_utc=start.isoformat(), end_utc=end.isoformat(),
        requested_minutes=10, full_trade_horizon_requested=False, execution_allowed=False)


def probe_latest(mt5, *, reference, reference_sha256, output, now):
    request = _request(reference, reference_sha256, now)
    root = Path(output)
    if root.exists() or root.is_symlink():
        raise FileExistsError('New output directory required')
    identity = _account(mt5); spec = _spec(mt5, 'XAUUSD'); valuation = _valuation_spec(mt5, 'XAUUSD')
    def check():
        if (_account(mt5) != identity or _spec(mt5, 'XAUUSD') != spec
                or _valuation_spec(mt5, 'XAUUSD') != valuation):
            raise ValueError('DEMO identity or specification changed')
    check(); root.mkdir()
    request_bytes = _encode(request); _write_exclusive(root/'request.json', request_bytes)
    result = check_history(mt5, output=root/'history', symbol='XAUUSD',
        start=datetime.fromisoformat(request['start_utc']), end=datetime.fromisoformat(request['end_utc']), now=now)
    check()
    history_bytes = (root/'history'/'history_check.json').read_bytes()
    code_names = (Path(__file__).name, 'orrery_mt5_history_check.py', 'lsr04_mt5_ticks.py',
                  'lsr03_mt5_pilot.py', 'lsr04_tick_archive.py', 'lsr04_tick_quality.py')
    receipt = dict(status=('BLOCKED_CANDIDATE_PROBE_QUALITY' if result['status'].startswith('BLOCKED')
                          else 'DEMO_CANDIDATE_PROBE_SAVED_REVIEW_REQUIRED'),
        candidate_id=request['candidate_id'], start_utc=request['start_utc'], end_utc=request['end_utc'],
        selection=request['selection'], request_sha256=sha256(request_bytes).hexdigest(),
        reference_report_sha256=reference_sha256, history_receipt_sha256=sha256(history_bytes).hexdigest(),
        demo_scope_sha256=_scope(identity), current_symbol_spec=spec, current_valuation_spec=valuation,
        source_sha256={n: sha256(Path(__file__).with_name(n).read_bytes()).hexdigest() for n in code_names},
        history=result, mt5_feed_matches_tradingview_verified=False,
        commission_per_lot_usd=None, slippage=None, carry_cost_usd=None,
        historical_usd_valuation_verified=False, full_trade_history_complete=False,
        backtest_ready=False, actual_profit_usd=None, profitability_evaluated=False, execution_allowed=False)
    check()
    _write_exclusive(root/'probe.json', _encode(receipt))  # last completion marker
    return receipt


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--reference', required=True); p.add_argument('--reference-sha256', required=True)
    p.add_argument('--terminal-path', required=True, help='Exact path of caller-confirmed DEMO terminal')
    p.add_argument('--output', required=True); a = p.parse_args(argv); mt5 = None
    try:
        if sys.platform != 'win32' or sys.version_info[:2] != (3,12):
            raise ValueError('Windows Python 3.12 required')
        now = datetime.now(timezone.utc).replace(microsecond=0)
        # Validate reference and output before initializing an explicitly selected terminal.
        _request(a.reference, a.reference_sha256, now)
        if Path(a.output).exists() or Path(a.output).is_symlink():
            raise FileExistsError('New output required')
        import MetaTrader5 as mt5
        if not mt5.initialize(a.terminal_path, timeout=30000):
            raise ValueError('Terminal unavailable')
        result = probe_latest(mt5, reference=a.reference, reference_sha256=a.reference_sha256,
                              output=a.output, now=now)
        print(_encode(result).decode(), end='')
        return 2 if result['status'].startswith('BLOCKED') else 0
    except Exception:
        print('{"status":"BLOCKED_CANDIDATE_PROBE","execution_allowed":false,"actual_profit_usd":null}')
        return 1
    finally:
        if mt5 is not None:
            mt5.shutdown()


if __name__ == '__main__':
    raise SystemExit(main())
