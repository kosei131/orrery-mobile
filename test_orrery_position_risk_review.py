import unittest
from orrery_position_risk_review import inspect

class PositionRiskTests(unittest.TestCase):
    def test_known_contract_scenario_shows_tail_risk_without_order(self):
        r=inspect(side='BUY',entry=3909.56,current=3910.87,sl=3901.56,tp=3921.56,
            lots=1,usd_per_price_unit_per_lot=100,balance=6205.5,equity=6336.5,margin=3909.56)
        self.assertAlmostEqual(r['reference_open_pnl_usd'],131)
        self.assertAlmostEqual(r['gross_loss_to_sl_usd'],800)
        self.assertAlmostEqual(r['gross_gain_to_tp_usd'],1200)
        self.assertTrue(r['exceeds_research_risk_budget'])
        self.assertIsNone(r['estimated_fee_usd'])
        self.assertFalse(r['execution_allowed'])

    def test_invalid_stop_and_unknown_contract_are_rejected(self):
        base=dict(side='BUY',entry=3909.56,current=3910.87,sl=3901.56,tp=3921.56,
            lots=1,usd_per_price_unit_per_lot=100,balance=6205.5,equity=6336.5,margin=3909.56)
        with self.assertRaises(ValueError):inspect(**(base|{'sl':3915}))
        with self.assertRaises(ValueError):inspect(**(base|{'usd_per_price_unit_per_lot':None}))

if __name__=='__main__':unittest.main()
