import copy
import unittest
from orrery_gold_three_hypotheses import scan

def candles(n=23):
    return [dict(close_time=(i+1)*900,open=1000,high=1010,low=990,close=1000)
            for i in range(n)]

class ThreeHypothesesTests(unittest.TestCase):
    def test_sweep_buy_only_after_confirmation(self):
        b=candles()
        b[21].update(low=980,close=1000)
        b[22].update(high=1030,close=1020)
        r=scan(b)
        s=[x for x in r['signals'] if x['family']=='SWEEP_REVERSAL']
        self.assertEqual(len(s),1)
        self.assertEqual(s[0]['side'],'BUY')
        self.assertEqual(s[0]['signal_known_at'],b[-1]['close_time'])
        self.assertIsNone(s[0]['entry_price_scaled'])

    def test_sweep_not_known_until_confirmation(self):
        b=candles()
        b[21].update(low=980)
        self.assertEqual(scan(b[:-1])['signal_count_by_family']['SWEEP_REVERSAL'],0)

    def test_failed_break_reentry_buy(self):
        b=candles()
        b[21].update(low=970,close=980)
        b[22].update(open=980,low=975,close=1000)
        x=scan(b)['signals']
        self.assertEqual([(s['family'],s['side']) for s in x],
                         [('FAILED_BREAK_REENTRY','BUY')])

    def test_trend_breakout_buy(self):
        b=candles()
        b[20].update(close=1002)
        b[21].update(close=1004)
        b[22].update(close=1020,high=1030)
        self.assertIn('TREND_CONTINUATION',scan(b)['signal_count_by_family'])
        self.assertEqual(scan(b)['signal_count_by_family']['TREND_CONTINUATION'],1)

    def test_future_data_cannot_change_past(self):
        b=candles()
        b[21].update(low=980)
        b[22].update(close=1020,high=1030)
        earlier=scan(b)['signals']
        later=copy.deepcopy(b)+[dict(close_time=24*900,open=1020,low=950,high=1050,close=1040)]
        self.assertEqual([x for x in scan(later)['signals'] if x['signal_known_at']<=23*900],earlier)

    def test_gap_cannot_be_bridged(self):
        b=candles()
        b[21].update(low=980)
        b[22].update(close=1020,high=1030)
        self.assertEqual(scan(b)['signal_count_by_family']['SWEEP_REVERSAL'],1)
        for x in b[20:]:x['close_time']+=900
        self.assertEqual(scan(b)['signal_count_by_family']['SWEEP_REVERSAL'],0)

    def test_duplicate_clock_rejected(self):
        b=candles()
        b[1]['close_time']=b[0]['close_time']
        with self.assertRaises(ValueError):scan(b)

    def test_malformed_price_rejected(self):
        b=candles();b[0]['low']=1100
        with self.assertRaises(ValueError):scan(b)

    def test_preliminary_empty_without_lookback(self):
        r=scan(candles(10))
        self.assertEqual(sum(r['signal_count_by_family'].values()),0)
        self.assertIsNone(r['net_expectancy_r'])

    def test_no_fake_outcomes(self):
        r=scan(candles())
        self.assertFalse(r['real_price_results_verified'])
        self.assertFalse(r['execution_allowed'])
        self.assertIsNone(r['account_return_pct'])

if __name__=='__main__':
    unittest.main()
