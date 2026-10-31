# SPDX-License-Identifier: GPL-3.0-only
"""Offline file intake and replayable receipts for supplied HalfTrend exports."""
import argparse
from hashlib import sha256
from pathlib import Path

from lsr04_tick_archive import _decode, _encode, _pin, _write_exclusive
from lsr05_reference_compare import compare_reference, reference_sha256

MAX_INPUT_BYTES = 8 * 1024 * 1024
INPUTS = ('bars.json', 'reference.json', 'settings.json')
MEMBERS = set(INPUTS) | {'result.json', 'complete.json'}
SOURCES = ('lsr05_reference_review.py', 'lsr05_reference_compare.py', 'lsr05_halftrend.py',
           'lsr05_session_clock.py', 'orrery_m1_complete_bars.py',
           'lsr04_tick_quality.py', 'lsr04_tick_archive.py')


def _digest(data):
    return sha256(data).hexdigest()


def _read(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError('Regular input file required')
    with path.open('rb') as stream:
        data = stream.read(MAX_INPUT_BYTES + 1)
    if len(data) > MAX_INPUT_BYTES:
        raise ValueError('Input exceeds fixed read budget')
    return data


def _code_pins():
    root = Path(__file__).resolve().parent
    # Stable across Windows CRLF checkout. These identify code, not its execution.
    return {name: _digest((root / name).read_text(encoding='utf-8').encode('utf-8'))
            for name in SOURCES}


def _evaluate(payloads):
    bars, reference, settings = [_decode(payloads[name]) for name in INPUTS]
    keys = {'schema_version', 'symbol', 'data_source', 'as_of', 'interval', 'amplitude',
            'channel_deviation', 'absolute_tolerance', 'calendar_evidence', 'expected_calendar_sha256'}
    if (not isinstance(settings, dict) or set(settings) != keys
            or type(settings['schema_version']) is not int or settings['schema_version'] != 1):
        raise ValueError('Complete fixed comparison settings version 1 required')
    return compare_reference(bars, reference, expected_reference_sha256=reference_sha256(reference),
                             **{k: v for k, v in settings.items() if k != 'schema_version'})


def save_review(output, *, bars_path, bars_sha256, reference_path, reference_raw_sha256,
                settings_path, settings_sha256):
    """Check independently retained raw file pins BEFORE creating a new output."""
    payloads = {}
    for name, path, pin in zip(INPUTS, (bars_path, reference_path, settings_path),
                               (bars_sha256, reference_raw_sha256, settings_sha256)):
        _pin(pin)
        data = _read(path)
        if _digest(data) != pin:
            raise ValueError('Raw input file does not match retained pin')
        payloads[name] = data
    result = _evaluate(payloads)
    payloads['result.json'] = _encode(result)
    receipt = dict(schema_version=1, encoding='raw-inputs-canonical-result-v1',
                   files={name: dict(bytes=len(data), sha256=_digest(data)) for name, data in payloads.items()},
                   code_sha256=_code_pins(), status=result['status'],
                   source_execution_attested=False, external_export_authenticity_verified=False,
                   market_edge_verified=False, execution_allowed=False)
    marker = _encode(receipt)
    target = Path(output)
    # No resume, overwrite or parent-directory creation. A partial write stays incomplete.
    target.mkdir()
    for name, data in payloads.items():
        _write_exclusive(target / name, data)
    _write_exclusive(target / 'complete.json', marker)
    return dict(status=result['status'], receipt_sha256=_digest(marker),
                external_export_authenticity_verified=False, market_edge_verified=False, execution_allowed=False)


def verify_review(folder, *, expected_receipt_sha256):
    """Hash all archived bytes and reproduce the comparison using the same code."""
    _pin(expected_receipt_sha256)
    root = Path(folder)
    if root.is_symlink() or not root.is_dir() or {p.name for p in root.iterdir()} != MEMBERS:
        raise ValueError('Incomplete or unexpected review members')
    marker = _read(root / 'complete.json')
    if _digest(marker) != expected_receipt_sha256:
        raise ValueError('Receipt differs from separately retained pin')
    receipt = _decode(marker)
    keys = {'schema_version', 'encoding', 'files', 'code_sha256', 'status',
            'source_execution_attested', 'external_export_authenticity_verified',
            'market_edge_verified', 'execution_allowed'}
    if (not isinstance(receipt, dict) or set(receipt) != keys
            or type(receipt['schema_version']) is not int or receipt['schema_version'] != 1
            or receipt['encoding'] != 'raw-inputs-canonical-result-v1'
            or receipt['code_sha256'] != _code_pins()
            or any(receipt[k] is not False for k in ('source_execution_attested',
                'external_export_authenticity_verified', 'market_edge_verified', 'execution_allowed'))):
        raise ValueError('Unsupported receipt or implementation change')
    files = receipt['files']
    if not isinstance(files, dict) or set(files) != MEMBERS - {'complete.json'}:
        raise ValueError('Receipt inventory mismatch')
    payloads = {}
    for name in files:
        entry = files[name]
        if (not isinstance(entry, dict) or set(entry) != {'bytes', 'sha256'}
                or type(entry['bytes']) is not int or not 0 <= entry['bytes'] <= MAX_INPUT_BYTES):
            raise ValueError('Invalid receipt file bound')
        _pin(entry['sha256'])
        data = _read(root / name)
        if len(data) != entry['bytes'] or _digest(data) != entry['sha256']:
            raise ValueError('Archived input or result changed')
        payloads[name] = data
    fresh = _evaluate(payloads)
    if payloads['result.json'] != _encode(fresh) or receipt['status'] != fresh['status']:
        raise ValueError('Recomputed comparison differs from receipt')
    return dict(status=fresh['status'], receipt_sha256=expected_receipt_sha256,
                local_integrity_verified=True, comparison_recomputed=True,
                source_execution_attested=False, external_export_authenticity_verified=False,
                market_edge_verified=False, execution_allowed=False, result=fresh)


def _exit_code(status):
    return 0 if status == 'REFERENCE_SAMPLE_MATCHED_NOT_VERIFIED' else 2


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    run = commands.add_parser('run')
    for option in ('bars', 'bars-sha256', 'reference', 'reference-raw-sha256',
                   'settings', 'settings-sha256', 'output'):
        run.add_argument('--' + option, required=True)
    verify = commands.add_parser('verify')
    verify.add_argument('--run', required=True)
    verify.add_argument('--receipt-sha256', required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == 'run':
            result = save_review(args.output, bars_path=args.bars, bars_sha256=args.bars_sha256,
                reference_path=args.reference, reference_raw_sha256=args.reference_raw_sha256,
                settings_path=args.settings, settings_sha256=args.settings_sha256)
        else:
            result = verify_review(args.run, expected_receipt_sha256=args.receipt_sha256)
        # No source paths, private metadata, row payloads or credentials printed.
        print(result['status'])
        print('RECEIPT_SHA256=' + result['receipt_sha256'])
        print('RESEARCH ONLY; external authenticity, profitability and execution are unverified/disabled.')
        return _exit_code(result['status'])
    except Exception:
        print('BLOCKED: Input, pin, saved review or code version is invalid. No orders sent.')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
