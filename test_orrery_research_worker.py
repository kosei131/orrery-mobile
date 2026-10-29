import json
from datetime import timedelta
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace as D
import unittest
from orrery_research_worker import run_job, worker_lock, digest, verify_code, atomic_json
from lsr04_tick_archive import _encode
from lsr03_mt5_pilot import run_pilot
from lsr03_mt5_account_pilot import run_account_pilot
from test_lsr03_mt5_account_pilot import MT5, config
import test_lsr03_mt5_pilot as fixture


class WorkerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve(); self.code = self.root / 'code'; self.code.mkdir()
        (self.code / 'lsr03_mt5_pilot.py').write_text('# injected child only')
        (self.code / 'lsr03_mt5_account_pilot.py').write_text('# injected child only')
        self.manifest = self.root / 'manifest.json'
        self.manifest.write_bytes(_encode(dict(declared_revision='a'*40,
            files_sha256={p.name:digest(p.read_bytes()) for p in self.code.glob('*.py')})))
        self.pin = digest(self.manifest.read_bytes()); self.runtime = self.root / 'runtime'
        self.terminal = self.root / 'terminal.exe'; self.terminal.touch()
        helper = fixture.PilotTests(); helper.setUp(); self.addCleanup(helper.temp.cleanup)
        self.cfg = dict(enabled=True, terminal_path=str(self.terminal), stage_timeout_seconds=30,
                        pilot=helper.config, account=dict(config(), round_trip_cost_per_lot_usd=1,
                                                        cost_source='SYNTHETIC_POSITIVE_COST'))
        self.mt5 = MT5(); self.calls = []

    def launch(self, command, **kwargs):
        self.calls.append(command)
        def arg(k): return command[command.index(k)+1]
        cfg = json.loads(Path(arg('--config')).read_bytes())
        if Path(command[1]).name == 'lsr03_mt5_pilot.py':
            run_pilot(self.mt5, cfg, arg('--output'), now_utc=fixture.END+timedelta(hours=1))
        else:
            run_account_pilot(self.mt5, arg('--pilot'), arg('--pilot-run-sha256'), cfg, arg('--output'))
        return D(returncode=0)

    def job(self, launch=None):
        return run_job(self.cfg, self.runtime, self.code, self.manifest, self.pin,
                       now=fixture.END+timedelta(hours=1), launch=launch or self.launch)

    def folder(self, result): return self.runtime / 'runs' / result['run_id']

    def test_existing_engines_complete_without_inventing_trades(self):
        r = self.job(); folder = self.folder(r)
        self.assertEqual(r['state'], 'COMPLETED_RESEARCH'); self.assertEqual(len(self.calls), 2)
        self.assertTrue((folder / 'job_complete.json').is_file())
        self.assertFalse(r['execution_allowed'])
        report = json.loads((folder / 'account' / 'account_report.json').read_bytes())
        for a in report['accounts'].values(): self.assertEqual(a['closed_statistics']['trades'], 0)
        status = (folder / 'status.json').read_text()
        self.assertNotIn(str(self.terminal), status); self.assertNotIn('FAKE_DEMO', status)

    def test_missing_or_zero_cost_blocks_before_child(self):
        for value in (None, 0):
            with self.subTest(value=value):
                self.cfg['account']['round_trip_cost_per_lot_usd'] = value
                r = self.job(); self.assertEqual(r['state'], 'BLOCKED_CONFIG')
                self.assertFalse((self.folder(r) / 'job_complete.json').exists())
        self.assertEqual(self.calls, [])

    def test_disabled_and_unsupported_symbol_block(self):
        self.cfg['enabled'] = False
        self.assertEqual(self.job()['state'], 'BLOCKED_CONFIG')
        self.cfg['enabled'] = True; self.cfg['pilot']['symbol'] = 'USDJPY'
        self.assertEqual(self.job()['state'], 'BLOCKED_CONFIG'); self.assertFalse(self.calls)

    def test_pin_or_inventory_change_blocks(self):
        (self.code / 'new_module.py').touch()
        self.assertEqual(self.job()['state'], 'BLOCKED_CONFIG'); self.assertFalse(self.calls)
        with self.assertRaises(ValueError): verify_code(self.code, self.manifest, '0'*64)

    def test_quality_failure_never_compares(self):
        calls = []
        def launch(*a, **kw): calls.append(a); return D(returncode=2)
        r = self.job(launch)
        self.assertEqual(r['state'], 'BLOCKED_DATA'); self.assertEqual(len(calls), 1)
        self.assertFalse((self.folder(r) / 'job_complete.json').exists())

    def test_timeout_is_failure_and_no_raw_exception_saved(self):
        def launch(*a, **kw): raise subprocess.TimeoutExpired('secret-account-id', 30)
        r = self.job(launch)
        self.assertEqual(r['reason'], 'STAGE_TIMEOUT'); self.assertEqual(r['state'], 'FAILED')
        self.assertNotIn('secret-account-id', (self.folder(r) / 'status.json').read_text())

    def test_exit_zero_without_marker_is_not_success(self):
        r = self.job(lambda *a, **kw: D(returncode=0))
        self.assertEqual(r['state'], 'FAILED'); self.assertFalse((self.folder(r) / 'job_complete.json').exists())

    def test_tampered_account_report_rejected(self):
        def launch(command, **kw):
            result = self.launch(command, **kw)
            if 'lsr03_mt5_account_pilot.py' in command[1]:
                p = Path(command[command.index('--output')+1]) / 'account_report.json'
                p.write_bytes(p.read_bytes()+b' ')
            return result
        r = self.job(launch)
        self.assertEqual(r['state'], 'FAILED'); self.assertFalse((self.folder(r) / 'job_complete.json').exists())

    def test_owner_lock_released_after_error(self):
        with worker_lock(self.runtime):
            with self.assertRaises(OSError): self.job()
        self.assertEqual(self.job()['state'], 'COMPLETED_RESEARCH')

    def test_restart_marks_abandoned_run_and_never_reuses_it(self):
        old = self.runtime / 'runs' / 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'; old.mkdir(parents=True)
        atomic_json(old / 'status.json', dict(state='CAPTURING'))
        r = self.job()
        self.assertEqual(json.loads((old/'status.json').read_bytes())['state'], 'INTERRUPTED')
        self.assertNotEqual(self.folder(r), old)
        r2 = self.job(); self.assertNotEqual(r['run_id'], r2['run_id'])
        self.assertEqual(json.loads((self.folder(r)/'status.json').read_bytes())['state'], 'COMPLETED_RESEARCH')

    def test_source_change_between_stages_stops_second_child(self):
        def launch(command, **kw):
            result = self.launch(command, **kw)
            (self.code / 'lsr03_mt5_pilot.py').write_text('# changed')
            return result
        r = self.job(launch)
        self.assertEqual(r['state'], 'FAILED'); self.assertEqual(len(self.calls), 1)

    def test_manifest_preparation_exclusive_and_detects_later_changes(self):
        from orrery_research_code_manifest import prepare
        path = self.root / 'prepared.json'
        pin = prepare(self.code, 'b'*40, path)
        self.assertEqual(verify_code(self.code, path, pin)['declared_revision'], 'b'*40)
        with self.assertRaises(FileExistsError): prepare(self.code, 'b'*40, path)
        (self.code / 'lsr03_mt5_pilot.py').write_text('# changed')
        with self.assertRaises(ValueError): verify_code(self.code, path, pin)

    def test_account_stage_quality_blocked(self):
        def launch(command, **kw):
            if 'lsr03_mt5_account_pilot.py' in command[1]: return D(returncode=2)
            return self.launch(command, **kw)
        r = self.job(launch); self.assertEqual(r['reason'], 'ACCOUNT_QUALITY')
        self.assertEqual(r['state'], 'BLOCKED_DATA')


if __name__ == '__main__': unittest.main()
