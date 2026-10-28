"""Exclusive, checksummed normalized-tick archives with pinned verification.

Local manifest hashes detect mismatch only against a separately retained pin;
this is not broker authentication. A final manifest is the completion marker.
Verification streams a fresh audit before returning any successful result.
"""
import hashlib
import json
import os
from datetime import datetime
from pathlib import Path
import lsr04_tick_quality as quality

MAX_METADATA_BYTES = 64*1024*1024
MAX_LINE_BYTES = 4096
FILES = ('ticks.jsonl', 'audit.json', 'manifest.json')
DEFAULTS = dict(max_gap_seconds=60, windows=None, sessions=None, session_source=None,
                spread_bin_edges_points=[1,5,10,25,50,100], max_ticks=10000000, max_examples=100)
REQUIRED = {'symbol','start_utc','end_utc','source','broker_spec','max_spread_points'}


def _encode(value):
    def convert(x):
        if isinstance(x, datetime):
            quality._time(x)
            return x.isoformat()
        raise TypeError('Unsupported archive value')
    return (json.dumps(value, default=convert, ensure_ascii=True, sort_keys=True,
                       separators=(',', ':'), allow_nan=False)+'\n').encode('utf-8')


def _decode(data):
    def pairs(items):
        result = {}
        for k,v in items:
            if k in result:raise ValueError('Duplicate JSON key')
            result[k] = v
        return result
    def invalid(value):raise ValueError('Nonfinite JSON value')
    if isinstance(data, bytes):data = data.decode('utf-8')
    return json.loads(data, object_pairs_hook=pairs, parse_constant=invalid)


def _pin(value):
    if not isinstance(value,str) or len(value)!=64 or any(c not in '0123456789abcdef' for c in value):
        raise ValueError('Independent SHA-256 pin required')
    return value


def _options(options):
    if not isinstance(options,dict) or not REQUIRED <= options.keys() or options.keys()-REQUIRED-DEFAULTS.keys():
        raise ValueError('Explicit supported audit options required')
    encoded = _encode(dict(DEFAULTS, **options))
    if len(encoded) > MAX_METADATA_BYTES:raise ValueError('Audit configuration too large')
    result = _decode(encoded)
    # Freeze caller inputs and validate config before creating an output folder.
    quality.audit_ticks(iter(()), **result)
    return result


def _auditor_digest():
    # Universal newline decoding keeps a checkout's CRLF/LF from changing identity.
    return hashlib.sha256(Path(quality.__file__).read_text(encoding='utf-8').encode('utf-8')).hexdigest()


def _write_exclusive(path, data):
    with path.open('xb') as stream:
        stream.write(data);stream.flush();os.fsync(stream.fileno())


def save_tick_archive(path, ticks, *, audit_options):
    options = _options(audit_options)
    target = Path(path)
    target.mkdir()  # fails on an existing file, directory or symlink; never overwrites
    digest = hashlib.sha256();count = 0;size = 0
    with (target/'ticks.jsonl').open('xb') as output:
        def rows():
            nonlocal count, size
            for row in ticks:
                if not isinstance(row,dict) or set(row) != {'time_msc','bid','ask'}:
                    raise ValueError('Normalized time_msc/bid/ask records required')
                data = _encode(row)
                if len(data) > MAX_LINE_BYTES:raise ValueError('Tick record too large')
                output.write(data);digest.update(data);size+=len(data);count+=1
                yield row
        audit = quality.audit_ticks(rows(), **options)
        output.flush();os.fsync(output.fileno())
    audit_bytes = _encode(audit)
    _write_exclusive(target/'audit.json', audit_bytes)
    manifest = dict(schema_version=1, encoding='normalized-jsonl-utf8-v1',
                    auditor_sha256=_auditor_digest(), audit_options=options,
                    row_count=count, ticks_bytes=size, ticks_sha256=digest.hexdigest(),
                    audit_bytes=len(audit_bytes), audit_sha256=hashlib.sha256(audit_bytes).hexdigest())
    manifest_bytes = _encode(manifest)
    if len(manifest_bytes) > MAX_METADATA_BYTES:raise ValueError('Manifest too large')
    # Last file is the completion marker. An interrupted/failed write leaves an
    # incomplete folder which verification rejects; it is not silently resumed.
    _write_exclusive(target/'manifest.json', manifest_bytes)
    return dict(status='SAVED_UNVERIFIED_MARKET_ARCHIVE',
                manifest_sha256=hashlib.sha256(manifest_bytes).hexdigest(),
                row_count=count, quality_status=audit['status'],
                audit_config_sha256=audit['audit_config_sha256'],
                completeness_verified=False, backtest_ready=False, execution_allowed=False)


