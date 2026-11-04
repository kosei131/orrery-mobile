import unittest
from orrery_gold_m15_reference_outcomes import measure
STEP=900
def bar(n,o=1000,high=1010,low=990,close=1000):
    return dict(close_time=n*STEP,open=o*1000000,high=high*1000000,
                low=low*1000000,close=close*1000000)
def signal(n=1,side='BUY',family='TREND_CONTINUATION'):
    return dict(candidate_id=f'signal:{n}:{side}:{family}',family=family,
                side=side,signal_known_at=n*STEP,entry_price_scaled=None,outcome_r=None)

class M15ReferenceTests(unittest.TestCase):
    def test_buy_target_and_r(self):
        r=measure([bar(1),bar(2,high=1011,low=997)], [signal()])
        x=r['candidates'][0]
        self.assertEqual(x['state'],'TARGET_TOUCH_REFERENCE')
        self.assertEqual(x['reference_r'],1.5)

    def test_buy_stop(self):
        x=measure([bar(1),bar(2,high=1001,low=993)], [signal()])['candidates'][0]
        self.assertEqual(x['reference_r'],-1)

    def test_sell_uses_opposite_barrier(self):
        x=measure([bar(1),bar(2,high=1001,low=990)], [signal(side='SELL')])['candidates'][0]
        self.assertEqual(x['state'],'TARGET_TOUCH_REFERENCE')

    def test_same_bar_both_censored(self):
        x=measure([bar(1),bar(2,high=1010,low=993)], [signal()])['candidates'][0]
        self.assertEqual(x['state'],'AMBIGUOUS_SAME_M15')
        self.assertIsNone(x['reference_r'])

    def test_missing_next_bar(self):
        x=measure([bar(1),bar(3)], [signal()])['candidates'][0]
        self.assertEqual(x['state'],'CENSORED_NEXT_BAR_MISSING')

    def test_mid_trade_gap(self):
        x=measure([bar(1),bar(2,high=1002,low=997),bar(4)], [signal()])['candidates'][0]
        self.assertEqual(x['state'],'CENSORED_M15_GAP')

    def test_stop_gap_open_not_rounded(self):
        x=measure([bar(1),bar(2,o=990,high=1000,low=989,close=990)], [signal()])['candidates'][0]
        self.assertEqual(x['state'],'STOP_GAP_OPEN_REFERENCE')
        self.assertLess(x['reference_r'],-1)

    def test_favorable_gap_capped(self):
        x=measure([bar(1),bar(2,o=1012,high=1013,low=1011,close=1012)], [signal()])['candidates'][0]
        self.assertEqual(x['state'],'TARGET_GAP_OPEN_REFERENCE_CAPPED')
        self.assertEqual(x['reference_r'],1.5)

    def test_duplicate_candidate_rejected(self):
        with self.assertRaises(ValueError):
            measure([bar(1),bar(2)], [signal(),signal()])

    def test_no_broker_claim(self):
        r=measure([bar(1),bar(2,high=1011,low=997)], [signal()])
        self.assertIsNone(r['net_expectancy_r'])
        self.assertFalse(r['adoption_allowed'])
        self.assertFalse(r['execution_allowed'])

if __name__=='__main__':
    unittest.main()
