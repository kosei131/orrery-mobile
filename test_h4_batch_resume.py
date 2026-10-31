import unittest
import test_h4_reconciliation_batch as fixture
from test_orrery_mt5_history_check import Feed
from orrery_h4_reconciliation_batch import run_batch,resume_batch
from orrery_h4_batch_verify import verify_batch

class ResumeTests(unittest.TestCase):
    setUp=fixture.BatchTests.setUp
    def resume(self,pin,feed=None):
        return resume_batch(Feed() if feed is None else feed,previous=self.args['output'],
            previous_result_sha256=pin,output=self.root/'resumed',max_chunks=1,now=self.args['now'])
    def test_continues_without_overwriting_old(self):
        r=run_batch(Feed(),**self.args);old=(self.args['output']/'batch_result.json').read_bytes()
        new=self.resume(r['result_sha256'])
        self.assertEqual(new['start_chunk'],2);self.assertEqual(new['saved_chunks'],1)
        self.assertEqual(new['parent_result_sha256'],r['result_sha256'])
        verify_batch(self.root/'resumed',expected_result_sha256=new['result_sha256'])
        self.assertEqual(old,(self.args['output']/'batch_result.json').read_bytes())
    def test_retries_failed_chunk_without_skipping(self):
        f=Feed();f.empty=True;r=run_batch(f,**self.args)
        new=self.resume(r['result_sha256']);self.assertEqual(new['start_chunk'],0)
    def test_different_account_refused_before_new_folder(self):
        r=run_batch(Feed(),**self.args);f=Feed();f.login=2
        with self.assertRaises(ValueError):self.resume(r['result_sha256'],f)
        self.assertFalse((self.root/'resumed').exists())
    def test_tampered_or_missing_receipt_refused(self):
        r=run_batch(Feed(),**self.args);(self.args['output']/'progress-0000.json').unlink()
        with self.assertRaises(ValueError):self.resume(r['result_sha256'])
    def test_real_account_refused(self):
        r=run_batch(Feed(),**self.args);f=Feed();f.mode=2
        with self.assertRaises(ValueError):self.resume(r['result_sha256'],f)
