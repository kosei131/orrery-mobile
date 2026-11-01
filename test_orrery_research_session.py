import json
from pathlib import Path
from datetime import timedelta
import subprocess
import unittest
from unittest.mock import patch
from orrery_research_session import run_session, session_settings
from lsr04_tick_archive import _encode
import test_orrery_research_worker as fixture


class SessionTests(unittest.TestCase):
    def setUp(self):
        self.f = fixture.WorkerTests(); self.f.setUp(); self.addCleanup(self.f.doCleanups)

    def call(self, launch=None):
        return run_session(self.f.cfg, self.f.runtime, self.f.code, self.f.manifest, self.f.pin,
            now=fixture.fixture.END+timedelta(hours=1), launch=launch or self.f.launch)

    def folder(self, result): return self.f.runtime/'sessions'/result['session_id']

    def test_one_command_existing_worker_receipt_audit_and_summary(self):
        result=self.call(); folder=self.folder(result)
        self.assertEqual(result['state'],'COMPLETED_RESEARCH')
        self.assertTrue((folder/'session_complete.json').is_file())
        receipt=json.loads((folder/'receipt.json').read_bytes())
        self.assertEqual(receipt['run_id'],result['run_id'])
        self.assertNotEqual(folder,self.f.runtime/'runs'/receipt['run_id'])
        summary=json.loads((folder/'summary.json').read_bytes())
        self.assertEqual(summary['accounts']['CONFIRMATION']['closed_trades'],0)
        self.assertIsNone(summary['accounts']['RETEST']['win_rate_fraction'])
        self.assertFalse(result['execution_allowed'])
        self.assertNotIn(str(self.f.terminal),json.dumps(result))

    def test_missing_cost_retains_stopped_receipt_without_false_completion(self):
        self.f.cfg['account']['round_trip_cost_per_lot_usd']=None
        r=self.call(); folder=self.folder(r)
        self.assertEqual(r['state'],'WORKER_STOPPED')
        self.assertEqual(json.loads((folder/'receipt.json').read_bytes())['state'],'BLOCKED_CONFIG')
        self.assertFalse((folder/'session_complete.json').exists()); self.assertFalse(self.f.calls)

    def test_timeout_retains_failure_not_metrics(self):
        def launch(*a,**kw): raise subprocess.TimeoutExpired('private-server',1)
        r=self.call(launch); folder=self.folder(r)
        self.assertEqual(r['state'],'WORKER_STOPPED')
        self.assertNotIn('private-server',(folder/'receipt.json').read_text())
        self.assertFalse((folder/'summary.json').exists())

    def test_audit_failure_never_creates_session_complete(self):
        with patch('orrery_research_session.build_summary',return_value=dict(audit_status='AUDIT_BLOCKED',accounts=None)):
            r=self.call()
        self.assertEqual(r['state'],'AUDIT_BLOCKED')
        self.assertFalse((self.folder(r)/'session_complete.json').exists())

    def test_receipt_saved_before_audit_and_tamper_stops(self):
        from orrery_research_summary import build_summary
        def audit(folder,receipt):
            session=next((self.f.runtime/'sessions').iterdir())
            self.assertTrue((session/'receipt.json').is_file())
            value=build_summary(folder,receipt)
            p=session/'receipt.json'; p.write_bytes(p.read_bytes()+b' ')
            return value
        with patch('orrery_research_session.build_summary',side_effect=audit): r=self.call()
        self.assertEqual(r['state'],'SESSION_FAILED')
        self.assertFalse((self.folder(r)/'session_complete.json').exists())

    def test_repeated_runs_have_exclusive_folders(self):
        a=self.call(); marker=(self.folder(a)/'session_complete.json').read_bytes()
        b=self.call(); self.assertNotEqual(a['session_id'],b['session_id'])
        self.assertNotEqual(a['run_id'],b['run_id'])
        self.assertEqual((self.folder(a)/'session_complete.json').read_bytes(),marker)

    def test_runtime_inside_source_is_rejected(self):
        with self.assertRaises(ValueError):
            run_session(self.f.cfg,self.f.code/'runtime',self.f.code,self.f.manifest,self.f.pin)
        self.assertFalse((self.f.code/'runtime').exists())

    def test_empty_template_and_relative_paths_block(self):
        with self.assertRaises(ValueError): session_settings(json.loads(Path('research_session_settings.example.json').read_bytes()))
        with self.assertRaises(ValueError):
            session_settings(dict(worker_settings_path='relative.json',code_manifest_path=str(self.f.manifest),code_manifest_sha256=self.f.pin))


if __name__ == '__main__': unittest.main()
