import csv
import tempfile
import unittest
from pathlib import Path
from orrery_real_bars_lsr_bridge import load

class BridgeTest(unittest.TestCase):
    def test_contiguous_close_time_and_gap_rejection(self):
        with tempfile.TemporaryDirectory() as d:
            f=Path(d)/"bars.csv"
            with f.open("w",newline="") as out:
                w=csv.writer(out)
                w.writerow(["timestamp_utc","bid_open","bid_high","bid_low","bid_close"])
                for minute in (0,5,15):
                    w.writerow([f"2026-09-01T00:{minute:02d}:00+00:00",100,102,99,101])
            r=load(f,"M5")
            self.assertEqual(r["bars"][0]["close_time"]-r["bars"][0]["open_time"],300)
            self.assertEqual(len(r["gaps"]),1)
            self.assertFalse(r["safe_for_direct_replay"])
if __name__=="__main__":unittest.main()
