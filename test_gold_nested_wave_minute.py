import unittest

from orrery_gold_nested_wave_minute import audit_early_progress, audit_payoff, minute_exit


class MinuteExitTests(unittest.TestCase):
    def setUp(self):
        self.record = dict(known_at_utc=300, entry_open_reference='101',
                           structural_stop='98', target_reference='104',
                           state='AMBIGUOUS_SAME_M5')

    def test_minute_order_can_resolve_five_minute_ambiguity(self):
        bid = {300: dict(open=100, high=104, low=99, close=103),
               360: dict(open=103, high=103, low=97, close=99)}
        result = minute_exit(self.record, bid, end=900)
        self.assertEqual(result['state'], 'TARGET_REFERENCE')
        self.assertEqual(result['reference_r'], 1.0)

    def test_gap_and_same_minute_ambiguity_stay_unresolved(self):
        bar = dict(open=100, high=104, low=97, close=100)
        for bid, state in (({360: bar}, 'CENSORED_M1_GAP'),
                           ({300: bar}, 'AMBIGUOUS_SAME_M1')):
            result = minute_exit(self.record, bid, end=900)
            self.assertEqual(result['state'], state)
            self.assertIsNone(result['reference_r'])

    def test_payoff_audit_does_not_use_extreme_from_exit_bar(self):
        bid = {300: dict(open=100, high=102, low=99, close=100),
               360: dict(open=100, high=106, low=99, close=103)}
        exit_record = dict(minute_exit(self.record, bid, end=900), candidate_id='demo')
        audit = audit_payoff([exit_record], bid)
        self.assertEqual(audit['median_target_r'], 1.0)
        self.assertEqual(audit['records'][0]['observed_pre_exit_minutes'], 1)
        self.assertAlmostEqual(audit['records'][0]['best_bid_move_before_exit_bar_r'], 1/3)

    def test_landmarks_include_early_exit_and_keep_missing_path_unknown(self):
        closed = dict(self.record, candidate_id='closed', exit_m1_close=360, reference_r=1)
        missing = dict(self.record, candidate_id='missing', exit_m1_close=None, reference_r=None)
        reports = audit_early_progress([closed, missing], {}, end=3000)
        for report in reports:
            self.assertEqual(report['exited'], 1)
            self.assertEqual(report['unknown'], 1)
            self.assertEqual(report['median_reference_r'], 1)
