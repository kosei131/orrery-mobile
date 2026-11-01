import tempfile
import unittest
import zipfile
from pathlib import Path
from orrery_histdata_pipeline import pipeline

class PipelineTests(unittest.TestCase):
    def test_monthly_zip_produces_auditable_csvs_not_profits(self):
        with tempfile.TemporaryDirectory() as d:
            source=Path(d)/"sample.zip"
            with zipfile.ZipFile(source,"w") as z:
                lines=[]
                for m in range(15):
                    lines.append(f"20261022 08{m:02d}00;4000;4001;3999;4000.5;0")
                z.writestr("DAT_ASCII_XAUUSD_M1_202610.csv","\n".join(lines)+"\n")
            dest=Path(d)/"output"
            report=pipeline(source,"XAUUSD",dest)
            self.assertEqual(report["import"]["bars"],15)
            self.assertEqual(report["timeframes"]["M5"]["complete_bars"],3)
            self.assertEqual(report["timeframes"]["M15"]["complete_bars"],1)
            self.assertEqual(report["timeframes"]["H4"]["complete_bars"],0)
            self.assertFalse(report["ready_for_strategy_replay"])
            self.assertIsNone(report["verified_profit_usd"])
            self.assertTrue((dest/"pipeline_manifest.json").exists())

if __name__=="__main__":
    unittest.main()
