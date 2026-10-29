"""One-shot DEMO research coordinator. No network server, scheduler or orders.
The existing child CLIs retain ownership of MT5 initialize/shutdown and gates.
"""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
from hashlib import sha256
import os
from pathlib import Path
import re
import subprocess
import sys
from uuid import uuid4
from lsr04_tick_archive import _decode, _encode, _read_metadata, _pin, _write_exclusive
from lsr03_mt5_pilot import _config
from lsr03_mt5_account_pilot import _settings, verify_pilot_bundle


def digest(data): return sha256(data).hexdigest()


def verify_code(root, manifest_path, expected_sha256):
    """Caller-retained pin, exact top-level Python inventory, no path traversal."""
    _pin(expected_sha256)
    data = _read_metadata(manifest_path)
    if digest(data) != expected_sha256: raise ValueError('CODE_PIN')
    manifest = _decode(data)
    if set(manifest) != {'declared_revision', 'files_sha256'} or not re.fullmatch('[0-9a-f]{40}', manifest['declared_revision']):
        raise ValueError('CODE_MANIFEST')
    expected = manifest['files_sha256']
    actual = {p.name for p in root.glob('*.py') if p.is_file()}
    if not isinstance(expected, dict) or set(expected) != actual or not actual:
        raise ValueError('CODE_INVENTORY')
    for name, pin in expected.items():
        _pin(pin)
        if Path(name).name != name or (root / name).is_symlink() or digest((root / name).read_bytes()) != pin:
            raise ValueError('CODE_CHANGED')
    return manifest


@contextmanager
def worker_lock(root):
    root.mkdir(parents=True, exist_ok=True)
    with (root / 'worker.lock').open('a+b') as handle:
        if handle.seek(0, 2) == 0: handle.write(b'0'); handle.flush()
        handle.seek(0)
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try: yield
        finally:
            handle.seek(0)
            if os.name == 'nt': msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else: fcntl.flock(handle, fcntl.LOCK_UN)


def atomic_json(path, value):
    temp = path.with_name(path.name + '.tmp')
    with temp.open('wb') as handle:
        handle.write(_encode(value)); handle.flush(); os.fsync(handle.fileno())
    os.replace(temp, path)


def settings(value, now):
    if not isinstance(value, dict) or set(value) != {'enabled', 'terminal_path', 'stage_timeout_seconds', 'pilot', 'account'}:
        raise ValueError('Exact worker settings required')
    value = _decode(_encode(value))
    if value['enabled'] is not True: raise ValueError('Worker disabled')
    if type(value['stage_timeout_seconds']) is not int or not 1 <= value['stage_timeout_seconds'] <= 7200:
        raise ValueError('Bounded timeout required')
    if not isinstance(value['terminal_path'], str) or not Path(value['terminal_path']).is_absolute() or not Path(value['terminal_path']).is_file():
        raise ValueError('Terminal path required')
    pilot = _config(value['pilot'], now); _settings(value['account'])
    if pilot['symbol'] != 'XAUUSD': raise ValueError('Account pilot supports XAUUSD only')
    # Zero-cost smoke mode is not authorized in this coordinator.
    if value['pilot']['round_trip_cost_per_unit'] <= 0 or value['account']['round_trip_cost_per_lot_usd'] <= 0:
        raise ValueError('Zero cost mode is not enabled')
    s, e = (int(pilot[k].timestamp()*1000) for k in ('tick_start_utc', 'end_utc'))
    if (s-36000000)//86400000 != (e-1-36000000)//86400000:
        raise ValueError('One Hawaii risk day required')
    return value


