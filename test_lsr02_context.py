import unittest
from lsr02_context import analyze
from lsr02_divisor import levels
from lsr02_study import study
from test_lsr02_paths import fixture


class ContextTests(unittest.TestCase):
    def bar(self, close, i, high=None, low=None):
        return dict(open=close, close=close, high=high if high is not None else close+.5,
                    low=low if low is not None else close-.5, close_time=(i+1)*300)

    def context(self, bars, **kw):
        settings = dict(as_of=bars[-1]['close_time'] if bars else 0,
                        interval=300, tenkan=2, kijun=3, span_b=4, shift=2, left=1, right=1)
        settings.update(kw)
        return analyze(bars, **settings)

    def test_cloud_offset_and_formula(self):
        bars = [self.bar(i+10, i) for i in range(7)]
        out = self.context(bars)
        self.assertEqual(out['tenkan'], 15.5)
        self.assertEqual(out['kijun'], 15)
        self.assertEqual(out['cloud']['span_a'], 13.25)
        self.assertEqual(out['cloud']['span_b'], 12.5)
        self.assertEqual(out['cloud']['source_at'], 1500)
        self.assertEqual(out['cloud_location'], 'ABOVE')
        self.assertEqual(out['rule_2_6_status'], 'UNRESOLVED_AUTHOR_DEFINITION')
        self.assertFalse(out['execution_allowed'])

    def test_visible_cloud_needs_full_shifted_history(self):
        bars = [self.bar(10, i) for i in range(70)]
        self.assertEqual(self.context(bars, tenkan=9, kijun=26, span_b=52, shift=26)['cloud_location'], 'UNKNOWN')
        bars = [self.bar(10, i) for i in range(78)]
        self.assertEqual(self.context(bars, tenkan=9, kijun=26, span_b=52, shift=26)['cloud_location'], 'INSIDE')

    def test_up_down_cloud_cross_and_boundary(self):
        for last, expected in ((12, 'UP'), (8, 'DOWN'), (10, None)):
            bars = [self.bar(10, i) for i in range(6)]+[self.bar(last, 6)]
            self.assertEqual(self.context(bars)['cloud_break'], expected)

    def test_wick_does_not_count_as_horizontal_close_break(self):
        bars = [self.bar(c, i) for i, c in enumerate([10, 12, 10, 11])]
        bars.append(self.bar(11, 4, high=14))
        self.assertEqual(self.context(bars)['horizontal_breaks'], [])
        bars[-1] = self.bar(13, 4)
        event = self.context(bars)['horizontal_breaks'][0]
        self.assertEqual(event['direction'], 'UP')
        self.assertLess(event['reference_known_at'], event['observed_at'])

    def test_divisor_levels_are_price_levels_not_rr_or_extension(self):
        out = levels(low=100, high=126, known_at=300, as_of=600)
        self.assertEqual(out['offset'], 10)
        self.assertEqual(out['buy_pullback_level'], 116)
        self.assertEqual(out['sell_pullback_level'], 110)
        self.assertAlmostEqual(out['range_fraction'], .3846153846153846)
        self.assertEqual(out['author_match'], 'UNVERIFIED')
        self.assertFalse(out['execution_allowed'])
        with self.assertRaises(ValueError):
            levels(low=100, high=126, known_at=900, as_of=600)
        with self.assertRaises(ValueError):
            levels(low=126, high=100, known_at=300, as_of=600)

    def test_divisor_proxy_uses_only_previously_confirmed_anchors(self):
        bars = [self.bar(c, i) for i, c in enumerate([10, 12, 10, 8, 10, 11])]
        out = self.context(bars)['range_divisor_2_6']
        self.assertIsNotNone(out)
        self.assertLess(out['known_at'], bars[-1]['close_time'])
        self.assertLess(out['anchor_high']['known_at'], bars[-1]['close_time'])
        self.assertLess(out['anchor_low']['known_at'], bars[-1]['close_time'])

    def test_stale_future_gap_and_bad_config(self):
        bars = [self.bar(10, i) for i in range(7)]
        self.assertEqual(self.context(bars, as_of=2400)['status'], 'UNKNOWN')
        for kw in ({'as_of': 1800}, {'shift': True}, {'span_b': 0}):
            with self.assertRaises(ValueError):
                self.context(bars, **kw)
        with self.assertRaises(ValueError):
            self.context(bars[::2])

    def test_study_annotations_preserve_decisions_and_do_not_use_future(self):
        h, f, m = fixture()
        args = dict(as_of=m[-1]['close_time'], buffer=.1, risk_usd=100,
                    round_trip_cost_usd=10, per_exit_cost_usd=1,
                    partial_r=1, partial_fraction=.5, lifetime=6000, left=1, right=1)
        cfg = dict(tenkan=2, kijun=3, span_b=4, shift=2)
        plain = study('XAUUSD', h, f, m, **args)
        annotated = study('XAUUSD', h, f, m, **args, context_config=cfg)
        self.assertEqual(plain['summaries'], annotated['summaries'])
        t = annotated['candidates'][0]['entry_at']
        args['as_of'] = t
        short = study('XAUUSD', [b for b in h if b['close_time'] <= t],
                      [b for b in f if b['close_time'] <= t],
                      [b for b in m if b['close_time'] <= t], **args, context_config=cfg)
        self.assertEqual(short['candidates'][0]['entry_context'],
                         annotated['candidates'][0]['entry_context'])
        for v in annotated['candidates'][0]['entry_context'].values():
            self.assertLessEqual(v['at'], t)

if __name__ == '__main__':
    unittest.main()
