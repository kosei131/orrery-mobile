import unittest
import test_h4_reconciliation_batch as fixture
from test_orrery_mt5_history_check import Feed
from orrery_h4_reconciliation_batch import run_batch,resume_batch
from orrery_h4_batch_chain import audit_chain

class ChainTests(unittest.TestCase):
    setUp=fixture.BatchTests.setUp
    def chain(self,empty=False):
        f=Feed();f.empty=empty;r=run_batch(f,**self.args)
        b=resume_batch(Feed(),previous=self.args['output'],previous_result_sha256=r['result_sha256'],
                      output=self.root/'next',max_chunks=1,now=self.args['now'])
        return [dict(path=str(self.args['output']),result_sha256=r['result_sha256']),
                dict(path=str(self.root/'next'),result_sha256=b['result_sha256'])]
    def test_contiguous_saved_prefix_and_remaining(self):
        r=audit_chain(self.chain())
        self.assertEqual(r['saved_unique_chunks'],3);self.assertEqual(r['remaining_chunks'],453)
        self.assertEqual(r['slots'][0]['status'],'PARTIAL')
        self.assertFalse(r['all_planned_chunks_saved']);self.assertFalse(r['backtest_ready'])
    def test_failed_retry_not_double_counted(self):
        r=audit_chain(self.chain(empty=True))
        self.assertEqual(r['blocked_attempts'],1);self.assertEqual(r['saved_unique_chunks'],1)
    def test_parent_omission_reordering_and_duplicates_rejected(self):
        chain=self.chain()
        for items in ([chain[1]],list(reversed(chain)),chain+[chain[0]]):
            with self.assertRaises(ValueError):audit_chain(items)
    def test_independent_runs_cannot_be_concatenated(self):
        chain=self.chain();r=run_batch(Feed(),**dict(self.args,output=self.root/'other'))
        chain.append(dict(path=str(self.root/'other'),result_sha256=r['result_sha256']))
        with self.assertRaises(ValueError):audit_chain(chain)
    def test_tampering_in_old_generation_blocks_chain(self):
        chain=self.chain();(self.args['output']/'progress-0000.json').unlink()
        with self.assertRaises(ValueError):audit_chain(chain)
    def test_empty_chain_not_complete(self):
        with self.assertRaises(ValueError):audit_chain([])
