import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
import test_demo_order_check as fixture
from lsr04_tick_archive import _encode
from lsr04_demo_claims import initialize,claim

class ClaimTests(unittest.TestCase):
    def setUp(self):
        f=fixture.CheckTests();f.setUp();self.report=f.run_check(fixture.Broker())
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'claims.db'
        self.token=self.report['preflight']['draft_result']['draft']['snapshot']['account_token']
        initialize(self.path,account_token=self.token)
    def reserve(self,report=None,at=10002,candidate='M15:sweep:10000'):
        r=self.report if report is None else report
        return claim(self.path,candidate_id=candidate,checked_report=r,
            expected_report_sha256=sha256(_encode(r)).hexdigest(),now_msc=at)
    def test_persistent_claim_never_authorizes_and_duplicate_blocks(self):
        self.assertFalse(self.reserve()['execution_allowed'])
        with self.assertRaisesRegex(ValueError,'already claimed'):self.reserve()
    def test_quote_or_side_revision_cannot_bypass_same_candidate(self):
        self.reserve();r=deepcopy(self.report);r['request']['price']=101.
        with self.assertRaisesRegex(ValueError,'already claimed'):self.reserve(r)
    def test_concurrent_contenders_claim_once(self):
        def attempt(_):
            try:self.reserve();return True
            except ValueError:return False
        with ThreadPoolExecutor(max_workers=4) as pool:self.assertEqual(sum(pool.map(attempt,range(8))),1)
    def test_other_account_refused(self):
        r=deepcopy(self.report);r['preflight']['draft_result']['draft']['snapshot']['account_token']='a'*64
        with self.assertRaisesRegex(ValueError,'account or schema'):self.reserve(r)
    def test_expired_future_or_changed_report_refused(self):
        for at in (10000,15001):
            with self.assertRaises(ValueError):self.reserve(at=at)
        with self.assertRaisesRegex(ValueError,'pin mismatch'):
            claim(self.path,candidate_id='a',checked_report=self.report,expected_report_sha256='0'*64,now_msc=10002)
    def test_missing_or_corrupt_ledger_does_not_initialize(self):
        self.path.unlink()
        with self.assertRaises(ValueError):self.reserve()
        self.assertFalse(self.path.exists())
        self.path.write_bytes(b'broken')
        with self.assertRaises(ValueError):self.reserve()
        self.assertEqual(self.path.read_bytes(),b'broken')
    def test_explicit_initialize_never_overwrites(self):
        with self.assertRaises(FileExistsError):initialize(self.path,account_token=self.token)
