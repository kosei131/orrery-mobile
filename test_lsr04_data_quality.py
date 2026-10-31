import unittest
from lsr04_data_quality import audit_quality
class QualityTests(unittest.TestCase):
 def ev(self,close,at,signal):
  return dict(symbol="XAUUSD",timeframe="M5",source="sample",revision_id="v1",
              closed_at=close,observed_at=at,signal=signal)
 def test_missing_late_revised(self):
  rows=[self.ev(300,301,"BUY"),self.ev(300,900,"NONE"),self.ev(600,1200,"NONE")]
  r=audit_quality(symbol="XAUUSD",expected_closes=[300,600,900],events=rows,
      source="sample",revision_id="v1",max_delay_seconds=300)
  self.assertEqual((r["observed_bars"],r["missing_bars"],r["late_first_observations"],r["bars_with_revisions"]),(2,1,1,1))
  self.assertFalse(r["execution_allowed"])
 def test_complete_not_proof(self):
  r=audit_quality(symbol="XAUUSD",expected_closes=[300],events=[self.ev(300,301,"NONE")],
                  source="sample",revision_id="v1")
  self.assertEqual(r["verdict"],"OBSERVATIONS_COMPLETE_NOT_PROOF")
 def test_mixed_provenance_fails(self):
  with self.assertRaises(ValueError):
   audit_quality(symbol="XAUUSD",expected_closes=[300],events=[dict(self.ev(300,301,"BUY"),source="other")],source="sample",revision_id="v1")
if __name__=="__main__":unittest.main()
