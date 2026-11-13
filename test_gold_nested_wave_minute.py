import unittest

from orrery_gold_nested_wave_minute import audit_early_exit, audit_early_progress, audit_payoff, minute_exit


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

    def test_early_exit_uses_next_open_and_requires_observation(self):
        row = dict(self.record, candidate_id='one', reference_r=1)
        progress = [dict(minutes=5, records=[dict(candidate_id='one',
                                                   status='OPEN_AT_LANDMARK', reference_r=-0.1)])]
        observed = audit_early_exit([row], progress, {600: dict(open=99)}, end=1200)[0]
        self.assertAlmostEqual(observed['changes'][0]['early_exit_r'], -2/3)
        self.assertEqual(observed['baseline_winners_reduced'], 1)
        missing = audit_early_exit([row], progress, {}, end=1200)[0]
        self.assertEqual(missing['summary']['resolved'], 0)

    def test_sell_respects_ask_order_and_adverse_open(self):
        record = dict(self.record, side='SELL', structural_stop='104', target_reference='98')
        ask = {300: dict(open=102, high=103, low=98, close=99),
               360: dict(open=105, high=106, low=104, close=105)}
        result = minute_exit(record, ask, end=900)
        self.assertEqual(result['state'], 'TARGET_REFERENCE')
        self.assertEqual(result['reference_r'], 1)
        adverse = minute_exit(record, {300: ask[360]}, end=900)
        self.assertEqual(adverse['state'], 'ADVERSE_OPEN_REFERENCE')
        self.assertAlmostEqual(adverse['reference_r'], -4/3)

    def test_timeout_audit_uses_ask_low_for_sell_and_rejects_gaps(self):
        from orrery_gold_ab_archive_minutes import audit_timeout

        record = dict(self.record, candidate_id='sell', side='SELL',
                      structural_stop='104', target_reference='98',
                      exit_m1_close=7500, reference_r=0)
        prices = {t: dict(open=101, high=102, low=100, close=101)
                  for t in range(300, 7500, 60)}
        prices[360]['low'] = 99
        result = audit_timeout(record, prices)
        self.assertEqual(result['peak_minute_close'], 2)
        self.assertAlmostEqual(result['target_fraction_at_peak'], 2/3)
        del prices[300]
        with self.assertRaisesRegex(ValueError, 'Complete'):
            audit_timeout(record, prices)
