import unittest
from lsr02_portfolio import portfolio, _account
from lsr02_study import POLICIES
from test_lsr02_paths import fixture


class PortfolioTests(unittest.TestCase):
    def account(self, candidates, **kw):
        source = dict(candidates=candidates, round_trip_cost_usd=kw.pop('cost_r', 0),
                      portfolio_per_exit_cost_usd=kw.pop('fee', 0), partial_r=1, partial_fraction=.5)
        rules = dict(initial_equity=10000, risk_fraction=.005,
                     loss_budget_usd=1000, loss_stop=2)
        rules.update(kw)
        return _account(source, 'B_rr_full', **rules)

    def candidate(self, ident, at, fills, status='CLOSED'):
        outcome = dict(status=status, fills=[dict(at=t, gross_pnl=r*f,
                       fraction=f, reason='TEST') for t, r, f in fills])
        return dict(id=ident, entry_at=at, entry=100, stop=99,
                    sweep_range=1, policies={p: outcome for p in POLICIES})

    def test_integration_real_detector_single_symbol(self):
        h, f, m = fixture()
        out = portfolio('XAUUSD', h, f, m, as_of=m[-1]['close_time'], buffer=.1,
                        lifetime=6000, left=1, right=1, partial_r=2, partial_fraction=.5,
                        initial_equity=10000, risk_fraction=.0025, loss_budget_usd=500,
                        loss_stop=3, round_trip_cost_r=.03, per_exit_cost_usd=.1)
        self.assertFalse(out['execution_allowed'])
        self.assertEqual(set(out['accounts']), set(POLICIES))
        for a in out['accounts'].values():
            self.assertEqual(len(a['decisions']), 1)
            self.assertEqual(a['decisions'][0]['status'], 'HYPOTHETICAL_ENTRY')
            self.assertEqual(a['decisions'][0]['risk_usd'], 25)

    def test_no_overlap_or_future_profit_sizing(self):
        a = self.candidate('a', 0, [(900, 2.6, 1)])
        b = self.candidate('b', 300, [(600, -1, 1)])
        c = self.candidate('c', 900, [(1200, -1, 1)])
        out = self.account([a, b, c])
        self.assertEqual(out['decisions'][1]['reason'], 'POSITION_ALREADY_OPEN')
        self.assertEqual(out['decisions'][0]['risk_usd'], 50)
        self.assertAlmostEqual(out['decisions'][2]['risk_usd'], 50.65)
        self.assertEqual(out['closed_count'], 2)

    def test_risk_shrinks_after_loss_and_loss_stop_latches(self):
        rows = [self.candidate(str(i), i*600, [(i*600+300, -1, 1)]) for i in range(3)]
        out = self.account(rows)
        self.assertEqual(out['decisions'][0]['risk_usd'], 50)
        self.assertEqual(out['decisions'][1]['risk_usd'], 49.75)
        self.assertEqual(out['decisions'][2]['reason'], 'CONSECUTIVE_LOSS_STOP')
        self.assertEqual(out['closed_count'], 2)
        self.assertEqual(out['max_consecutive_losses'], 2)
        self.assertAlmostEqual(out['max_realized_drawdown_usd'], 99.75)

    def test_remaining_budget_blocks_without_reducing_stop(self):
        a = self.candidate('a', 0, [(300, -1, 1)])
        b = self.candidate('b', 600, [(900, 2.6, 1)])
        out = self.account([a, b], loss_budget_usd=75)
        self.assertEqual(out['decisions'][1]['reason'], 'INSUFFICIENT_LOSS_BUDGET')
        self.assertEqual(out['ending_realized_balance_usd'], 9950)

    def test_gap_can_breach_budget_then_stops_entries(self):
        a = self.candidate('a', 0, [(300, -3, 1)])
        b = self.candidate('b', 600, [(900, 2.6, 1)])
        out = self.account([a, b], loss_budget_usd=100)
        self.assertEqual(out['ending_realized_balance_usd'], 9850)
        self.assertEqual(out['decisions'][1]['reason'], 'LOSS_BUDGET_REACHED')

    def test_partial_realized_profit_does_not_free_position(self):
        a = self.candidate('a', 0, [(300, 1, .5)], status='OPEN')
        b = self.candidate('b', 600, [(900, 2.6, 1)])
        out = self.account([a, b])
        self.assertEqual(out['open_count'], 1)
        self.assertEqual(out['closed_count'], 0)
        self.assertEqual(out['ending_realized_balance_usd'], 10025)
        self.assertEqual(out['decisions'][1]['reason'], 'POSITION_ALREADY_OPEN')
        self.assertIsNone(out['win_rate'])
        self.assertEqual(out['open_position']['remaining_fraction'], .5)

    def test_partial_rr_below_two_is_rejected(self):
        h, f, m = fixture()
        out = portfolio('XAUUSD', h, f, m, as_of=m[-1]['close_time'], buffer=.1,
                        lifetime=6000, left=1, right=1, partial_r=1, partial_fraction=.5,
                        initial_equity=10000, risk_fraction=.0025, loss_budget_usd=500,
                        loss_stop=3, round_trip_cost_r=.03, per_exit_cost_usd=.1)
        self.assertEqual(out['accounts']['B_rr_partial']['decisions'][0]['reason'], 'NET_RR_BELOW_2')
        self.assertEqual(out['accounts']['B_rr_full']['decisions'][0]['status'], 'HYPOTHETICAL_ENTRY')

    def test_costs_scale_with_risk_but_fixed_fee_is_per_fill(self):
        a = self.candidate('a', 0, [(300, 1, .5), (600, -1, .5)])
        out = self.account([a], cost_r=.1, fee=1)
        self.assertEqual(out['ending_realized_balance_usd'], 9993)
        self.assertEqual(out['closed_trades'][0]['net_usd'], -7)
        self.assertEqual(out['current_consecutive_losses'], 1)
        self.assertEqual(out['fills'][0]['cost_usd'], 3.5)
        self.assertEqual(out['fills'][1]['cost_usd'], 3.5)
        self.assertEqual(out['max_realized_drawdown_usd'], 28.5)

    def test_future_result_does_not_change_earlier_entry_decision(self):
        a = self.candidate('a', 0, [(900, 2.6, 1)])
        b = self.candidate('b', 300, [(600, -1, 1)])
        full = self.account([a, b])
        prefix_a = self.candidate('a', 0, [], status='OPEN')
        short = self.account([prefix_a, b])
        self.assertEqual(full['decisions'], short['decisions'])

    def test_invalid_rules_rejected(self):
        h, f, m = fixture()
        rules = dict(initial_equity=10000, risk_fraction=.005, loss_budget_usd=1000,
                     loss_stop=2, round_trip_cost_r=.03, per_exit_cost_usd=.1)
        for k, v in [('risk_fraction', .01), ('loss_stop', True), ('loss_budget_usd', 10000),
                     ('initial_equity', float('nan')), ('round_trip_cost_r', -1)]:
            bad = dict(rules)
            bad[k] = v
            with self.assertRaises(ValueError):
                portfolio('XAUUSD', h, f, m, **bad)

if __name__ == '__main__':
    unittest.main()
