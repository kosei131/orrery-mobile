"""Offline, read-only preflight for pinned MT5 DEMO candidate capture.
Does not connect to MT5, write records, or assert that a terminal is DEMO.
"""
import argparse
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from lsr04_tick_archive import _decode, _encode, _pin
from orrery_mt5_candidate_probe import _request

def preflight(reference, reference_sha256, *, prepared_request, request_sha256, terminal_path, output, now=None):
    _pin(reference_sha256); _pin(request_sha256)
    now = now or datetime.now(timezone.utc).replace(microsecond=0)
    request = _request(reference, reference_sha256, now)
    path = Path(prepared_request)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 1024*1024:
        raise ValueError('Pinned regular request file required')
    raw=path.read_bytes()
    if sha256(raw).hexdigest()!=request_sha256:
        raise ValueError('Independent request pin mismatch')
    expected=_decode(raw)
    if not isinstance(expected,dict):
        raise ValueError('Request object required')
    for key,value in request.items():
        if expected.get(key)!=value:
            raise ValueError('Prepared request differs from reference candidate')
    sources=expected.get('required_python_source_sha256')
    if not isinstance(sources,dict) or not sources:
        raise ValueError('Pinned source manifest required')
    for name,digest in sources.items():
        if not isinstance(name,str) or name in ('','.','..') or '/' in name or '\\' in name or name.startswith('.'):
            raise ValueError('Unsafe source manifest name')
        _pin(digest)
        file=Path(__file__).with_name(name)
        if file.is_symlink() or not file.is_file() or sha256(file.read_bytes()).hexdigest()!=digest:
            raise ValueError('Pinned source implementation missing or changed')
    exe=Path(terminal_path)
    if not exe.is_absolute() or exe.name.lower()!='terminal64.exe' or not exe.is_file() or exe.is_symlink():
        raise ValueError('Explicit regular terminal64.exe path required')
    dest=Path(output)
    if dest.exists() or dest.is_symlink() or not dest.parent.is_dir():
        raise ValueError('Unused output directory with existing parent required')
    return dict(status='OFFLINE_PREFLIGHT_OK_NOT_DEMO_AUTHENTICATED',symbol=request['symbol'],
       candidate_id=request['candidate_id'],start_utc=request['start_utc'],end_utc=request['end_utc'],
       reference_sha256=reference_sha256,prepared_request_sha256=request_sha256,
       demo_account_verified=False,history_captured=False,backtest_ready=False,
       actual_profit_usd=None,execution_allowed=False)

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    for flag in ('reference','reference-sha256','prepared-request','request-sha256','terminal-path','output'):
        p.add_argument('--'+flag,required=True)
    a=p.parse_args(argv)
    result=preflight(a.reference,a.reference_sha256,prepared_request=a.prepared_request,
       request_sha256=a.request_sha256,terminal_path=a.terminal_path,output=a.output)
    print(_encode(result).decode())
    return 0

if __name__=='__main__':
    raise SystemExit(main())
