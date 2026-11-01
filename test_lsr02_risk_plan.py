import unittest
from lsr02_risk_plan import plan, performance

class RiskPlanTests(unittest.TestCase):
    def args(self):
        return dict(side='BUY', entry=100, sweep_extreme=99, buffer=.1,
                    target=103, equity=10000, risk_fraction=.0025,
                    cost=1, existing_risk=0, max_total_risk=100,
                    remaining_loss_budget=200, consecutive_losses=0,
                    loss_stop=3, data_ok=True, news_clear=True, spread_ok=True)

    def test_stop_beyond_sweep_and_no_execution(self):
        p = plan(**self.args())
        self.assertAlmostEqual(p['stop'], 98.9)
        self.assertEqual(p['estimated_stop_loss_usd'], 26)
        self.assertEqual(p['status'], 'DEMO_REVIEW_ONLY')
        self.assertIsNone(p['lots'])
        self.assertFalse(p['execution_allowed'])
        a = self.args()
        a.update(side='SELL', sweep_extreme=101, target=97)
        self.assertAlmostEqual(plan(**a)['stop'], 101.1)

    def test_reject_without_moving_structural_target(self):
        a = self.args()
        a['target'] = 102
        p = plan(**a)
        self.assertEqual(p['status'], 'SKIP')
        self.assertEqual(p['target'], 102)
        for key, value in [('news_clear', False), ('spread_ok', False),
                           ('data_ok', False), ('consecutive_losses', 3),
                           ('existing_risk', 90), ('remaining_loss_budget', 26),
                           ('risk_fraction', .01)]:
            a = self.args()
            a[key] = value
            self.assertEqual(plan(**a)['status'], 'SKIP', key)

    def test_bad_structure_rejected(self):
        for key, value in [('buffer', 0), ('entry', float('nan')),
                           ('sweep_extreme', 102), ('target', 99),
                           ('buffer', True)]:
            a = self.args()
            a[key] = value
            with self.assertRaises(ValueError):
                plan(**a)

    def rows(self, values, cost=0):
        return [dict(id=str(i), closed_at=i, gross_pnl=v, cost=cost,
                     initial_risk=100) for i, v in enumerate(values)]

    def test_losses_can_coexist_with_positive_net_expectancy(self):
        p = performance(self.rows([200]*4+[-100]*6), initial_equity=10000)
        self.assertEqual(p['win_rate'], .4)
        self.assertEqual(p['net_pnl_usd'], 200)
        self.assertAlmostEqual(p['expectancy_r'], .2)
        self.assertAlmostEqual(p['profit_factor'], 800/600)
        self.assertEqual(p['max_realized_drawdown_usd'], 600)
        self.assertEqual(p['max_consecutive_losses'], 6)
        self.assertFalse(p['execution_allowed'])

    def test_costs_and_large_losses_matter_more_than_win_rate(self):
        p = performance(self.rows([200]*4+[-100]*6, 21), initial_equity=10000)
        self.assertEqual(p['net_pnl_usd'], -10)
        p = performance(self.rows([100]*9+[-1500]), initial_equity=10000)
        self.assertEqual(p['win_rate'], .9)
        self.assertEqual(p['net_pnl_usd'], -600)

    def test_breakeven_no_losses_and_empty(self):
        p = performance(self.rows([-100, 0, -100, 200]), initial_equity=10000)
        self.assertEqual(p['max_consecutive_losses'], 2)
        self.assertEqual(p['current_consecutive_losses'], 0)
        self.assertIsNone(performance(self.rows([100]), initial_equity=10000)['profit_factor'])
        p = performance([], initial_equity=10000)
        self.assertIsNone(p['win_rate'])
        self.assertIsNone(p['expectancy_r'])

    def test_bad_trade_history_rejected(self):
        rows = self.rows([100, -100])
        for key, value in [('id', '0'), ('closed_at', -1), ('cost', -1),
                           ('initial_risk', 0), ('gross_pnl', float('inf'))]:
            bad = [dict(t) for t in rows]
            bad[1][key] = value
            with self.assertRaises(ValueError):
                performance(bad, initial_equity=10000)
        with self.assertRaises(ValueError):
            performance(self.rows([-10001]), initial_equity=10000)

if __name__ == '__main__':
    unittest.main()
