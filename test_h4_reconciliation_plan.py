import unittest,tempfile,json,hashlib
from pathlib import Path
from datetime import datetime
from orrery_h4_reconciliation_plan import build_plan,save_plan

class PlanTests(unittest.TestCase):
    def test_deduplication_and_exact_ten_minute_tiling(self):
        p=build_plan();self.assertEqual(len(p['slots']),19);self.assertEqual(len(p['tick_chunks']),456)
        self.assertEqual(len({s['end_utc_exclusive'] for s in p['slots']}),19)
        for s in p['slots']:
            chunks=[c for c in p['tick_chunks'] if c['slot_id']==s['id']]
            self.assertEqual(chunks[0]['start_utc'],s['start_utc'])
            self.assertEqual(chunks[-1]['end_utc_exclusive'],s['end_utc_exclusive'])
            for a,b in zip(chunks,chunks[1:]):self.assertEqual(a['end_utc_exclusive'],b['start_utc'])
            for c in chunks:self.assertEqual((datetime.fromisoformat(c['end_utc_exclusive'])-datetime.fromisoformat(c['start_utc'])).total_seconds(),600)
    def test_plan_is_not_acquisition_or_market_session_proof(self):
        p=build_plan()
        for k in ('terminal_connected','history_acquired','backtest_ready','execution_allowed'):
            self.assertIs(p[k],False)
        self.assertTrue(all(s['expected_m1_count'] is None for s in p['slots']))
    def test_receipt_pins_request_and_prevents_overwrite(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'new';r=save_plan(root);raw=(root/'request.json').read_bytes()
            self.assertEqual(r['request_sha256'],hashlib.sha256(raw).hexdigest())
            self.assertEqual(json.loads(raw),build_plan())
            with self.assertRaises(FileExistsError):save_plan(root)
            self.assertEqual(raw,(root/'request.json').read_bytes())
