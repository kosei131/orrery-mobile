"""One local command: existing DEMO worker -> retained receipt -> audited summary.
No installer, scheduler, remote control, viewer startup or order capability.
"""
import argparse
from datetime import datetime, timezone
from pathlib import Path
import os
import subprocess
import sys
from uuid import uuid4
from orrery_research_worker import run_job, atomic_json, digest
from orrery_research_summary import build_summary, _uuid
from lsr04_tick_archive import _decode, _encode, _pin, _read_metadata, _write_exclusive

WORKER_STOPS = {'BLOCKED_CONFIG', 'BLOCKED_DATA', 'FAILED', 'INTERRUPTED'}


def run_session(config, runtime_root, code_root, manifest_path, code_pin, *, now=None, launch=subprocess.run):
    """Keep the worker return value before audit, separately from its run folder.

    The receipt is a same-PC reference, not an external signature or backup.
    One new session every time; no prefix result is silently resumed/adopted.
    """
    runtime_root = Path(runtime_root).resolve()
    code_root = Path(code_root).resolve()
    if runtime_root == code_root or code_root in runtime_root.parents:
        raise ValueError('Research data must be outside source checkout')
    config = _decode(_encode(config))
    sessions = runtime_root / 'sessions'; sessions.mkdir(parents=True, exist_ok=True)
    session_id = str(uuid4()); folder = sessions / session_id; folder.mkdir()
    state = dict(session_id=session_id, state='WORKER_RUNNING', execution_allowed=False,
                 market_edge_verified=False, historical_broker_conditions_verified=False)
    def update(value):
        state.update(state=value, updated_at_utc=datetime.now(timezone.utc).isoformat())
        atomic_json(folder / 'session_status.json', state)
    update('WORKER_RUNNING')
    try:
        receipt = run_job(config, runtime_root, code_root, manifest_path, code_pin, now=now, launch=launch)
        run_id = _uuid(receipt['run_id'])
        state['run_id'] = run_id
        update('SAVING_RECEIPT')
        raw = _encode(receipt); _write_exclusive(folder / 'receipt.json', raw)
        state['receipt_sha256'] = digest(raw)
        if receipt['state'] in WORKER_STOPS:
            update('WORKER_STOPPED'); return state
        if receipt['state'] != 'COMPLETED_RESEARCH': raise ValueError('Unexpected worker state')
        update('AUDITING')
        result = build_summary(runtime_root / 'runs' / run_id, receipt)
        raw_summary = _encode(result); _write_exclusive(folder / 'summary.json', raw_summary)
        state['summary_sha256'] = digest(raw_summary)
        if result['audit_status'] != 'CONSISTENT_RESEARCH_ARTIFACTS':
            update('AUDIT_BLOCKED'); return state
        if digest(_read_metadata(folder / 'receipt.json')) != state['receipt_sha256']:
            raise ValueError('Receipt changed')
        if digest(_read_metadata(folder / 'summary.json')) != state['summary_sha256']:
            raise ValueError('Summary changed')
        _write_exclusive(folder / 'session_complete.json', _encode(dict(state, state='COMPLETED_RESEARCH')))
        update('COMPLETED_RESEARCH'); return state
    except Exception:
        update('SESSION_FAILED'); return state


def session_settings(value):
    if not isinstance(value,dict) or set(value) != {'worker_settings_path','code_manifest_path','code_manifest_sha256'}:
        raise ValueError('Exact private session settings required')
    _pin(value['code_manifest_sha256'])
    for key in ('worker_settings_path','code_manifest_path'):
        if not isinstance(value[key],str) or not Path(value[key]).is_absolute():
            raise ValueError('Explicit absolute input paths required')
    return dict(value)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',required=True)
    args = parser.parse_args(argv)
    try:
        if sys.platform != 'win32' or sys.version_info[:2] != (3,12):
            raise ValueError('Windows Python 3.12 required')
        values = session_settings(_decode(_read_metadata(Path(args.config)).decode('utf-8-sig')))
        config = _decode(_read_metadata(Path(values['worker_settings_path'])).decode('utf-8-sig'))
        result = run_session(config, Path(os.environ['LOCALAPPDATA'])/'ORRERYFX'/'research',
            Path(__file__).resolve().parent, values['code_manifest_path'], values['code_manifest_sha256'])
        print(_encode(result).decode(),end='')
        return 0 if result['state'] == 'COMPLETED_RESEARCH' else 2
    except Exception:
        print('{"state":"SESSION_UNAVAILABLE","execution_allowed":false}')
        return 1


if __name__ == '__main__': raise SystemExit(main())
