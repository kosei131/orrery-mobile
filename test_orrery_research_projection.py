import unittest
from orrery_research_projection import projection

class ResearchProjectionTests(unittest.TestCase):
    def test_buy_and_sell_levels_are_research_only(self):
        for side,entry,stop,target in [('BUY',3000,2990,3020),('SELL',3000,3010,2980)]:
            with self.subTest(side=side):
                r=projection(dict(side=side,stop=stop,target=target,known_at_msc=300000),
                    candidate_id='XAUUSD:example',entry_reference=entry,
                    observed_close=entry,as_of_s=300)
                self.assertEqual(r['reference_rr'],2)
                self.assertEqual(r['lines']['structural_sl'],stop)
                self.assertEqual(r['lines']['reference_tp'],target)
                self.assertIsNone(r['forecast_candles'])
                self.assertIsNone(r['forecast_confidence'])
                self.assertFalse(r['execution_allowed'])

    def test_future_information_and_invalid_levels_rejected(self):
        p=dict(side='BUY',stop=2990,target=3020,known_at_msc=301000)
        with self.assertRaises(ValueError):
            projection(p,candidate_id='x',entry_reference=3000,observed_close=3000,as_of_s=300)
        with self.assertRaises(ValueError):
            projection(dict(p,known_at_msc=300000,target=2980),
                candidate_id='x',entry_reference=3000,observed_close=3000,as_of_s=300)

if __name__=='__main__': unittest.main()
