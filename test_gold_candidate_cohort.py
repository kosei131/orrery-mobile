import unittest
from orrery_gold_candidate_cohort import audit_cohort

PIN='a'*64
def candidate(i, **changes):
    x=dict(candidate_id=str(i),symbol='XAUUSD',source_sha256=PIN,
           entry_utc_ms=0,side='BUY',stop=990,
           targets={'small':1010,'normal':1030},
           quotes=[(0,1000,1005),(1000,1011,1016),(2000,989,994)])
    x.update(changes)
    return x

class CohortTests(unittest.TestCase):
    def test_same_candidate_both_targets(self):
        a=audit_cohort([candidate(1)],expected_tick_sha256=PIN)
        self.assertEqual(a['candidate_count'],1)
        self.assertEqual(a['target_status_counts']['small']['TARGET_OBSERVED'],1)
        self.assertEqual(a['target_status_counts']['normal']['STOP_OBSERVED'],1)
        self.assertIsNone(a['actual_win_rate_pct'])
        self.assertFalse(a['execution_allowed'])

    def test_missing_data_remains_counted(self):
        a=audit_cohort([candidate(1,quotes=None)],expected_tick_sha256=PIN)
        self.assertEqual(a['target_status_counts']['small']['CENSORED_QUOTES_UNAVAILABLE'],1)

    def test_source_mismatch_never_joins(self):
        a=audit_cohort([candidate(1,source_sha256='b'*64)],expected_tick_sha256=PIN)
        self.assertEqual(a['target_status_counts']['normal']['CENSORED_SOURCE_MISMATCH'],1)

    def test_mixed_status_denominator(self):
        a=audit_cohort([candidate(1),candidate(2,quotes=None)],expected_tick_sha256=PIN)
        self.assertEqual(a['candidate_count'],2)
        self.assertEqual(sum(a['target_status_counts']['small'].values()),2)

    def test_duplicate_rejected(self):
        with self.assertRaises(ValueError):
            audit_cohort([candidate(1),candidate(1)],expected_tick_sha256=PIN)

    def test_target_cohort_mismatch_rejected(self):
        with self.assertRaises(ValueError):
            audit_cohort([candidate(1),candidate(2,targets={'other':1030})],
                         expected_tick_sha256=PIN)

    def test_other_market_rejected(self):
        with self.assertRaises(ValueError):
            audit_cohort([candidate(1,symbol='USDJPY')],expected_tick_sha256=PIN)

    def test_bad_source_pin_rejected(self):
        with self.assertRaises(ValueError):
            audit_cohort([],expected_tick_sha256='not-a-hash')

    def test_same_second_ambiguity_preserved(self):
        q=[(0,1000,1005),(1000,1011,1016),(1000,989,994)]
        a=audit_cohort([candidate(1,quotes=q)],expected_tick_sha256=PIN)
        self.assertEqual(a['target_status_counts']['small']['AMBIGUOUS_SAME_SECOND'],1)

    def test_empty_cohort_not_win_rate(self):
        a=audit_cohort([],expected_tick_sha256=PIN)
        self.assertEqual(a['candidate_count'],0)
        self.assertEqual(a['target_status_counts'],{})
        self.assertIsNone(a['net_expectancy_r'])

if __name__=='__main__':
    unittest.main()
