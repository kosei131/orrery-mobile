import csv
import datetime as dt
import tempfile
import unittest
from pathlib import Path
from orrery_m1_complete_bars import aggregate

class CompleteBarsTests(unittest.TestCase):
    def test_complete_m5_and_missing_m15(self):
        with tempfile.TemporaryDirectory() as d:
            src=Path(d)/"m1.csv"
            with src.open("w",newline="") as fp:
                w=csv.writer(fp)
                w.writerow(["timestamp_utc","bid_open","bid_high","bid_low","bid_close"])
                start=dt.datetime(2026,10,22,8,tzinfo=dt.timezone.utc)
                for m in range(15):
                    if m==7:
                        continue
                    w.writerow([(start+dt.timedelta(minutes=m)).isoformat(),100,101,99,100.5])
            result=aggregate(src,Path(d)/"m5.csv","M5")
            self.assertEqual(result["complete_bars"],2)
            self.assertEqual(result["incomplete_bars_rejected"],1)
            result=aggregate(src,Path(d)/"m15.csv","M15")
            self.assertEqual(result["complete_bars"],0)
            self.assertEqual(result["incomplete_bars_rejected"],1)

if __name__=="__main__":
    unittest.main()
