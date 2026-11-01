import tempfile,unittest,json
from pathlib import Path
from datetime import datetime,timezone
from test_orrery_mt5_history_check import Feed
from orrery_h4_pc_workflow import workflow

class WorkflowTests(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup);self.root=Path(t.name)/'new'
        self.args=dict(output=self.root,now=datetime(2026,10,31,tzinfo=timezone.utc))
    def test_default_never_accesses_terminal(self):
        r=workflow(mt5=object(),**self.args)
        self.assertEqual(r['status'],'PREPARED_NOT_EXECUTED')
        self.assertFalse(r['acquisition_attempted']);self.assertFalse((self.root/'batch').exists())
    def test_execute_intake_verify_and_chain(self):
        r=workflow(execute=True,mt5=Feed(),max_chunks=2,**self.args)
        self.assertEqual(r['saved_chunks'],2);self.assertEqual(r['remaining_chunks'],454)
        self.assertEqual(r['status'],'REQUESTED_CHUNKS_VERIFIED_REVIEW_REQUIRED')
        self.assertTrue((self.root/'chain_review.json').exists());self.assertFalse(r['backtest_ready'])
    def test_empty_history_remains_blocked(self):
        f=Feed();f.empty=True;r=workflow(execute=True,mt5=f,**self.args)
        self.assertEqual(r['status'],'BLOCKED_WORKFLOW');self.assertEqual(r['saved_chunks'],0)
    def test_real_account_blocked_without_ticks(self):
        f=Feed();f.mode=2;r=workflow(execute=True,mt5=f,**self.args)
        self.assertEqual(r['status'],'BLOCKED_WORKFLOW');self.assertFalse((self.root/'batch').exists())
    def test_no_overwrite(self):
        workflow(**self.args);before=(self.root/'workflow_result.json').read_bytes()
        with self.assertRaises(FileExistsError):workflow(**self.args)
        self.assertEqual(before,(self.root/'workflow_result.json').read_bytes())
    def test_invalid_count_before_writes(self):
        with self.assertRaises(ValueError):workflow(max_chunks=0,**self.args)
        self.assertFalse(self.root.exists())
