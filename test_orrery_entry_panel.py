import copy
from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest
from orrery_entry_panel import load_panel

PATH = Path('research_evidence/local-history-20261101/entry_opportunity_reaudit_20261102.json')


class EntryPanelTests(unittest.TestCase):
    def load(self, report):
        raw = json.dumps(report).encode()
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)/'report.json'; p.write_bytes(raw)
            return load_panel(p, sha256(raw).hexdigest())

    def test_real_archive_preserves_all_four_models_and_denominators(self):
        raw = PATH.read_bytes(); r = load_panel(PATH, sha256(raw).hexdigest())
        self.assertEqual(r['confirmation_universe'], 22)
        self.assertEqual(len(r['results']), 4)
        self.assertEqual(r['results']['CONFIRMATION_SWEEP_EXTREME']['entry_outcomes']['unresolved_or_unmodeled'], 9)
        self.assertEqual(r['results']['RETEST_SWEEP_EXTREME']['no_entry_reasons'], {'EXPIRED':11,'UNKNOWN_HISTORY':1})
        self.assertFalse(r['execution_allowed'])

    def test_hash_mismatch_rejected(self):
        with self.assertRaisesRegex(ValueError, 'hash'):
            load_panel(PATH, '0'*64)

    def test_rehashed_scope_and_account_claims_rejected(self):
        base = json.loads(PATH.read_bytes())
        for key in ('formal_lsr02','execution_allowed','adopted','out_of_sample'):
            r = copy.deepcopy(base); r[key] = True
            with self.subTest(key=key), self.assertRaises(ValueError):self.load(r)
        r = copy.deepcopy(base); r['net_expectancy_r'] = 0
        with self.assertRaises(ValueError):self.load(r)

    def test_rehashed_accounting_and_win_rate_corruption_rejected(self):
        base = json.loads(PATH.read_bytes())
        for section,key in (('entry_outcomes','resolved_outcomes'),('entry_outcomes','win_rate_pct'),
                            ('no_entry_reasons','EXPIRED'),('stop_policy_skip_counts','STRUCTURE_BREACHED_BEFORE_ENTRY')):
            r = copy.deepcopy(base); r['results']['RETEST_SWEEP_EXTREME'][section][key] += 1
            with self.subTest(key=key), self.assertRaises(ValueError):self.load(r)
        r = copy.deepcopy(base); del r['results']['RETEST_FIXED_6']
        with self.assertRaises(ValueError):self.load(r)

    def test_dashboard_cli_blocks_non_history_modes(self):
        import subprocess,sys
        for args in (['--entry-report',str(PATH)], ['--test-data','--entry-report',str(PATH),'--entry-report-sha256','0'*64]):
            p = subprocess.run([sys.executable,'mt5_local_dashboard.py',*args],capture_output=True,timeout=10)
            self.assertEqual(p.returncode,2)

if __name__ == '__main__': unittest.main()
