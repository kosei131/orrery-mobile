import unittest
from datetime import timedelta
from types import SimpleNamespace as D
from lsr04_daily_reconciliation import reconcile_day
from lsr04_mt5_account_sync import demo_day_check
import test_lsr04_mt5_account_sync as fixtures


class Arithmetic(unittest.TestCase):
    def run_day(self, **kw):
        args = dict(opening_balance=10000, opening_equity=9900,
                    closing_balance=9990, closing_equity=9950,
                    trade_net=-10, external_cash_net=0,
                    history_complete=True, baseline_verified=True)
        args.update(kw)
        return reconcile_day(**args)

    def test_floating_change_not_realized_profit(self):
        r = self.run_day()
        self.assertTrue(r['balance_reconciled'])
        self.assertEqual(r['nonbalance_equity_component_change'], 60)
        self.assertEqual(r['equity_change'], 50)
        self.assertFalse(r['equity_components_verified'])
        self.assertFalse(r['execution_allowed'])

    def test_deposit_not_profit(self):
        r = self.run_day(closing_balance=10490, closing_equity=10450, external_cash_net=500)
        self.assertTrue(r['balance_reconciled'])
        self.assertEqual(r['equity_change_excluding_external_cash'], 50)
        self.assertEqual(r['trade_net'], -10)

    def test_missing_cost_creates_residual(self):
        r = self.run_day(trade_net=-8)
        self.assertEqual(r['balance_residual'], -2)
        self.assertFalse(r['balance_reconciled'])

    def test_evidence_required_despite_arithmetic_match(self):
        for kw in ({'history_complete': False}, {'baseline_verified': False}):
            self.assertFalse(self.run_day(**kw)['balance_reconciled'])

    def test_small_rounding_tolerance(self):
        self.assertTrue(self.run_day(closing_balance=9990.005)['balance_reconciled'])
        self.assertFalse(self.run_day(closing_balance=9990.02)['balance_reconciled'])

    def test_bad_values_rejected(self):
        for kw in ({'trade_net': float('nan')}, {'tolerance': 100}, {'baseline_verified': 1}):
            with self.assertRaises(ValueError):
                self.run_day(**kw)


class Integration(unittest.TestCase):
    def setup_run(self, *, cash=0, balance=10008, equity=10008):
        helper = fixtures.Bridge()
        rows = [helper.row(1, 1, 0), helper.row(1, 2, 1, profit=10)]
        evidence = {}
        if cash:
            rows.append(D(ticket=3, time_msc=rows[-1].time_msc+1, type=2,
                          position_id=0, volume=0, profit=cash, commission=0, swap=0, fee=0))
            evidence[3] = cash
        broker = helper.broker(rows)
        broker.DEAL_TYPE_BALANCE = 2
        old_account = broker.account_info
        def account():
            a = old_account(); a.balance=balance; a.equity=equity; return a
        broker.account_info = account
        kw = helper.kw(history_complete=True, verified_cash_flows=evidence)
        kw['day_start_snapshot'] = dict(at_utc=kw['day_start_utc'], login=1, server='demo',
            currency='USD', trade_mode=0, balance=10000, equity=10000, verified=True)
        return broker, kw

    def test_matched_balance_still_blocks_equity_and_stop_exposure(self):
        b, kw = self.setup_run()
        r = demo_day_check(b, **kw)
        self.assertTrue(r['daily_review']['balance_reconciled'])
        self.assertFalse(r['daily_reconciled'])
        self.assertEqual(r['status'], 'BLOCKED_UNVERIFIED_EQUITY_AND_STOP_EXPOSURE')

    def test_deposit_and_withdrawal_not_counted_as_trades(self):
        for cash in (500, -500):
            b, kw = self.setup_run(cash=cash, balance=10008+cash, equity=10008+cash)
            r = demo_day_check(b, **kw)
            self.assertEqual(r['grouping']['completed_positions'], 1)
            self.assertEqual(r['daily_deal_net'], 8)
            self.assertEqual(r['daily_external_cash_net'], cash)
            self.assertTrue(r['daily_review']['balance_reconciled'])
            self.assertEqual(r['status'], 'BLOCKED_CASH_ADJUSTED_RISK_REQUIRED')

    def test_unverified_cash_blocks(self):
        b, kw = self.setup_run(cash=500); kw['verified_cash_flows'] = {}
        self.assertEqual(demo_day_check(b, **kw)['status'], 'BLOCKED_UNCLASSIFIED_OR_INVALID_HISTORY')

    def test_cash_amount_mismatch_blocks(self):
        b, kw = self.setup_run(cash=500); kw['verified_cash_flows'][3] = 400
        self.assertEqual(demo_day_check(b, **kw)['status'], 'BLOCKED_UNCLASSIFIED_OR_INVALID_HISTORY')

    def test_missing_cash_evidence_ticket_blocks(self):
        b, kw = self.setup_run(); kw['verified_cash_flows'] = {99: 10}
        self.assertEqual(demo_day_check(b, **kw)['status'], 'BLOCKED_UNCLASSIFIED_OR_INVALID_HISTORY')

    def test_balance_mismatch_blocks(self):
        b, kw = self.setup_run(balance=10007)
        r = demo_day_check(b, **kw)
        self.assertEqual(r['daily_review']['balance_residual'], -1)
        self.assertEqual(r['status'], 'BLOCKED_DAILY_RECONCILIATION')

    def test_wrong_baseline_account_time_and_equity_block(self):
        for key, value in (('login', 9), ('currency', 'JPY'), ('equity', 9999), ('at_utc', None)):
            b, kw = self.setup_run(); kw['day_start_snapshot'][key] = value
            self.assertEqual(demo_day_check(b, **kw)['status'], 'BLOCKED_INVALID_DAILY_BASELINE')

    def test_unverified_baseline_blocks(self):
        b, kw = self.setup_run(); kw['day_start_snapshot']['verified'] = False
        self.assertEqual(demo_day_check(b, **kw)['status'], 'BLOCKED_DAILY_RECONCILIATION')

    def test_pre_session_cash_excluded_from_day(self):
        b, kw = self.setup_run(cash=500)
        rows = b.history_deals_get(None, None)
        rows[-1].time_msc -= 86400000
        kw['history_start_utc'] = kw['day_start_utc'] - timedelta(days=1)
        r = demo_day_check(b, **kw)
        self.assertEqual(r['daily_external_cash_net'], 0)
        self.assertTrue(r['daily_review']['balance_reconciled'])


if __name__ == '__main__':
    unittest.main()