def _read_metadata(path):
    if path.is_symlink() or not path.is_file():raise ValueError('Regular archive file required')
    with path.open('rb') as stream:
        data = stream.read(MAX_METADATA_BYTES+1)
    if len(data) > MAX_METADATA_BYTES:raise ValueError('Metadata exceeds read budget')
    return data


def verify_tick_archive(path, *, expected_manifest_sha256,
                        expected_audit_config_sha256=None, max_ticks=10000000):
    _pin(expected_manifest_sha256)
    if expected_audit_config_sha256 is not None:_pin(expected_audit_config_sha256)
    if type(max_ticks) is not int or not 1 <= max_ticks <= 100000000:
        raise ValueError('Explicit verification read budget required')
    target = Path(path)
    if target.is_symlink() or not target.is_dir():raise ValueError('Regular archive directory required')
    if {p.name for p in target.iterdir()} != set(FILES):raise ValueError('Incomplete or unexpected archive files')
    manifest_bytes = _read_metadata(target/'manifest.json')
    if hashlib.sha256(manifest_bytes).hexdigest() != expected_manifest_sha256:
        raise ValueError('Manifest pin mismatch')
    manifest = _decode(manifest_bytes)
    expected_keys={'schema_version','encoding','auditor_sha256','audit_options',
                   'row_count','ticks_bytes','ticks_sha256','audit_bytes','audit_sha256'}
    if not isinstance(manifest,dict) or set(manifest) != expected_keys or type(manifest['schema_version']) is not int or manifest['schema_version'] != 1 or manifest['encoding'] != 'normalized-jsonl-utf8-v1':
        raise ValueError('Unsupported archive schema')
    if manifest['auditor_sha256'] != _auditor_digest():raise ValueError('Audit implementation version mismatch')
    options = _options(manifest['audit_options'])
    for key in ('row_count','ticks_bytes','audit_bytes'):
        if type(manifest[key]) is not int or manifest[key] < 0:raise ValueError('Invalid manifest count')
    if manifest['row_count'] > max_ticks:
        raise ValueError('Archive exceeds caller verification budget')
    _pin(manifest['ticks_sha256']);_pin(manifest['audit_sha256'])
    audit_bytes = _read_metadata(target/'audit.json')
    if len(audit_bytes) != manifest['audit_bytes'] or hashlib.sha256(audit_bytes).hexdigest() != manifest['audit_sha256']:
        raise ValueError('Stored audit hash/size mismatch')
    stored_audit = _decode(audit_bytes)
    data_path = target/'ticks.jsonl'
    if data_path.is_symlink() or not data_path.is_file():raise ValueError('Regular tick file required')
    digest = hashlib.sha256();count = 0;size = 0
    with data_path.open('rb') as stream:
        def rows():
            nonlocal count, size
            while True:
                data = stream.readline(MAX_LINE_BYTES+1)
                if not data:break
                if len(data) > MAX_LINE_BYTES or not data.endswith(b'\n'):
                    raise ValueError('Oversized or truncated JSONL record')
                count+=1;size+=len(data)
                if count > max_ticks or size > manifest['ticks_bytes']:
                    raise ValueError('Tick stream exceeds pinned size/budget')
                digest.update(data)
                row = _decode(data)
                if not isinstance(row,dict) or set(row) != {'time_msc','bid','ask'}:
                    raise ValueError('Invalid normalized tick schema')
                yield row
        fresh_audit = quality.audit_ticks(rows(), **options)
    if count != manifest['row_count'] or size != manifest['ticks_bytes'] or digest.hexdigest() != manifest['ticks_sha256']:
        raise ValueError('Tick bytes/hash/count mismatch')
    if audit_bytes != _encode(fresh_audit) or stored_audit != fresh_audit:
        raise ValueError('Recomputed audit mismatch')
    if expected_audit_config_sha256 is not None and fresh_audit['audit_config_sha256'] != expected_audit_config_sha256:
        raise ValueError('Expected audit configuration mismatch')
    return dict(status='VERIFIED_LOCAL_ARCHIVE_ONLY', row_count=count,
                manifest_sha256=expected_manifest_sha256, audit=fresh_audit,
                completeness_verified=False, backtest_ready=False, execution_allowed=False,
                caveat='Checks local bytes and reproducible audit against an independent pin, not broker authenticity. Raw broker fields were not archived; concurrent external file replacement is outside this API guarantee.')
