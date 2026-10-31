# SPDX-License-Identifier: GPL-3.0-only
"""Pinned diagnostic CSV intake. No TradingView login, network or order API."""
import argparse
import csv
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from io import StringIO
from math import isfinite
from pathlib import Path

from lsr04_tick_archive import _decode, _encode, _pin, _write_exclusive
from lsr05_halftrend import SOURCE_SHA256
from lsr05_reference_review import _read, _evaluate, save_review, verify_review

COLUMNS = ('SCHEMA', 'INDEX', 'OPEN_MS', 'CLOSE_MS', 'CONFIRMED', 'STANDARD', 'INTERVAL_SEC',
           'AMPLITUDE', 'DEVIATION', 'OPEN', 'HIGH', 'LOW', 'CLOSE', 'STATE', 'LINE',
           'ATR100', 'ATR_HIGH', 'ATR_LOW', 'SIGNAL', 'READY')
GENERATED = ('bars.json', 'reference.json', 'settings.json')
ROOT_FILES = ('source.csv', 'import.json') + GENERATED
PINE_FILE = 'lsr05_tradingview_export.pine'


def _sha(raw): return sha256(raw).hexdigest()


def _code_pins():
    root = Path(__file__).resolve().parent
    return {name: _sha((root / name).read_text(encoding='utf-8').encode('utf-8'))
            for name in (Path(__file__).name, PINE_FILE)}


def _numeric(cell, *, integer=False, missing_token=None):
    if missing_token is not None and cell == missing_token:
        return None
    if not isinstance(cell, str) or not 0 < len(cell) <= 128 or cell != cell.strip():
        raise ValueError('Explicit bounded decimal CSV cells required')
    try:
        value = Decimal(cell)
    except InvalidOperation:
        raise ValueError('Invalid decimal CSV cell') from None
    if not value.is_finite() or abs(value) > Decimal('1e15'):
        raise ValueError('Nonfinite or excessive CSV value')
    if integer:
        if value != value.to_integral_value(): raise ValueError('Whole CSV value required')
        return int(value)
    result = float(value)
    if not isfinite(result): raise ValueError('CSV numeric overflow')
    return result


