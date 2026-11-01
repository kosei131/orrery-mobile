import unittest
from lsr02_seeded_replay import simulate
class VariantTests(unittest.TestCase):
 def test_same_series_across_indicator_variants(self):
  common=dict(seed=260427,steps=350)
  base=simulate(**common)
  adx=simulate(**common,use_adx=True)
  atr=simulate(**common,use_atr_stop=True)
  both=simulate(**common,use_adx=True,use_atr_stop=True)
  self.assertEqual(len({x['price_series_sha256'] for x in (base,adx,atr,both)}),1)
  for x in (base,adx,atr,both):self.assertFalse(x['execution_allowed'])
 def test_bad_switches(self):
  with self.assertRaises(ValueError):simulate(use_adx=1)
if __name__=='__main__':unittest.main()
