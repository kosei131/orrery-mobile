import unittest
from lsr02 import advance, risk_gate, hypothesis_targets

class Gates(unittest.TestCase):
    def test_no_skipping(self):
        self.assertEqual(advance('WATCH', {'risk_checked':True}), 'WATCH')
        self.assertEqual(advance('WATCH', {'htf_context':1,'sweep_closed':True}), 'WATCH')
        self.assertEqual(advance('WATCH', {'htf_context':True,'sweep_closed':True}), 'SWEEP')
        self.assertEqual(advance('INVALID', {'risk_checked':True}), 'INVALID')
        self.assertEqual(advance('READY', {}), 'INVALID')
    def test_risk(self):
        base=dict(equity=100000,risk_fraction=.0025,existing_risk=0,max_total_risk=500,remaining_loss_budget=1000,entry=100,sl=99,tp=103,side='BUY',cost=10,consecutive_losses=0,loss_stop=3,data_ok=True,news_clear=True,spread_ok=True)
        self.assertTrue(risk_gate(**base))
        for change in [dict(news_clear=False),dict(existing_risk=300),dict(consecutive_losses=3),dict(risk_fraction=.01),dict(remaining_loss_budget=260),dict(tp=102),dict(equity=float('nan'))]:
            self.assertFalse(risk_gate(**(base|change)))
    def test_hypotheses_separate(self):
        t=hypothesis_targets('BUY',100,99,2)
        self.assertAlmostEqual(t['A_range_2_6'],105.2)
        self.assertAlmostEqual(t['B_gross_rr_2_6'],102.6)
        self.assertIsNone(t['C_undefined'])

if __name__=='__main__': unittest.main()