def normalize_csv(raw, config):
    """Use explicit column names and diagnostic millisecond clocks, not UI dates."""
    if not isinstance(raw, bytes) or len(raw) > 8 * 1024 * 1024:
        raise ValueError('Bounded raw CSV bytes required')
    keys = {'schema_version', 'script_sha256', 'captured_at', 'missing_token', 'column_map', 'settings'}
    if (not isinstance(config, dict) or set(config) != keys
            or type(config['schema_version']) is not int or config['schema_version'] != 1
            or config['script_sha256'] != _code_pins()[PINE_FILE]
            or config['missing_token'] not in ('', 'NaN', 'n/a')):
        raise ValueError('Pinned explicit diagnostic import version 1 required')
    captured = config['captured_at']
    if type(captured) not in (int, float) or not isfinite(captured) or captured < 0:
        raise ValueError('UTC capture clock required')
    settings = config['settings']
    if not isinstance(settings, dict): raise ValueError('Explicit comparison settings required')
    columns = config['column_map']
    if (not isinstance(columns, dict) or set(columns) != set(COLUMNS)
            or any(not isinstance(v, str) or not 0 < len(v) <= 200 for v in columns.values())
            or len(set(columns.values())) != len(COLUMNS)):
        raise ValueError('Unique explicit column mapping required')
    reader = csv.reader(StringIO(raw.decode('utf-8-sig'), newline=''), strict=True)
    headers = next(reader, None)
    if (not headers or len(headers) > 128 or len(set(headers)) != len(headers)
            or any(not h or len(h) > 200 for h in headers)
            or not set(columns.values()) <= set(headers)):
        raise ValueError('Missing, duplicate or excessive CSV headers')
    positions = {key: headers.index(value) for key, value in columns.items()}
    bars, rows = [], []
    previous_end = None
    pending = 0
    pending_close = None
    raw_count = 0
    for index, cells in enumerate(reader):
        if index >= 10001 or len(cells) != len(headers):
            raise ValueError('Truncated, excessive or ragged CSV')
        raw_count += 1
        row = {key: cells[pos] for key, pos in positions.items()}
        ints = {key: _numeric(row[key], integer=True) for key in
                ('SCHEMA', 'INDEX', 'OPEN_MS', 'CLOSE_MS', 'CONFIRMED', 'STANDARD',
                 'INTERVAL_SEC', 'AMPLITUDE', 'DEVIATION', 'STATE', 'SIGNAL', 'READY')}
        if ints['SCHEMA'] != 1 or ints['INDEX'] != index:
            raise ValueError('Export must include sequential history from bar_index zero')
        if (ints['STANDARD'] != 1 or ints['INTERVAL_SEC'] not in (300, 900)
                or ints['INTERVAL_SEC'] != settings.get('interval')
                or ints['AMPLITUDE'] != settings.get('amplitude')
                or ints['DEVIATION'] != settings.get('channel_deviation')):
            raise ValueError('Nonstandard chart or wrong timeframe/settings')
        if (ints['CONFIRMED'] not in (0, 1) or ints['READY'] not in (0, 1)
                or ints['STATE'] not in (0, 1) or ints['SIGNAL'] not in (-1, 0, 1)):
            raise ValueError('Invalid diagnostic flags')
        opened, closed = ints['OPEN_MS'], ints['CLOSE_MS']
        if (opened < 0 or opened % 1000 or closed % 1000
                or closed - opened != ints['INTERVAL_SEC'] * 1000
                or (previous_end is not None and opened < previous_end)
                or opened / 1000 > captured):
            raise ValueError('Non-UTC whole-second, partial, overlapping or future bar')
        previous_end = closed
        prices = {k: _numeric(row[k]) for k in ('OPEN', 'HIGH', 'LOW', 'CLOSE', 'LINE')}
        if not 0 < prices['LOW'] <= min(prices['OPEN'], prices['CLOSE']) <= max(prices['OPEN'], prices['CLOSE']) <= prices['HIGH']:
            raise ValueError('Invalid exported OHLC geometry')
        atr = {k: _numeric(row[k], missing_token=config['missing_token']) for k in ('ATR100', 'ATR_HIGH', 'ATR_LOW')}
        if pending:
            raise ValueError('Only one trailing unconfirmed row may be deferred')
        if ints['CONFIRMED'] == 0:
            pending = 1; pending_close = closed // 1000
            continue
        if closed / 1000 > captured:
            raise ValueError('Confirmed CSV bar closes after capture')
        bars.append(dict(close_time=closed // 1000, open=prices['OPEN'], high=prices['HIGH'],
                         low=prices['LOW'], close=prices['CLOSE']))
        rows.append(dict(at=closed // 1000, state='UP' if ints['STATE'] == 0 else 'DOWN',
                         line=prices['LINE'], atr=atr['ATR100'], atr_high=atr['ATR_HIGH'], atr_low=atr['ATR_LOW'],
                         signal={0: None, 1: 'BUY', -1: 'SELL'}[ints['SIGNAL']], ready=bool(ints['READY'])))
    if not 0 < len(bars) <= 10000:
        raise ValueError('One to ten thousand confirmed bars required')
    reference = dict(schema_version=1, platform='TRADINGVIEW',
        implementation_label='ORRERY diagnostic wrapper of pinned everget HalfTrend; execution unverified',
        implementation_sha256=config['script_sha256'], source_sha256=SOURCE_SHA256,
        symbol=settings.get('symbol'), data_source=settings.get('data_source'), captured_at=captured,
        interval=settings.get('interval'), amplitude=settings.get('amplitude'),
        channel_deviation=settings.get('channel_deviation'), calendar_sha256=settings.get('expected_calendar_sha256'),
        bars=bars, rows=rows)
    payloads = {name: _encode(value) for name, value in zip(GENERATED, (bars, reference, settings))}
    # Existing comparator owns OHLC/session/readiness/config validation; do not duplicate it.
    comparison = _evaluate(payloads)
    audit = dict(exported_rows=raw_count, confirmed_rows=len(bars), deferred_unconfirmed_rows=pending,
                 deferred_close=pending_close, csv_raw_sha256=_sha(raw),
                 pine_compiled_verified=False, external_export_authenticity_verified=False,
                 market_edge_verified=False, execution_allowed=False)
    return payloads, audit, comparison


