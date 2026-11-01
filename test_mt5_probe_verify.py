from hashlib import sha256
from pathlib import Path
import unittest

from lsr04_tick_archive import _decode, _encode
from orrery_mt5_candidate_probe import _request
from orrery_mt5_probe_verify import verify_probe, main, PROBE_SOURCES, HISTORY_SOURCES
import test_mt5_candidate_probe as fixture
from test_orrery_mt5_history_check import Feed


class ProbeVerifyTests(unittest.TestCase):
    def setUp(self):
        f=fixture.ProbeTests();f.setUp();self.addCleanup(f.doCleanups);self.f=f
        expected=_request(f.path,f.pin,f.now)
        expected['required_python_source_sha256']={n:sha256(Path(__file__).with_name(n).read_bytes()).hexdigest()
                                                   for n in PROBE_SOURCES|HISTORY_SOURCES}
        self.expected=f.root/'expected-request.json';self.expected.write_bytes(_encode(expected))
        self.expected_pin=sha256(self.expected.read_bytes()).hexdigest()
        self.result=f.probe();self.pin=sha256((f.output/'probe.json').read_bytes()).hexdigest()

    def verify(self, **changes):
        args=dict(probe_sha256=self.pin,expected_request=self.expected,expected_request_sha256=self.expected_pin,
                  reference=self.f.path,now=self.f.now)
        args.update(changes)
        return verify_probe(self.f.output,**args)

    def change_probe(self, change):
        p=self.f.output/'probe.json';r=_decode(p.read_bytes());change(r);p.write_bytes(_encode(r))
        self.pin=sha256(p.read_bytes()).hexdigest()

    def change_history(self, change):
        p=self.f.output/'history/history_check.json';r=_decode(p.read_bytes());change(r);p.write_bytes(_encode(r))
        self.change_probe(lambda probe:probe.update(history=r,history_receipt_sha256=sha256(p.read_bytes()).hexdigest()))

    def test_matching_receipts_recompute_local_bytes_without_profit_or_authentication(self):
        r=self.verify()
        self.assertEqual(r['rows'],600)
        self.assertEqual(r['status'],'VERIFIED_LOCAL_PROBE_ONLY_REVIEW_REQUIRED')
        self.assertTrue(r['local_bytes_recomputed']);self.assertTrue(r['expected_source_pins_match'])
        for k in ('broker_authenticity_verified','live_demo_account_verified','mt5_feed_matches_tradingview_verified',
                  'full_trade_history_complete','backtest_ready','execution_allowed'):
            self.assertFalse(r[k])
        self.assertIsNone(r['actual_profit_usd']);self.assertIsNone(r['commission_per_lot_usd'])

    def test_independent_probe_and_request_pins_are_required(self):
        for kw in (dict(probe_sha256='0'*64),dict(expected_request_sha256='0'*64)):
            with self.assertRaises(ValueError):self.verify(**kw)

    def test_changed_reference_or_raw_ticks_cannot_pass(self):
        original=self.f.path.read_bytes();self.f.path.write_bytes(original+b' ')
        with self.assertRaises(ValueError):self.verify()
        self.f.path.write_bytes(original)
        tick=self.f.output/'history/archive/ticks.jsonl'
        tick.write_bytes(tick.read_bytes().replace(b'2000.0',b'2001.0',1))
        with self.assertRaises(ValueError):self.verify()

    def test_self_consistent_rehash_does_not_change_candidate_request(self):
        p=self.f.output/'request.json';r=_decode(p.read_bytes());r['candidate_id']='XAUUSD:wrong:SELL'
        p.write_bytes(_encode(r))
        self.change_probe(lambda probe:probe.update(request_sha256=sha256(p.read_bytes()).hexdigest(),candidate_id=r['candidate_id']))
        with self.assertRaisesRegex(ValueError,'request differs'):self.verify()

    def test_source_hash_cannot_be_changed_with_receipt(self):
        self.change_probe(lambda r:r['source_sha256'].update({'orrery_mt5_candidate_probe.py':'0'*64}))
        with self.assertRaisesRegex(ValueError,'Source implementation'):self.verify()

    def test_fake_zero_fee_and_promoted_permissions_are_rejected(self):
        self.change_probe(lambda r:r.update(commission_per_lot_usd=0))
        with self.assertRaisesRegex(ValueError,'unknown'):self.verify()
        self.change_probe(lambda r:r.update(commission_per_lot_usd=None,backtest_ready=True))
        with self.assertRaisesRegex(ValueError,'unverified'):self.verify()

    def test_nested_row_count_is_checked_against_recomputed_stream(self):
        self.change_history(lambda h:h.update(rows=601))
        with self.assertRaisesRegex(ValueError,'count/quality'):self.verify()

    def test_rehashed_history_policy_cannot_change_dates(self):
        p=self.f.output/'history/request.json';r=_decode(p.read_bytes());r['start_utc']='2026-10-29T03:30:00+00:00'
        p.write_bytes(_encode(r))
        self.change_history(lambda h:h.update(request_sha256=sha256(p.read_bytes()).hexdigest()))
        with self.assertRaisesRegex(ValueError,'policy differs'):self.verify()

    def test_extra_files_and_incomplete_directory_are_not_ignored(self):
        (self.f.output/'unreviewed.txt').write_text('extra')
        with self.assertRaisesRegex(ValueError,'complete probe'):self.verify()

    def test_blocked_quality_remains_blocked_even_with_matching_hashes(self):
        feed=Feed();feed.spread=2;output=self.f.root/'blocked'
        r=self.f.probe(feed,output=output);pin=sha256((output/'probe.json').read_bytes()).hexdigest()
        result=verify_probe(output,probe_sha256=pin,expected_request=self.expected,
            expected_request_sha256=self.expected_pin,reference=self.f.path,now=self.f.now)
        self.assertEqual(result['status'],'BLOCKED_LOCAL_PROBE_QUALITY')
        self.assertFalse(result['backtest_ready'])
        # Even if every outer hash is updated, quality failure cannot become success.
        p=output/'probe.json';receipt=_decode(p.read_bytes());receipt['status']='DEMO_CANDIDATE_PROBE_SAVED_REVIEW_REQUIRED'
        p.write_bytes(_encode(receipt))
        with self.assertRaisesRegex(ValueError,'relabelled'):
            verify_probe(output,probe_sha256=sha256(p.read_bytes()).hexdigest(),expected_request=self.expected,
                expected_request_sha256=self.expected_pin,reference=self.f.path,now=self.f.now)

    def test_receipt_shape_rejects_extra_claims_even_with_updated_hash(self):
        # A new field in the returned receipt must not silently expand the trusted contract.
        self.change_probe(lambda r:r.update(verified_net_profit_usd=50000))
        with self.assertRaisesRegex(ValueError,'Supported probe receipt required'):
            self.verify()

    def test_missing_history_archive_is_not_treated_as_zero_trades(self):
        # Missing observations are not zero-profit observations.
        (self.f.output/'history/archive/ticks.jsonl').unlink()
        with self.assertRaises(ValueError):
            self.verify()

    def test_cli_preserves_receipts_and_refuses_existing_output(self):
        out=self.f.root/'verification.json';original=(self.f.output/'probe.json').read_bytes()
        args=['--folder',str(self.f.output),'--probe-sha256',self.pin,'--expected-request',str(self.expected),
              '--expected-request-sha256',self.expected_pin,'--reference',str(self.f.path),'--output',str(out)]
        self.assertEqual(main(args),0)
        self.assertFalse(_decode(out.read_bytes())['execution_allowed'])
        self.assertEqual((self.f.output/'probe.json').read_bytes(),original)
        with self.assertRaises(FileExistsError):main(args)

    def test_cli_cannot_add_verification_output_inside_original_bundle(self):
        out=self.f.output/'verification.json'
        args=['--folder',str(self.f.output),'--probe-sha256',self.pin,'--expected-request',str(self.expected),
              '--expected-request-sha256',self.expected_pin,'--reference',str(self.f.path),'--output',str(out)]
        with self.assertRaisesRegex(ValueError,'outside input bundle'):main(args)
        self.assertFalse(out.exists())


if __name__=='__main__':unittest.main()
