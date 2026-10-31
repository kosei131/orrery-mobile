import unittest,tempfile
from pathlib import Path
from datetime import datetime,timezone
from unittest.mock import patch
from test_orrery_mt5_history_check import Feed
from orrery_h4_reconciliation_plan import save_plan
from orrery_h4_reconciliation_batch import run_batch

class BatchTests(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup);self.root=Path(t.name)
        r=save_plan(self.root/'plan');self.args=dict(plan_path=self.root/'plan/request.json',
            plan_sha256=r['request_sha256'],output=self.root/'out',max_chunks=2,
            now=datetime(2026,10,30,tzinfo=timezone.utc))
    def test_two_chunks_preserved_without_full_history_claim(self):
        r=run_batch(Feed(),**self.args)
        self.assertEqual(r['saved_chunks'],2);self.assertFalse(r['completeness_verified'])
        self.assertFalse(r['full_plan_attempted']);self.assertFalse(r['execution_allowed'])
        self.assertTrue((self.root/'out/progress-0001.json').exists())
    def test_real_account_never_writes_output(self):
        f=Feed();f.mode=2
        with self.assertRaises(ValueError):run_batch(f,**self.args)
        self.assertFalse(self.args['output'].exists())
    def test_empty_stops_and_records_failure(self):
        f=Feed();f.empty=True;r=run_batch(f,**self.args)
        self.assertEqual(r['status'],'BLOCKED_BATCH');self.assertEqual(r['saved_chunks'],0)
        self.assertEqual(r['failed_chunk_id'],0)
    def test_quality_block_and_switch_are_not_success(self):
        for kind in ('switch','spread'):
            f=Feed();setattr(f,kind,True if kind=='switch' else 2.)
            args=dict(self.args,output=self.root/kind)
            r=run_batch(f,**args);self.assertEqual(r['status'],'BLOCKED_BATCH')
    def test_tampered_plan_never_contacts_account(self):
        self.args['plan_path'].write_text('{}')
        with self.assertRaises(ValueError):run_batch(object(),**self.args)
    def test_existing_output_is_preserved(self):
        run_batch(Feed(),**self.args)
        with self.assertRaises(FileExistsError):run_batch(Feed(),**self.args)
