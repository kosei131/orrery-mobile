import unittest
from lsr02_regime_diagnostics import diagnose
class DiagnosticsTests(unittest.TestCase):
 def test_reconciled_attribution(self):
  r=diagnose([dict(rr=2.6,net_profit=-10,by_regime={
   "RANGE":dict(net_usd=-30,trades=8),
   "TREND":dict(net_usd=20,trades=5)})])
  self.assertEqual(r["scenarios"][0]["worst_regime"],"RANGE")
  self.assertTrue(r["requires_new_replay"])
  self.assertFalse(r["execution_allowed"])
 def test_unreconciled_fails(self):
  with self.assertRaises(ValueError):diagnose([dict(net_profit=100,by_regime={
   "RANGE":dict(net_usd=-30,trades=8)})])
if __name__=="__main__":unittest.main()
