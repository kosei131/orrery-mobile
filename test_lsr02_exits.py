import unittest
from lsr02_exits import simulate, compare

class ExitTests(unittest.TestCase):
    def args(self):
        return dict(side='BUY', entry=100, sl=99, entry_at=0, as_of=600,
                    interval=300, risk_usd=100, round_trip_cost_usd=10,
                    per_exit_cost_usd=1)

    def bar(self, o=100, h=103, l=99.5, c=102, at=300):
        return dict(open=o, high=h, low=l, close=c, close_time=at)

    def test_full_vs_partial_not_both_2_6r(self):
        r = compare([self.bar()], measured_range=2, partial_target=101,
                    partial_fraction=.5, **self.args())
        b = r['hypotheses']['B_gross_rr_2_6']
        self.assertAlmostEqual(b['full']['completed_net_usd'], 249)
        self.assertAlmostEqual(b['partial']['completed_net_usd'], 168)
        self.assertEqual(r['hypotheses']['A_range_2_6']['full']['status'], 'OPEN')
        self.assertIsNone(r['C_undefined'])

    def test_same_bar_stop_first(self):
        r = simulate([self.bar(l=98)], targets=[(101, .5), (102.6, .5)], **self.args())
        self.assertEqual(len(r['fills']), 1)
        self.assertEqual(r['completed_net_usd'], -111)

    def test_partial_then_stop_and_costs(self):
        bars = [self.bar(h=101.5, c=101), self.bar(o=101, h=101, l=98, c=99, at=600)]
        r = simulate(bars, targets=[(101, .5), (102.6, .5)], **self.args())
        self.assertAlmostEqual(r['completed_net_usd'], -12)
        self.assertEqual(len(r['fills']), 2)

    def test_stop_gap_can_exceed_initial_risk(self):
        r = simulate([self.bar(o=98, l=97, h=100, c=99)], targets=[(102.6, 1)], **self.args())
        self.assertEqual(r['completed_net_usd'], -211)
        self.assertEqual(r['fills'][0]['reason'], 'STOP_GAP')

    def test_open_target_precedes_later_stop_no_price_improvement(self):
        r = simulate([self.bar(o=101.5, h=102, l=98, c=99)],
                     targets=[(101, .5), (102.6, .5)], **self.args())
        self.assertEqual(r['fills'][0]['price'], 101)
        self.assertEqual(r['fills'][0]['reason'], 'TARGET_AT_OPEN')
        self.assertAlmostEqual(r['completed_net_usd'], -12)

    def test_sell_symmetry(self):
        args = self.args()
        args.update(side='SELL', sl=101)
        r = simulate([self.bar(h=100.5, l=97, c=98)], targets=[(97.4, 1)], **args)
        self.assertAlmostEqual(r['completed_net_usd'], 249)
        self.assertFalse(r['execution_allowed'])

    def test_open_not_counted_as_completed(self):
        r = simulate([], targets=[(102.6, 1)], **self.args())
        self.assertEqual(r['remaining_fraction'], 1)
        self.assertIsNone(r['completed_net_usd'])
        r = simulate([self.bar(h=101.5, c=101)], targets=[(101, .5), (102.6, .5)], **self.args())
        self.assertEqual(r['status'], 'OPEN')
        self.assertAlmostEqual(r['realized_net_usd'], 44)

    def test_bad_or_future_inputs_rejected(self):
        for targets in [[(101, .8)], [(102, .5), (101, .5)], [(101, True)], [(98, 1)]]:
            with self.assertRaises(ValueError):
                simulate([], targets=targets, **self.args())
        for bars in [[self.bar(at=900)], [self.bar(at=600)],
                     [self.bar(), self.bar(at=900)]]:
            with self.assertRaises(ValueError):
                simulate(bars, targets=[(102.6, 1)], **self.args())

if __name__ == '__main__':
    unittest.main()
