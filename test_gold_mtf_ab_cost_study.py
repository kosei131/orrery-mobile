import unittest

from orrery_gold_mtf_ab_cost_study import summarize


class GoldCostStudyTests(unittest.TestCase):
    def test_cost_uses_each_stop_width_and_keeps_censored_candidate(self):
        rows = [
            dict(reference_r=1, entry_open_reference='2000', structural_stop='1999'),
            dict(reference_r=-0.5, entry_open_reference='2000', structural_stop='2003'),
            dict(reference_r=None, candidate_id='gap'),
        ]
        result = summarize(rows)
        self.assertEqual(result['unresolved_ids'], ['gap'])
        self.assertEqual(result['resolved'], 2)
        self.assertAlmostEqual(result['break_even_flat_cost_price'], 0.375)
        self.assertAlmostEqual(result['scenarios'][1]['mean_adjusted_reference_r'], 0.05)
        self.assertAlmostEqual(result['scenarios'][1]['unresolved_average_r_for_all_candidate_break_even'], -0.1)

    def test_unresolved_only_group_has_no_estimated_performance(self):
        result = summarize([dict(reference_r=None, candidate_id='gap')])
        self.assertIsNone(result['break_even_flat_cost_price'])
        self.assertIsNone(result['scenarios'][0]['mean_adjusted_reference_r'])
