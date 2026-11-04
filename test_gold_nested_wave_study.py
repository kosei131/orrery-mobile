import unittest

from orrery_gold_nested_wave_study import complete_hours, wait_for_resume


class NestedWaveTests(unittest.TestCase):
    def test_partial_hour_is_not_context(self):
        bars = [dict(open_time=i*900, open=100, close=101, high=103, low=99)
                for i in (0, 1, 3)]
        self.assertEqual(complete_hours(bars), {})

    def test_resume_requires_prior_pullback_and_closed_break(self):
        origin = dict(close=103, low=100, high=104)
        bars = {900: dict(close=105, low=102, high=106),
                1800: dict(close=103, low=101, high=105),
                2700: dict(close=104, low=102, high=107),
                3600: dict(close=106, low=103, high=107)}
        self.assertEqual(wait_for_resume(bars, 0, origin, 100), ('RESUMED', 3600))

    def test_origin_breach_precedes_same_bar_resume_and_gaps_stop_scan(self):
        origin = dict(close=103, low=100, high=104)
        bars = {900: dict(close=102, low=101, high=103),
                1800: dict(close=104, low=99, high=105)}
        self.assertEqual(wait_for_resume(bars, 0, origin, 100), ('WAIT_INVALIDATED', None))
        self.assertEqual(wait_for_resume({1800: bars[1800]}, 0, origin, 100), ('WAIT_DATA_GAP', None))


class ResumeRoomTests(unittest.TestCase):
    def test_net_parity_checks_cost_and_capped_target(self):
        from orrery_gold_nested_wave_study import resume_room_gate

        def screen(entry, ceiling):
            return resume_room_gate(signal_close=entry, stop=100, ceiling=ceiling)['decision']

        self.assertEqual(screen(104, 109.08), 'PASS_RESEARCH_SCREEN')
        self.assertEqual(screen(104, 109.07), 'NET_REWARD_BELOW_RISK')
        self.assertEqual(screen(102, 200), 'NET_REWARD_BELOW_RISK')
        self.assertEqual(screen(104, 104.54), 'TARGET_ROOM_DOES_NOT_COVER_COST')
        self.assertEqual(screen(100, 110), 'INVALID_STOP')
