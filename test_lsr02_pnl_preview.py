import unittest
from lsr02_pnl_preview import preview

CFG=dict(take_profit=4530,stop_loss=4490,contract_units_per_lot=100,
         usd_per_quote_unit=1,estimated_round_trip_cost_usd=5,max_total_stop_loss_usd=100)
class PreviewTests(unittest.TestCase):
    def test_single_long_tp_sl_and_cost(self):
        r=preview([dict(side="BUY",entry=4500,lots=".05")],**CFG)
        self.assertEqual(r["net_tp_usd"],"145.00")
        self.assertEqual(r["net_sl_usd"],"-55.00")
        self.assertFalse(r["execution_allowed"])
        self.assertTrue(r["risk_budget_ok"])
    def test_multiple_entries_and_cap(self):
        r=preview([dict(side="BUY",entry=4500,lots=".05"),
                   dict(side="BUY",entry=4495,lots=".05")],**CFG)
        self.assertEqual(r["net_tp_usd"],"320.00")
        self.assertEqual(r["net_sl_usd"],"-80.00")
        self.assertTrue(r["risk_budget_ok"])
        constrained=dict(CFG,max_total_stop_loss_usd=75)
        self.assertFalse(preview([dict(side="BUY",entry=4500,lots=".05"),
             dict(side="BUY",entry=4495,lots=".05")],**constrained)["risk_budget_ok"])
    def test_reverse_sell(self):
        c=dict(CFG,take_profit=4470,stop_loss=4510)
        r=preview([dict(side="SELL",entry=4500,lots=".1")],**c)
        self.assertEqual(r["net_tp_usd"],"295.0")
        self.assertEqual(r["net_sl_usd"],"-105.0")
    def test_invalid_mixed_and_nonfinite(self):
        with self.assertRaises(ValueError):
            preview([dict(side="BUY",entry=4500,lots=".1"),dict(side="SELL",entry=4500,lots=".1")],**CFG)
        with self.assertRaises(ValueError):
            preview([dict(side="BUY",entry=4500,lots=float("nan"))],**CFG)
        with self.assertRaises(ValueError):
            preview([dict(side="BUY",entry=4500,lots=".1")],**dict(CFG,usd_per_quote_unit=0))
if __name__=="__main__":unittest.main()
