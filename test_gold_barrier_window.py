import unittest
from orrery_gold_barrier_window import compare_barriers

class WindowTests(unittest.TestCase):
    def evaluate(self, quotes, side='BUY', stop=990, targets=None):
        return compare_barriers(quotes, entry_utc_ms=0, side=side, stop=stop,
                                targets=targets or {'small': 1010, 'normal': 1030})

    def test_small_target_but_normal_stop(self):
        r=self.evaluate([(0,1000,1005),(1000,1011,1016),(2000,989,994)])
        self.assertEqual(r['target_results']['small']['status'],'TARGET_OBSERVED')
        self.assertEqual(r['target_results']['normal']['status'],'STOP_OBSERVED')

    def test_same_second_is_ambiguous(self):
        r=self.evaluate([(0,1000,1005),(1000,1011,1016),(1000,989,994)])
        self.assertEqual(r['target_results']['small']['status'],'AMBIGUOUS_SAME_SECOND')

    def test_gap_censors_future_hit(self):
        r=self.evaluate([(0,1000,1005),(1000,1001,1006),(63000,1040,1045)])
        self.assertEqual(r['boundary'],'UNOBSERVED_GAP')
        self.assertEqual(r['target_results']['normal']['status'],'CENSORED_UNOBSERVED_GAP')

    def test_reversal_censors_without_sort(self):
        r=self.evaluate([(0,1000,1005),(2000,1002,1007),(1000,1040,1045)])
        self.assertEqual(r['boundary'],'CLOCK_REVERSAL')
        self.assertEqual(r['target_results']['small']['status'],'CENSORED_CLOCK_REVERSAL')

    def test_sell_exits_on_ask(self):
        r=self.evaluate([(0,1000,1005),(1000,992,997),(2000,1020,1025)],
                        side='SELL',stop=1020,targets={'small':998,'normal':980})
        self.assertEqual(r['target_results']['small']['status'],'TARGET_OBSERVED')
        self.assertEqual(r['target_results']['normal']['status'],'STOP_OBSERVED')

    def test_entry_second_excluded(self):
        r=self.evaluate([(0,999,1003),(0,1100,1105),(1000,1002,1007)])
        self.assertEqual(r['target_results']['small']['status'],'CENSORED_DATA_END')

    def test_no_post_entry_quotes(self):
        r=self.evaluate([(0,1000,1005)])
        self.assertEqual(r['target_results']['small']['status'],'CENSORED_NO_POST_ENTRY_QUOTES')

    def test_invalid_quote_even_after_gap(self):
        with self.assertRaises(ValueError):
            self.evaluate([(0,1000,1005),(70000,1000,999)])

    def test_invalid_barrier(self):
        with self.assertRaises(ValueError):
            self.evaluate([(0,1000,1005)],targets={'bad':989})

    def test_no_profit_or_execution_claim(self):
        r=self.evaluate([(0,1000,1005),(1000,1011,1016)])
        self.assertIsNone(r['actual_net_expectancy_r'])
        self.assertIsNone(r['account_return_pct'])
        self.assertFalse(r['execution_allowed'])
        self.assertFalse(r['backtest_ready'])

if __name__ == '__main__':
    unittest.main()
