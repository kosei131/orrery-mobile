import unittest

from orrery_gold_nested_wave_minute import minute_exit


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
