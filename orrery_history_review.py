"""Offline review of a short DEMO intake using a separately retained receipt pin."""
import argparse
from hashlib import sha256
from pathlib import Path
from lsr04_tick_archive import (_decode, _encode, _pin, _read_metadata,
                                _write_exclusive, verify_tick_archive)
from lsr04_tick_quality import _time


def review_history(folder, *, expected_receipt_sha256):
    _pin(expected_receipt_sha256)
    root = Path(folder)
    if root.is_symlink() or not root.is_dir():
        raise ValueError('Regular intake folder required')
    if {p.name for p in root.iterdir()} != {'request.json', 'archive', 'history_check.json'}:
        raise ValueError('Incomplete or unexpected intake members')
    receipt_bytes = _read_metadata(root/'history_check.json')
    if sha256(receipt_bytes).hexdigest() != expected_receipt_sha256:
        raise ValueError('Independent receipt pin mismatch')
    receipt = _decode(receipt_bytes)
    keys = {'status','symbol','rows','quality_status','request_sha256','review_reasons',
            'manifest_sha256','audit_config_sha256','completeness_verified',
            'backtest_ready','profitability_evaluated','execution_allowed'}
    if not isinstance(receipt, dict) or set(receipt) != keys:
        raise ValueError('Unsupported receipt')
    for name in ('completeness_verified','backtest_ready','profitability_evaluated','execution_allowed'):
        if receipt[name] is not False:
            raise ValueError('Unsupported approval or profit claim')
    request_bytes = _read_metadata(root/'request.json')
    if sha256(request_bytes).hexdigest() != _pin(receipt['request_sha256']):
        raise ValueError('Request mismatch')
    request = _decode(request_bytes)
    request_keys = {'symbol','start_utc','end_utc','audit_policy','max_spread_points',
                    'max_gap_seconds','commission_verified','costs_required','source_sha256'}
    if not isinstance(request, dict) or set(request) != request_keys:
        raise ValueError('Unsupported request')
    names = {'orrery_mt5_history_check.py','lsr03_mt5_pilot.py','lsr04_mt5_account_sync.py',
             'lsr04_mt5_ticks.py','lsr04_tick_archive.py','lsr04_tick_quality.py'}
    if not isinstance(request['source_sha256'], dict) or set(request['source_sha256']) != names:
        raise ValueError('Source inventory mismatch')
    for pin in request['source_sha256'].values(): _pin(pin)
    if (request['audit_policy'] != 'diagnostic_only_not_entry_permission'
            or request['commission_verified'] is not False or request['costs_required'] is not False
            or type(request['max_spread_points']) is not int or request['max_spread_points'] != 100
            or type(request['max_gap_seconds']) is not int or request['max_gap_seconds'] != 60):
        raise ValueError('Unsupported diagnostic policy')
    start, end = _time(request['start_utc']), _time(request['end_utc'])
    if start % 1000 or end % 1000 or not 0 < end-start <= 600000:
        raise ValueError('Short whole-second UTC window required')
    verified = verify_tick_archive(root/'archive',
        expected_manifest_sha256=receipt['manifest_sha256'],
        expected_audit_config_sha256=receipt['audit_config_sha256'], max_ticks=300000)
    options, audit = verified['audit_options'], verified['audit']
    if (options['source'] != 'MT5_DEMO_READ_ONLY' or options['symbol'] != request['symbol']
            or receipt['symbol'] != request['symbol']
            or _time(options['start_utc']) != start or _time(options['end_utc']) != end
            or options['max_spread_points'] != request['max_spread_points']
            or options['max_gap_seconds'] != request['max_gap_seconds']
            or options['sessions'] is not None or options['session_source'] is not None):
        raise ValueError('Archive/request mismatch')
    rows = verified['row_count']
    windows = options['windows']
    if (not isinstance(windows, list) or len(windows) != 1
            or set(windows[0]) != {'start','end','count'}
            or _time(windows[0]['start']) != start or _time(windows[0]['end']) != end
            or type(windows[0]['count']) is not int or windows[0]['count'] != rows
            or options['max_ticks'] != 300000):
        raise ValueError('Capture window mismatch')
    expected_status = ('BLOCKED_HISTORY_QUALITY' if audit['status']=='BLOCKED_TICK_QUALITY'
                       else 'HISTORY_SAVED_REVIEW_REQUIRED')
    if (type(receipt['rows']) is not int or not 0 < rows < 300000 or receipt['rows'] != rows
            or receipt['status'] != expected_status or receipt['quality_status'] != audit['status']
            or receipt['review_reasons'] != audit['review_reasons']):
        raise ValueError('Receipt/audit mismatch')
    return dict(status='BLOCKED_HISTORY_QUALITY' if expected_status.startswith('BLOCKED')
                else 'LOCAL_HISTORY_REVIEW_REQUIRED', symbol=receipt['symbol'],
                requested_start_msc=start, requested_end_msc=end, rows=rows,
                counts=audit['counts'], issues=audit['issues'], review_reasons=audit['review_reasons'],
                spread_points=audit['spread_points'], observed_max_gap_seconds=audit['observed_max_gap_seconds'],
                receipt_sha256=expected_receipt_sha256, local_integrity_verified=True,
                broker_authenticity_verified=False, source_execution_attested=False,
                completeness_verified=False, backtest_ready=False,
                profitability_evaluated=False, execution_allowed=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', required=True)
    parser.add_argument('--receipt-sha256', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    try:
        output = Path(args.output)
        root = Path(args.run).resolve()
        if output.resolve().is_relative_to(root):
            raise ValueError('Review must be saved outside intake')
        result = review_history(root, expected_receipt_sha256=args.receipt_sha256)
        _write_exclusive(output, _encode(result))
        print(result['status'])
        return 2 if result['status'].startswith('BLOCKED') else 0
    except Exception:
        print('BLOCKED: Intake incomplete, changed or unverifiable. No backtest ran.')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
