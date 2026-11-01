import io
import tempfile
import unittest
import zipfile
from pathlib import Path
from orrery_histdata_m1_import import convert

class HistDataM1Tests(unittest.TestCase):
    def test_fixed_est_to_utc_and_bid_only(self):
        with tempfile.TemporaryDirectory() as d:
            zpath=Path(d)/"month.zip"
            with zipfile.ZipFile(zpath,"w") as z:
                z.writestr("DAT_ASCII_XAUUSD_M1_202610.csv",
                    "20261022 080000;4059.000;4060.000;4058.000;4059.500;0\n"
                    "20261022 080100;4059.500;4061.000;4059.000;4060.200;0\n")
            dst=Path(d)/"m1.csv"
            report=convert(zpath,dst,"XAUUSD")
            self.assertEqual(report["bars"],2)
            self.assertEqual(report["first_utc"],"2026-10-22T13:00:00+00:00")
            self.assertFalse(report["tick_execution_validated"])
            self.assertIn("bid_close",dst.read_text())
    def test_invalid_ohlc_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            zpath=Path(d)/"month.zip"
            with zipfile.ZipFile(zpath,"w") as z:
                z.writestr("DAT_ASCII_USDJPY_M1_202610.csv",
                    "20261022 080000;150;149;148;150;0\n")
            with self.assertRaises(ValueError):
                convert(zpath,Path(d)/"out.csv","USDJPY")

if __name__=="__main__":
    unittest.main()
