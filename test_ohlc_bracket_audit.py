import unittest
from orrery_ohlc_bracket_audit import audit_bar

class BracketTests(unittest.TestCase):
    def buy(self,**bar):return audit_bar(side='BUY',entry=100,stop=99,target=102,bar=bar)
    def sell(self,**bar):return audit_bar(side='SELL',entry=100,stop=101,target=98,bar=bar)
    def test_buy_gap_both_is_not_fixed_minus_one(self):
        r=self.buy(open=98,high=103,low=97,close=100)
        self.assertEqual(r['gross_reference_r'],-2);self.assertTrue(r['both_touched'])
        self.assertEqual(r['status'],'OPEN_AT_OR_BEYOND_STOP');self.assertFalse(r['fill_verified'])
    def test_sell_gap_both_is_not_fixed_minus_one(self):
        self.assertEqual(self.sell(open=102,high=103,low=97,close=100)['gross_reference_r'],-2)
    def test_non_gap_both_remains_unknown(self):
        for r in (self.buy(open=100,high=103,low=98,close=100),self.sell(open=100,high=103,low=97,close=100)):
            self.assertIsNone(r['gross_reference_r']);self.assertTrue(r['intrabar_order_unknown'])
            self.assertEqual(r['stop_first_sensitivity_r'],-1)
    def test_single_stop_and_target_for_both_directions(self):
        self.assertEqual(self.buy(open=100,high=101,low=98,close=100)['gross_reference_r'],-1)
        self.assertEqual(self.buy(open=100,high=103,low=100,close=101)['gross_reference_r'],2)
        self.assertEqual(self.sell(open=100,high=102,low=99,close=100)['gross_reference_r'],-1)
        self.assertEqual(self.sell(open=100,high=100,low=97,close=99)['gross_reference_r'],2)
    def test_target_gap_is_explicit_assumption_even_if_both_touched(self):
        r=self.buy(open=103,high=104,low=98,close=100)
        self.assertEqual(r['gross_reference_r'],3);self.assertTrue(r['open_fill_assumption'])
        self.assertFalse(r['fill_verified']);self.assertIsNone(r['actual_profit_usd'])
    def test_no_touch_is_not_zero_profit(self):
        r=self.buy(open=100,high=101,low=100,close=100)
        self.assertIsNone(r['gross_reference_r']);self.assertFalse(r['execution_allowed'])
    def test_nonfinite_and_invalid_ohlc_rejected(self):
        for value in ('NaN','Infinity',True,-1):
            with self.assertRaises(ValueError):self.buy(open=value,high=103,low=97,close=100)
        with self.assertRaises(ValueError):self.buy(open=104,high=103,low=97,close=100)
    def test_invalid_side_or_geometry_rejected(self):
        for side,stop in (('LONG',99),('BUY',100),('SELL',99)):
            with self.assertRaises(ValueError):audit_bar(side=side,entry=100,stop=stop,target=102,bar=dict(open=100,high=103,low=98,close=100))

if __name__=='__main__':unittest.main()