def run_job(config, runtime_root, code_root, manifest_path, code_pin, *, now=None, launch=subprocess.run):
    """One configured runtime root; no automatic retry/resume/period advancement.

    launch injection tests orchestration only; real CLI invokes fixed child files.
    """
    now = now or datetime.now(timezone.utc)
    runtime_root, code_root = Path(runtime_root).resolve(), Path(code_root).resolve()
    with worker_lock(runtime_root):
        runs = runtime_root / 'runs'; runs.mkdir(exist_ok=True)
        # Holding the sole owner lock makes abandoned records detectable.
        for old in runs.iterdir():
            if not old.is_dir() or not re.fullmatch('[0-9a-f-]{36}', old.name): continue
            path = old / 'status.json'
            if not path.is_file(): continue
            previous = _decode(_read_metadata(path))
            if previous.get('state') in {'VALIDATING', 'CAPTURING', 'COMPARING'}:
                previous.update(state='INTERRUPTED', reason='OWNER_EXITED', updated_at_utc=now.isoformat())
                atomic_json(path, previous)
        run_id = str(uuid4()); folder = runs / run_id; folder.mkdir()
        status = dict(run_id=run_id, state='VALIDATING', reason=None, created_at_utc=now.isoformat(),
                      execution_allowed=False, market_edge_verified=False, historical_broker_conditions_verified=False)
        def update(state, reason=None):
            status.update(state=state, reason=reason, updated_at_utc=datetime.now(timezone.utc).isoformat())
            atomic_json(folder / 'status.json', status)
        update('VALIDATING')
        try:
            cfg = settings(config, now)
            manifest = verify_code(code_root, manifest_path, code_pin)
            status.update(config_sha256=digest(_encode(cfg)), code_manifest_sha256=code_pin,
                          declared_revision=manifest['declared_revision'], python_version=sys.version.split()[0])
            _write_exclusive(folder / 'settings.json', _encode(cfg))
            _write_exclusive(folder / 'code_manifest.json', _encode(manifest))
        except Exception:
            update('BLOCKED_CONFIG', 'CONFIG_OR_CODE_PIN'); return status
        try:
            def child(script, args):
                verify_code(code_root, manifest_path, code_pin)
                return launch([sys.executable, str(code_root / script), *args,
                               '--terminal-path', cfg['terminal_path']], cwd=code_root,
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                              timeout=cfg['stage_timeout_seconds'], check=False).returncode
            pilot_cfg = folder / 'pilot_settings.json'; account_cfg = folder / 'account_settings.json'
            _write_exclusive(pilot_cfg, _encode(cfg['pilot'])); _write_exclusive(account_cfg, _encode(cfg['account']))
            update('CAPTURING')
            rc = child('lsr03_mt5_pilot.py', ['--config', str(pilot_cfg), '--output', str(folder / 'capture')])
            if rc != 0:
                update('BLOCKED_DATA' if rc == 2 else 'FAILED', 'CAPTURE_QUALITY' if rc == 2 else 'CAPTURE_FAILED'); return status
            capture = folder / 'capture'; capture_pin = digest(_read_metadata(capture / 'run.json'))
            marker, _ = verify_pilot_bundle(capture, capture_pin)
            if marker['report_status'] != 'MATCHED_TICK_CANDIDATE_RESEARCH':
                update('BLOCKED_DATA', 'CAPTURE_STATUS'); return status
            status['capture_run_sha256'] = capture_pin
            update('COMPARING')
            rc = child('lsr03_mt5_account_pilot.py', ['--pilot', str(capture), '--pilot-run-sha256', capture_pin,
                '--config', str(account_cfg), '--output', str(folder / 'account')])
            if rc != 0:
                update('BLOCKED_DATA' if rc == 2 else 'FAILED', 'ACCOUNT_QUALITY' if rc == 2 else 'ACCOUNT_FAILED'); return status
            verify_code(code_root, manifest_path, code_pin)
            verify_pilot_bundle(capture, capture_pin)
            account = folder / 'account'; raw = _read_metadata(account / 'account_run.json'); result = _decode(raw)
            if (result.get('status') != 'DEMO_ACCOUNT_PILOT_CURRENT_SPEC_ESTIMATE_ONLY'
                or result.get('report_status') != 'CONFIRMATION_RETEST_INDEPENDENT_ACCOUNT_RESEARCH'
                or result.get('input_pilot_run_sha256') != capture_pin
                or result.get('catalog_sha256') != marker['catalog_sha256']
                or result.get('execution_allowed') is not False
                or set(result['files_sha256']) != {'account_settings.json', 'sequence.json', 'account_report.json'}):
                raise ValueError('Account completion mismatch')
            for name, pin in result['files_sha256'].items():
                _pin(pin)
                if digest(_read_metadata(account / name)) != pin: raise ValueError('Account file changed')
            if digest(_read_metadata(folder / 'settings.json')) != status['config_sha256']:
                raise ValueError('Settings changed')
            status['account_run_sha256'] = digest(raw)
            _write_exclusive(folder / 'job_complete.json', _encode(dict(status, state='COMPLETED_RESEARCH',
                historical_broker_conditions_verified=False)))
            update('COMPLETED_RESEARCH'); return status
        except subprocess.TimeoutExpired:
            update('FAILED', 'STAGE_TIMEOUT'); return status
        except Exception:
            update('FAILED', 'STAGE_OR_ARTIFACT_FAILED'); return status


def main(argv=None):
    p = argparse.ArgumentParser(description='One-shot read-only DEMO research worker')
    p.add_argument('--config', required=True); p.add_argument('--code-manifest', required=True)
    p.add_argument('--code-manifest-sha256', required=True)
    args = p.parse_args(argv)
    try:
        if sys.platform != 'win32': raise ValueError('Windows required')
        root = Path(os.environ['LOCALAPPDATA']) / 'ORRERYFX' / 'research'
        result = run_job(_decode(_read_metadata(args.config)), root, Path(__file__).resolve().parent,
                         args.code_manifest, args.code_manifest_sha256)
        print(_encode(result).decode(), end='')
        return 0 if result['state'] == 'COMPLETED_RESEARCH' else 2
    except Exception:
        print('{"state":"WORKER_UNAVAILABLE","execution_allowed":false}')
        return 1


if __name__ == '__main__': raise SystemExit(main())
