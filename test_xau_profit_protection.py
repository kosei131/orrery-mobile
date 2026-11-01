import unittest
from orrery_xau_profit_protection import replay

class ProtectionTests(unittest.TestCase):
    def run_policy(self,bars,policy,side='BUY',horizon=3):
        return replay(bars,side=side,policy=policy,spread=0,distance=10,horizon=horizon)
    def test_no_retroactive_breakeven_in_trigger_bar(self):
        b=[(0,100,111,95,100),(60,100,101,99,100)]
        r=self.run_policy(b,'PRICE_BE_AFTER_1R');self.assertEqual(r['r'],0)
    def test_same_bar_stop_first(self):
        r=self.run_policy([(0,100,125,89,100)],'HALF_AT_1R_AND_PRICE_BE')
        self.assertEqual(r['r'],-1);self.assertEqual(r['partial_r'],0)
    def test_partial_profit_does_not_make_unresolved_position_closed(self):
        r=self.run_policy([(0,100,111,99,110)],'HALF_AT_1R')
        self.assertEqual(r['partial_r'],.5);self.assertIsNone(r['r'])
    def test_breakeven_can_remove_original_winner(self):
        b=[(0,100,111,99,110),(60,110,112,99,110),(120,110,121,105,120)]
        self.assertEqual(self.run_policy(b,'BASELINE_2R')['r'],2)
        self.assertEqual(self.run_policy(b,'PRICE_BE_AFTER_1R')['r'],0)
    def test_gap_stop_worse_than_price_breakeven(self):
        b=[(0,100,111,99,110),(60,95,99,94,96)]
        self.assertEqual(self.run_policy(b,'PRICE_BE_AFTER_1R')['r'],-.5)
    def test_partial_total_and_sell_symmetry(self):
        b=[(0,100,111,99,110),(60,110,121,105,120)]
        self.assertEqual(self.run_policy(b,'HALF_AT_1R')['r'],1.5)
        s=[(0,100,101,89,90),(60,90,95,79,80)]
        self.assertEqual(self.run_policy(s,'HALF_AT_1R',side='SELL')['r'],1.5)
