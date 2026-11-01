import tempfile
import unittest
from pathlib import Path
import test_demo_order_check as fixture
from lsr04_demo_claims import initialize
from lsr04_demo_account_context import create_context,inspect_bound,check_and_claim

class ContextTests(unittest.TestCase):
    def setUp(self):
        f=fixture.CheckTests();f.setUp();self.args=f.args
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'context.json';self.db=Path(self.tmp.name)/'claims.db'
        self.saved=create_context(fixture.Broker(),self.path)
        initialize(self.db,account_token=self.saved['account_token'])
    def inspect(self,b=None,**extra):
        return inspect_bound(b or fixture.Broker(),context_path=self.path,
            expected_context_sha256=self.saved['context_sha256'],clock_msc=lambda:10001,**dict(self.args,**extra))
    def reserve(self,b=None):
        return check_and_claim(b or fixture.Broker(),context_path=self.path,
            expected_context_sha256=self.saved['context_sha256'],ledger_path=self.db,
            candidate_id='M15:sweep:10000',clock_msc=lambda:10001,**self.args)
    def test_restarted_adapter_keeps_identity_without_exporting_nonce(self):
        a=self.inspect();b=self.inspect()
        self.assertEqual(a,b)
        self.assertNotIn('nonce',str(a));self.assertNotIn('PRIVATE',str(a))
        self.assertNotIn('PRIVATE',self.path.read_text())
        self.assertEqual(a['preflight']['draft_result']['draft']['snapshot']['account_token'],self.saved['account_token'])
    def test_complete_check_and_reservation_blocks_repeat_after_restart(self):
        first=self.reserve();self.assertFalse(first['execution_allowed'])
        self.assertFalse(first['reservation']['broker_order_sent'])
        with self.assertRaisesRegex(ValueError,'already claimed'):self.reserve(fixture.Broker())
    def test_changed_demo_account_and_real_account_stop_before_check(self):
        class Other(fixture.Broker):
            def account_info(self):
                a=super().account_info();a.login=2;return a
        for b in (Other(),fixture.Broker()):
            if type(b) is fixture.Broker:b.mode=2
            with self.assertRaises(ValueError):self.inspect(b)
            self.assertEqual(b.calls,[])
    def test_missing_or_modified_context_never_recreated(self):
        self.path.unlink()
        with self.assertRaises(ValueError):self.inspect()
        self.assertFalse(self.path.exists())
        self.path.write_bytes(b'broken')
        with self.assertRaises(ValueError):self.inspect()
        self.assertEqual(self.path.read_bytes(),b'broken')
    def test_explicit_creation_never_overwrites(self):
        old=self.path.read_bytes()
        with self.assertRaises(FileExistsError):create_context(fixture.Broker(),self.path)
        self.assertEqual(self.path.read_bytes(),old)
    def test_caller_cannot_override_persisted_nonce(self):
        with self.assertRaisesRegex(ValueError,'persisted'):self.inspect(account_nonce='a'*64)
    def test_context_change_during_check_refused(self):
        path=self.path
        class Changed(fixture.Broker):
            def order_check(self,req):
                r=super().order_check(req);path.write_bytes(b'broken');return r
        with self.assertRaises(ValueError):self.reserve(Changed())
        # No reservation was made before all context checks passed.
        import sqlite3
        db=sqlite3.connect(self.db)
        try:self.assertEqual(db.execute('SELECT count(*) FROM claims').fetchone()[0],0)
        finally:db.close()
    def test_final_context_review_expiry_blocks_claim(self):
        ticks=iter((10001,10001,10001,15001))
        with self.assertRaisesRegex(ValueError,'expired'):
            check_and_claim(fixture.Broker(),context_path=self.path,
                expected_context_sha256=self.saved['context_sha256'],ledger_path=self.db,
                candidate_id='late',clock_msc=lambda:next(ticks),**self.args)
