import unittest
from orrery_second_barrier_diagnostic import first_touch

class SecondBarrierDiagnosticTests(unittest.TestCase):
    def test_buy_same_second_both_is_ambiguous_regardless_of_file_order(self):
        tick_a=(1000,95,96)
        tick_b=(1000,105,106)
        for seq in ((tick_a,tick_b),(tick_b,tick_a)):
            result=first_touch(seq,'BUY',97,104)
            self.assertEqual(result['status'],'AMBIGUOUS_SAME_SECOND')
            self.assertIsNone(result['actual_profit_usd'])
            self.assertFalse(result['execution_allowed'])

    def test_sell_uses_ask_to_assess_barriers(self):
        result=first_touch([(1000,98,99),(2000,90,91)],'SELL',104,92)
        self.assertEqual(result['status'],'TARGET_OBSERVED')
        self.assertEqual(result['at_utc_ms'],2000)

    def test_no_touch_remains_unresolved(self):
        self.assertEqual(first_touch([(1000,100,101)],'BUY',95,110)['status'],'UNRESOLVED')

    def test_reverse_clock_and_nonsecond_ticks_refused(self):
        for seq in ([(2000,100,101),(1000,100,101)],[(1001,100,101)]):
            with self.assertRaises(ValueError): first_touch(seq,'BUY',95,105)

    def test_crossed_quote_and_invalid_orientation_refused(self):
        with self.assertRaises(ValueError):first_touch([(1000,101,100)],'BUY',95,105)
        with self.assertRaises(ValueError):first_touch([(1000,100,101)],'SELL',95,105)

    def test_distinct_seconds_preserve_observed_order(self):
        result=first_touch([(1000,100,101),(2000,95,96),(3000,110,111)],'BUY',96,109)
        self.assertEqual(result['status'],'STOP_OBSERVED')
        self.assertEqual(result['at_utc_ms'],2000)

if __name__=='__main__':unittest.main()