def prepare_review(csv_path, config_path, output, *, expected_csv_sha256, expected_config_sha256):
    raw, config_raw = _read(csv_path), _read(config_path)
    if _sha(raw) != _pin(expected_csv_sha256) or _sha(config_raw) != _pin(expected_config_sha256):
        raise ValueError('CSV or import settings differ from retained raw pin')
    payloads, audit, _ = normalize_csv(raw, _decode(config_raw))
    payloads.update({'source.csv': raw, 'import.json': config_raw})
    target = Path(output)
    target.mkdir()  # Never overwrite or resume an existing case.
    for name, data in payloads.items(): _write_exclusive(target / name, data)
    result = save_review(target / 'comparison', bars_path=target / 'bars.json',
        bars_sha256=_sha(payloads['bars.json']), reference_path=target / 'reference.json',
        reference_raw_sha256=_sha(payloads['reference.json']), settings_path=target / 'settings.json',
        settings_sha256=_sha(payloads['settings.json']))
    marker = _encode(dict(schema_version=1, files={k: _sha(v) for k, v in payloads.items()},
                          code_sha256=_code_pins(), audit=audit, comparison_receipt_sha256=result['receipt_sha256']))
    _write_exclusive(target / 'complete.json', marker)
    return dict(status=result['status'], receipt_sha256=_sha(marker), audit=audit, execution_allowed=False)


def verify_prepared(folder, *, expected_receipt_sha256):
    root = Path(folder)
    if root.is_symlink() or not root.is_dir() or {p.name for p in root.iterdir()} != set(ROOT_FILES) | {'comparison', 'complete.json'}:
        raise ValueError('Incomplete or unexpected prepared case')
    marker = _read(root / 'complete.json')
    if _sha(marker) != _pin(expected_receipt_sha256): raise ValueError('Prepared receipt pin mismatch')
    receipt = _decode(marker)
    if (not isinstance(receipt, dict) or set(receipt) != {'schema_version', 'files', 'code_sha256', 'audit', 'comparison_receipt_sha256'}
            or type(receipt['schema_version']) is not int or receipt['schema_version'] != 1
            or receipt['code_sha256'] != _code_pins() or not isinstance(receipt['files'], dict)
            or set(receipt['files']) != set(ROOT_FILES)):
        raise ValueError('Prepared schema or implementation mismatch')
    payloads = {name: _read(root / name) for name in ROOT_FILES}
    if any(_sha(data) != _pin(receipt['files'][name]) for name, data in payloads.items()):
        raise ValueError('Prepared files changed')
    generated, audit, comparison = normalize_csv(payloads['source.csv'], _decode(payloads['import.json']))
    if any(generated[name] != payloads[name] for name in GENERATED) or audit != receipt['audit']:
        raise ValueError('Reconverted CSV differs from saved inputs')
    nested = verify_review(root / 'comparison', expected_receipt_sha256=receipt['comparison_receipt_sha256'])
    if nested['result'] != comparison or any(_read(root / 'comparison' / name) != generated[name] for name in GENERATED):
        raise ValueError('Comparison is for another conversion')
    return dict(status=nested['status'], receipt_sha256=expected_receipt_sha256,
                csv_conversion_recomputed=True, comparison_recomputed=True, audit=audit, execution_allowed=False)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    run = commands.add_parser('run')
    for name in ('csv', 'csv-sha256', 'config', 'config-sha256', 'output'): run.add_argument('--' + name, required=True)
    verify = commands.add_parser('verify')
    for name in ('run', 'receipt-sha256'): verify.add_argument('--' + name, required=True)
    args = parser.parse_args(argv)
    try:
        result = (prepare_review(args.csv, args.config, args.output, expected_csv_sha256=args.csv_sha256,
                                expected_config_sha256=args.config_sha256) if args.command == 'run'
                  else verify_prepared(args.run, expected_receipt_sha256=args.receipt_sha256))
        print(result['status'])
        print('RECEIPT_SHA256=' + result['receipt_sha256'])
        print('DEFERRED_UNCONFIRMED_ROWS=' + str(result['audit']['deferred_unconfirmed_rows']))
        print('RESEARCH ONLY; Pine compilation, export authenticity and market edge are unverified; no orders.')
        return 0 if result['status'] == 'REFERENCE_SAMPLE_MATCHED_NOT_VERIFIED' else 2
    except Exception:
        print('BLOCKED: CSV, pins, diagnostic schema or saved case invalid. No orders.')
        return 1


if __name__ == '__main__': raise SystemExit(main())
