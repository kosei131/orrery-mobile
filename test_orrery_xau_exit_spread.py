"""Regression coverage for explicitly hypothetical bid/ask exit evaluation."""
import unittest
from orrery_xau_hypothetical_pnl import evaluate_exit_bar
class ExitTests(unittest.TestCase):
    def test_sell_target_blocked_by_ask_spread(self):
        self.assertIsNone(evaluate_exit_bar("SELL",100,106,94,101,93.7,.6))
        self.assertEqual(evaluate_exit_bar("SELL",100,106,94,101,93.3,.6),"target")
    def test_sell_stop_triggered_by_ask_spread(self):
        self.assertEqual(evaluate_exit_bar("SELL",100,106,94,105.5,99,.6),"stop")
    def test_buy_target_and_stop(self):
        self.assertEqual(evaluate_exit_bar("BUY",100,94,112,113,98,.6),"target")
        self.assertEqual(evaluate_exit_bar("BUY",100,94,112,111,93,.6),"stop")
    def test_ambiguous_bar_assumes_stop(self):
        self.assertEqual(evaluate_exit_bar("SELL",100,106,94,106,92,.6),"stop")
    def test_invalid_side_rejected(self):
        with self.assertRaises(ValueError):
            evaluate_exit_bar("UNKNOWN",100,94,112,115,90,.6)
if __name__=="__main__":unittest.main()
