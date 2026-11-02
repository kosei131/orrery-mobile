import unittest
from orrery_barrier_cost_sensitivity import compare

def row(status,target=2):
    return dict(status=status,target_r=target,execution_allowed=False)

class CostSensitivityTests(unittest.TestCase):
    def test_net_cost_sensitivity_is_not_real_account_pnl(self):
        v=compare([row('TP_FIRST'),row('SL_FIRST')],estimated_cost_r=.2)
        self.assertAlmostEqual(v['resolved_only_gross_mean_r'],.5)
        self.assertAlmostEqual(v['resolved_only_cost_adjusted_mean_r'],.3)
        self.assertAlmostEqual(v['full_cohort_cost_adjusted_mean_r'],.3)
        self.assertIsNone(v['actual_net_expectancy_r'])
        self.assertFalse(v['execution_allowed'])

    def test_censor_or_ambiguous_blocks_full_cohort_result(self):
        v=compare([row('TP_FIRST'),row('AMBIGUOUS_SAME_BAR'),row('CENSORED_HORIZON')],estimated_cost_r=.1)
        self.assertEqual(v['unresolved'],2)
        self.assertIsNone(v['full_cohort_cost_adjusted_mean_r'])

    def test_invalid_cost_and_imaginary_target_rejected(self):
        with self.assertRaises(ValueError):compare([row('TP_FIRST')],estimated_cost_r=-1)
        with self.assertRaises(ValueError):compare([row('TP_FIRST',0)],estimated_cost_r=0)
        with self.assertRaises(ValueError):compare([dict(row('SL_FIRST'),execution_allowed=True)],estimated_cost_r=.1)
if __name__=='__main__':unittest.main()
