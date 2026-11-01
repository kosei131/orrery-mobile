import unittest
from orrery_xau_loss_diagnostic import excursions

class ExcursionTests(unittest.TestCase):
    def trade(self,**changes):
        return dict(dict(entry_assumed=100.,initial_stop_distance=10.,touch_close_utc=0,
                         exit_time_utc=60,side='BUY'),**changes)
    def test_stop_bar_later_high_is_excluded(self):
        r=excursions([(0,102.,99.,100.),(60,130.,85.,90.)],self.trade(),.6)
        self.assertEqual(r['mfe_r'],.2);self.assertEqual(r['mae_r'],.1)
    def test_same_minute_exit_is_unknown(self):
        r=excursions([(0,130.,85.,90.)],self.trade(exit_time_utc=0),.6)
        self.assertIsNone(r['mfe_r']);self.assertIsNone(r['mae_r'])
    def test_timeout_close_does_not_include_next_bar(self):
        r=excursions([(0,102.,99.,101.),(60,140.,80.,100.)],self.trade(),.6)
        self.assertEqual(r['fully_elapsed_minutes_observed'],1)
        self.assertEqual(r['mfe_r'],.2)
    def test_sell_uses_assumed_ask(self):
        r=excursions([(0,101.,95.,100.)],self.trade(side='SELL'),1.)
        self.assertEqual(r['mfe_r'],.4);self.assertEqual(r['mae_r'],.2)
    def test_wrong_side_and_risk_rejected(self):
        for c in (dict(side='BAD'),dict(initial_stop_distance=0)):
            with self.assertRaises(ValueError):excursions([],self.trade(**c),.6)
