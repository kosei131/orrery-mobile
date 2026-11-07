import copy
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from orrery_halftrend_panel import load_panel

EVIDENCE=Path('research_evidence/local-history-20261101/tradingview_halftrend_cohorts.json')

class PanelTests(unittest.TestCase):
    def setUp(self):
        self.report=json.loads(EVIDENCE.read_text())
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'study.json'
    def load(self, r=None):
        raw=json.dumps(self.report if r is None else r).encode()
        self.path.write_bytes(raw)
        return load_panel(self.path,sha256(raw).hexdigest())
    def test_received_result_preserves_unknown_and_cohorts(self):
        r=self.load()
        self.assertEqual(r['summaries']['LSR02']['candidates'],4)
        self.assertEqual(r['summaries']['HALFTREND_ALIGNED']['reference_losses'],1)
        self.assertIsNone(r['summaries']['LSR02']['account_return_pct'])
        self.assertNotIn('candidates',r)
    def test_pin_mismatch_rejected(self):
        self.path.write_bytes(EVIDENCE.read_bytes())
        with self.assertRaises(ValueError):load_panel(self.path,'0'*64)
    def test_changed_counts_rejected_even_with_new_pin(self):
        self.report['summaries']['LSR02']['reference_wins']=99
        with self.assertRaises(ValueError):self.load()
    def test_scope_escalation_or_missing_flags_rejected(self):
        for field in ('execution_allowed','halftrend_filter_adopted','reversal04_compared','independent_holdout','bid_ask_costs_verified','account_risk_controls_applied','tradingview_indicator_parity_verified'):
            for value in (True,None):
                r=copy.deepcopy(self.report);r[field]=value
                with self.subTest(field=field,value=value), self.assertRaises(ValueError):self.load(r)
    def test_unknown_cohort_and_missing_source_rejected(self):
        r=copy.deepcopy(self.report);r['candidates'][0]['halftrend_group']='OTHER'
        with self.assertRaises(ValueError):self.load(r)
        self.report['zip_sha256']=''
        with self.assertRaises(ValueError):self.load()
    def test_cannot_attach_to_mt5_or_simulation(self):
        r=subprocess.run([sys.executable,'mt5_local_dashboard.py','--test-data','--halftrend-report',str(EVIDENCE),'--halftrend-report-sha256',sha256(EVIDENCE.read_bytes()).hexdigest()],capture_output=True,text=True)
        self.assertEqual(r.returncode,2)
        self.assertIn('offline history only',r.stderr)

if __name__=='__main__':unittest.main()
