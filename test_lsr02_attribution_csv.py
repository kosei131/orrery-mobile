import csv
import tempfile
import unittest
from pathlib import Path
from lsr02_attribution_csv import FIELDS, load_report

def row():
 return dict(id="A",symbol="XAUUSD",strategy="SCALP",opened_at="1",closed_at="31",
  gross_pnl_usd="100",cost_usd="10",max_adverse_usd="30",max_favorable_usd="100",
  max_simultaneous_lots="1",averaging_added="false",support_confirmed="true",
  two_six_near="false",spread_widened="false",news_window="false",regime_changed="false")

class ImportTests(unittest.TestCase):
 def write(self,p,r,header=FIELDS):
  with p.open("w",newline="",encoding="utf-8") as f:
   w=csv.DictWriter(f,fieldnames=header);w.writeheader();w.writerow(r)
 def test_import_and_unverified_provenance(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp)/"trades.csv";self.write(p,row())
   r=load_report(p);self.assertEqual(r["total_net_usd"],90.0)
   self.assertEqual(r["data_provenance"],"LOCAL_NORMALIZED_CSV_UNVERIFIED")
   self.assertFalse(r["execution_allowed"])
 def test_missing_field_and_invented_flags_rejected(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp)/"trades.csv";r=row();r["news_window"]="maybe";self.write(p,r)
   with self.assertRaises(ValueError):load_report(p)
   self.write(p,{k:v for k,v in row().items() if k in FIELDS[:-1]},FIELDS[:-1])
   with self.assertRaises(ValueError):load_report(p)
if __name__=="__main__":unittest.main()
