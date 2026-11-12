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


class DirectionComparisonTests(unittest.TestCase):
    def test_opposite_trade_can_also_stop_and_missing_quote_stays_unknown(self):
        from orrery_gold_channel_breakout import compare_directions

        signal = dict(at_utc=1788220800, side='BUY', stop_range_price=2, selected=True)
        bid = {signal['at_utc']: dict(open=100, high=104, low=97, close=100)}
        ask = {signal['at_utc']: dict(open=101, high=105, low=98, close=101)}
        result = compare_directions(
            [signal, dict(signal, at_utc=signal['at_utc'] + 7200)], bid, ask)['overall']
        self.assertEqual(result['candidates'], 2)
        self.assertEqual(result['matched_resolved'], 1)
        for direction in ('original', 'reverse'):
            arm = result[direction]
            self.assertEqual(arm['exit_reasons'], {'SL_TOUCH': 1})
            self.assertEqual(arm['statuses']['UNKNOWN_ENTRY_HISTORY'], 1)
            self.assertAlmostEqual(arm['scenarios'][1]['mean_resolved_r'], -1.1)


class BreakoutStrengthTests(unittest.TestCase):
    def test_strength_uses_prior_channel_and_includes_exact_threshold(self):
        from orrery_gold_channel_breakout import compare_breakout_strength

        prior = [dict(close_time=900*(i+1), open=100, close=100, high=101, low=99)
                 for i in range(20)]
        for close, expected in ((101.5, 'passed'), (98.6, 'filtered')):
            with self.subTest(close=close):
                current = dict(close_time=18900, open=100, close=close, high=104, low=96)
                row, = signals(prior + [current], record_breakout_strength=True)
                result = compare_breakout_strength(
                    [dict(row, status='UNKNOWN_ENTRY_HISTORY')])['overall']
                self.assertEqual(result[expected]['candidates'], 1)
                self.assertEqual(result[expected]['resolved'], 0)
