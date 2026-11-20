import unittest
from orrery_second_barrier_diagnostic import first_touch

class SecondBarrierTests(unittest.TestCase):
    def test_buy_bid_target_then_later_stop(self):
        r=first_touch([(1000,100,102),(2000,111,113),(3000,89,91)],'BUY',90,110)
        self.assertEqual((r['status'],r['at_utc_ms']),('TARGET_OBSERVED',2000))
        self.assertIsNone(r['actual_profit_usd'])
        self.assertFalse(r['execution_allowed'])

    def test_sell_uses_ask(self):
        r=first_touch([(1000,88,96),(2000,98,102)],'SELL',101,90)
        self.assertEqual((r['status'],r['at_utc_ms']),('STOP_OBSERVED',2000))

    def test_same_second_two_barriers_is_ambiguous_in_both_orders(self):
        rows=[(1000,100,102),(2000,89,91),(2000,111,113)]
        for case in (rows,rows[:1]+rows[:0:-1]):
            with self.subTest(case=case):
                r=first_touch(case,'BUY',90,110)
                self.assertEqual(r['status'],'AMBIGUOUS_SAME_SECOND')
                self.assertFalse(r['intrasecond_order_verified'])

    def test_clock_reversal_even_after_initial_target_must_fail(self):
        with self.assertRaisesRegex(ValueError,'Clock reversal'):
            first_touch([(1000,111,113),(0,100,102)],'BUY',90,110)

    def test_invalid_ask_clock_quote_rejected(self):
        for tick in ((1000,110,109),(1001,100,102),(1000,0,1),('1000',100,102)):
            with self.subTest(tick=tick),self.assertRaises(ValueError):
                first_touch([tick],'BUY',90,110)

    def test_invalid_barriers_rejected(self):
        for side,sl,tp in (('BUY',110,90),('SELL',90,110),('BUY',0,110),('SIDE',90,110)):
            with self.subTest(side=side),self.assertRaises(ValueError):
                first_touch([],side,sl,tp)

    def test_empty_is_not_profit_or_backtest(self):
        r=first_touch([],'BUY',90,110)
        self.assertEqual(r['status'],'UNRESOLVED')
        self.assertFalse(r['backtest_ready'])
        self.assertIsNone(r['actual_profit_usd'])

if __name__=='__main__':
    unittest.main()
