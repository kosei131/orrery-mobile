import copy
import unittest
from orrery_gold_m15_reference_outcomes import measure
from orrery_gold_m15_report_audit import audit

def b(n,o=1000,h=1010,l=990,c=1000):
    return dict(close_time=n*900,open=o*1000000,high=h*1000000,low=l*1000000,close=c*1000000)
def s(n=1):
    return dict(candidate_id='sig'+str(n),family='TREND_CONTINUATION',side='BUY',signal_known_at=n*900,entry_price_scaled=None,outcome_r=None)

class AuditTests(unittest.TestCase):
    def setUp(self):
        self.report=measure([b(1),b(2,h=1010,l=997),b(3)], [s()])
    def test_valid_report(self):
        self.assertEqual(audit(self.report)['candidate_count'],1)
    def test_missing_candidates(self):
        d=copy.deepcopy(self.report);d['cohorts']['TREND_CONTINUATION']['candidates']=0
        with self.assertRaises(ValueError):audit(d)
    def test_nonresolved_must_remain_unknown(self):
        d=copy.deepcopy(self.report);d['candidates'][0]['reference_r']=0
        with self.assertRaises(ValueError):audit(d)
    def test_fake_profit_not_accepted(self):
        d=copy.deepcopy(self.report);d['net_expectancy_r']=1.5
        with self.assertRaises(ValueError):audit(d)
    def test_wrong_positive_count(self):
        d=copy.deepcopy(self.report);d['cohorts']['TREND_CONTINUATION']['positive']=9
        with self.assertRaises(ValueError):audit(d)
    def test_corrupted_win_percent(self):
        d=copy.deepcopy(self.report);d['cohorts']['TREND_CONTINUATION']['observed_positive_pct']=95
        with self.assertRaises(ValueError):audit(d)
    def test_missing_family_rejected(self):
        d=copy.deepcopy(self.report);d['cohorts'].pop('SWEEP_REVERSAL')
        with self.assertRaises(ValueError):audit(d)
    def test_duplicate_candidate_ids_rejected(self):
        d=copy.deepcopy(self.report);d['candidates'].append(copy.deepcopy(d['candidates'][0]))
        with self.assertRaises(ValueError):audit(d)

if __name__=='__main__':
    unittest.main()
