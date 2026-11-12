import unittest

from orrery_gold_channel_breakout import evaluate_signal, signals


class ChannelBreakoutTests(unittest.TestCase):
    def test_signal_uses_only_prior_twenty_bars_and_respects_gap(self):
        bars = [dict(close_time=900*(i+1), open=100, close=100, high=101, low=99)
                for i in range(20)]
        bars.append(dict(close_time=18900, open=100, close=102, high=103, low=100))
        result = list(signals(bars))
        self.assertEqual(result, [dict(at_utc=18900, side='BUY', stop_range_price=2,
                                       selected=True)])
        self.assertEqual(list(signals(bars[:5] + bars[6:])), [])

    def test_buy_stop_uses_bid_and_risk_includes_opening_spread(self):
        signal = dict(at_utc=900, side='BUY', stop_range_price=2, selected=True)
        bid = {900: dict(open=100, high=106, low=99, close=104)}
        ask = {900: dict(open=101, high=107, low=100, close=105)}
        result = evaluate_signal(signal, bid, ask)
        self.assertEqual(result['stop'], 98)
        self.assertEqual(result['entry'], 101)
        self.assertEqual(result['initial_risk_price'], 3)
        self.assertEqual(result['r'], 1.5)


class OpeningSpreadTests(unittest.TestCase):
    def test_opening_spread_boundary_and_unknown_risk(self):
        from orrery_gold_breakout_spread_review import spread_group

        self.assertEqual(spread_group(dict(initial_risk_price=10, stop_range_price=9)), 'PASS')
        self.assertEqual(spread_group(dict(initial_risk_price=10, stop_range_price=8.9)), 'FILTERED')
        self.assertEqual(spread_group(dict(stop_range_price=9)), 'UNKNOWN')
        with self.assertRaisesRegex(ValueError, 'Negative implied'):
            spread_group(dict(initial_risk_price=10, stop_range_price=11))

    def test_reentry_waits_until_exit_minute_closes(self):
        from orrery_gold_breakout_frequency import next_eligible_clock

        row = dict(status='RESOLVED_REFERENCE', at_utc=900, exit_at=1800, exit_reason='TP_TOUCH')
        self.assertEqual(next_eligible_clock(row), 1860)
        self.assertEqual(next_eligible_clock(dict(row, exit_reason='TIMEOUT_CLOSE')), 1800)
        self.assertEqual(next_eligible_clock(dict(row, status='CENSORED_AT_SIDE_GAP')), 8100)
