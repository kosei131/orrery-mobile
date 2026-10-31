from pathlib import Path
import unittest
import test_h4_reconciliation_batch as fixture
from test_orrery_mt5_history_check import Feed
from orrery_h4_reconciliation_batch import run_batch
from orrery_h4_batch_verify import verify_batch

class VerifyTests(unittest.TestCase):
    setUp=fixture.BatchTests.setUp
    def batch(self,empty=False):
        f=Feed();f.empty=empty;r=run_batch(f,**self.args)
        return r['result_sha256']
    def test_rechecks_ticks_and_plan_offline(self):
        pin=self.batch();r=verify_batch(self.args['output'],expected_result_sha256=pin)
        self.assertEqual(r['saved_chunks'],2);self.assertFalse(r['restart_allowed'])
    def test_missing_and_extra_progress_rejected(self):
        pin=self.batch();(self.args['output']/'progress-0000.json').unlink()
        with self.assertRaises(ValueError):verify_batch(self.args['output'],expected_result_sha256=pin)
    def test_tampered_ticks_rejected(self):
        pin=self.batch();folder=self.args['output']/'chunk-0000/archive'
        p=next(p for p in folder.rglob('*') if p.is_file());p.write_bytes(b'changed')
        with self.assertRaises(ValueError):verify_batch(self.args['output'],expected_result_sha256=pin)
    def test_changed_receipt_or_wrong_pin_rejected(self):
        pin=self.batch();(self.args['output']/'batch_result.json').write_text('{}')
        with self.assertRaises(ValueError):verify_batch(self.args['output'],expected_result_sha256=pin)
    def test_blocked_batch_remains_blocked(self):
        pin=self.batch(empty=True);r=verify_batch(self.args['output'],expected_result_sha256=pin)
        self.assertEqual(r['batch_status'],'BLOCKED_BATCH');self.assertEqual(r['saved_chunks'],0)
