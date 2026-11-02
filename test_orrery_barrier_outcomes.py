import unittest
from orrery_barrier_outcomes import evaluate,summarize

def bar(t,high=101,low=99,opening=100,close=100):
    return dict(close_time=t,open=opening,high=high,low=low,close=close)

def check(rows,side='BUY',**kw):
    args=dict(side=side,decision_at=300,entry_reference=100,sl=98,tp=102,interval=300)
    args.update(kw)
    return evaluate(rows,**args)

class BarrierOutcomeTests(unittest.TestCase):
    def test_buy_tp_and_stop_first(self):
        self.assertEqual(check([bar(600,high=103)])['status'],'TP_FIRST')
        self.assertEqual(check([bar(600,low=97)])['status'],'SL_FIRST')
    def test_sell_tp_and_stop_first(self):
        self.assertEqual(check([bar(600,low=97)],'SELL',sl=102,tp=98)['status'],'TP_FIRST')
        self.assertEqual(check([bar(600,high=103)],'SELL',sl=102,tp=98)['status'],'SL_FIRST')
    def test_same_bar_cannot_be_claimed_win(self):
        result=check([bar(600,high=103,low=97)])
        self.assertEqual(result['status'],'AMBIGUOUS_SAME_BAR')
        self.assertIsNone(summarize([result])['full_cohort_win_rate'])
    def test_horizon_censor_is_not_zero_pnl(self):
        r=check([bar(600)])
        self.assertEqual(r['status'],'CENSORED_HORIZON')
        self.assertIsNone(r['realized_net_usd'])
    def test_no_future_info_or_missing_bars(self):
        with self.assertRaises(ValueError):check([bar(900,high=103)])
        with self.assertRaises(ValueError):check([bar(300,high=103)])
        with self.assertRaises(ValueError):check([bar(600),bar(1200,high=103)])
    def test_full_resolved_fraction_not_net_expectancy(self):
        r=summarize([check([bar(600,high=103)]),check([bar(600,low=97)])])
        self.assertEqual(r['full_cohort_win_rate'],0.5)
        self.assertIsNone(r['net_expectancy_usd'])
        self.assertFalse(r['execution_allowed'])
if __name__=='__main__':unittest.main()
