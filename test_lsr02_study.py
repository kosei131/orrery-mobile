import copy
import unittest
from lsr02_study import study, POLICIES
from test_lsr02_paths import fixture


class StudyTests(unittest.TestCase):
    def run_study(self, h, f, m, **kw):
        settings = dict(as_of=m[-1]['close_time'], buffer=.1, risk_usd=100,
                        round_trip_cost_usd=10, per_exit_cost_usd=1,
                        partial_r=1, partial_fraction=.5,
                        left=1, right=1, lifetime=6000)
        settings.update(kw)
        return study('XAUUSD', h, f, m, **settings)

    def test_real_detector_to_exits_for_buy_and_sell(self):
        for sell in (False, True):
            h, f, m = fixture(sell)
            original = copy.deepcopy((h, f, m))
            out = self.run_study(h, f, m)
            self.assertEqual(len(out['candidates']), 1)
            c = out['candidates'][0]
            self.assertEqual(c['entry_at'], 105900)
            self.assertEqual(c['side'], 'SELL' if sell else 'BUY')
            self.assertEqual(set(c['policies']), set(POLICIES))
            self.assertIsNone(out['C_undefined'])
            self.assertFalse(out['execution_allowed'])
            self.assertFalse(out['portfolio_metrics_available'])
            self.assertEqual(c['guard_status'], 'BLOCKED_UNVERIFIED_GUARDS')
            for p in c['policies'].values():
                self.assertTrue(all(f['at'] > c['entry_at'] for f in p['fills']))
            self.assertEqual((h, f, m), original)

    def test_no_entry_bar_profit_and_no_repeated_entries(self):
        h, f, m = fixture()
        t = 105900
        m = [b for b in m if b['close_time'] <= t]
        out = self.run_study(h, f, m)
        c = out['candidates'][0]
        for p in c['policies'].values():
            self.assertEqual(p['status'], 'OPEN')
            self.assertEqual(p['fills'], [])
            self.assertIsNone(p['completed_net_usd'])
        self.assertEqual(out['paired_completed_candidate_ids'], [])
        self.assertEqual(out['summaries']['B_rr_full']['closed'], 0)
        self.assertIsNone(out['summaries']['B_rr_full']['win_rate'])

    def test_expired_candidate_never_becomes_trade(self):
        h, f, m = fixture()
        out = self.run_study(h, f, m, lifetime=2400)
        self.assertEqual(out['not_entered'], 1)
        self.assertEqual(out['candidates'][0]['reason'], 'EXPIRED')
        self.assertEqual(out['candidates'][0]['policies'], {})

    def test_later_stop_closes_each_policy_with_costs(self):
        for sell in (False, True):
            h, f, m = fixture(sell)
            m = [b for b in m if b['close_time'] <= 105900]
            price = m[-1]['close']
            m.append(dict(open=price, high=21 if sell else price,
                          low=price if sell else 9, close=price, close_time=106200))
            out = self.run_study(h, f, m)
            c = out['candidates'][0]
            self.assertEqual(out['paired_completed_candidate_ids'], [c['id']])
            for key in POLICIES:
                self.assertAlmostEqual(c['policies'][key]['completed_net_usd'], -111)
                self.assertEqual(out['paired_summaries'][key]['closed'], 1)
                self.assertAlmostEqual(out['summaries'][key]['expectancy_usd'], -111)

    def test_a_b_and_completion_cohorts_are_separate(self):
        h, f, m = fixture()
        m = [b for b in m if b['close_time'] <= 105900]
        entry = m[-1]['close']
        # A sweep range target is below B 2.6R in this fixture.
        m.append(dict(open=entry, high=21.4, low=entry, close=entry, close_time=106200))
        out = self.run_study(h, f, m)
        c = out['candidates'][0]
        self.assertEqual(c['policies']['A_sweep_range_full']['status'], 'CLOSED')
        self.assertEqual(c['policies']['B_rr_full']['status'], 'OPEN')
        self.assertEqual(out['summaries']['A_sweep_range_full']['closed'], 1)
        self.assertEqual(out['paired_summaries']['A_sweep_range_full']['closed'], 0)

    def test_entry_metadata_does_not_change_with_future_data(self):
        h, f, m = fixture()
        full = self.run_study(h, f, m)['candidates'][0]
        short = [b for b in m if b['close_time'] <= 105900]
        t = short[-1]['close_time']
        prefix = self.run_study([b for b in h if b['close_time'] <= t],
                                [b for b in f if b['close_time'] <= t], short)['candidates'][0]
        for key in ('id', 'entry_at', 'entry', 'stop', 'sweep_range', 'poi'):
            self.assertEqual(prefix[key], full[key])

    def test_reject_bad_parameters_and_future_data(self):
        h, f, m = fixture()
        for key, val in [('risk_usd', 0), ('partial_r', -1), ('partial_fraction', True),
                         ('round_trip_cost_usd', -1), ('per_exit_cost_usd', float('nan'))]:
            with self.assertRaises(ValueError):
                self.run_study(h, f, m, **{key: val})
        with self.assertRaises(ValueError):
            self.run_study(h, f, m, as_of=105900)

    def test_invalid_partial_target_skipped_without_hiding_full_result(self):
        h, f, m = fixture()
        out = self.run_study(h, f, m, partial_r=3)
        c = out['candidates'][0]
        self.assertEqual(c['policies']['B_rr_partial']['status'], 'SKIP')
        self.assertNotEqual(c['policies']['B_rr_full']['status'], 'SKIP')
        self.assertEqual(out['summaries']['B_rr_partial']['skipped'], 1)

if __name__ == '__main__':
    unittest.main()
