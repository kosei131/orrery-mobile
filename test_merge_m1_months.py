import csv
import tempfile
import unittest
from pathlib import Path
from orrery_merge_m1_months import merge, FIELDS

class MergeMonthsTest(unittest.TestCase):
    def test_merge_orders_months_and_rejects_overlap(self):
        with tempfile.TemporaryDirectory() as d:
            a,b=Path(d)/"a.csv",Path(d)/"b.csv"
            def write(p,t):
                with p.open("w",newline="") as f:
                    w=csv.writer(f);w.writerow(FIELDS);w.writerow([t,1,2,1,2])
            write(a,"2026-05-01T00:00:00+00:00")
            write(b,"2026-04-30T23:59:00+00:00")
            output=Path(d)/"joined.csv"
            report=merge([a,b],output)
            self.assertEqual(report["merged_m1_rows"],2)
            self.assertEqual(report["first_utc"],"2026-04-30T23:59:00+00:00")
            write(b,"2026-05-01T00:00:00+00:00")
            with self.assertRaisesRegex(ValueError,"overlapping"):
                merge([a,b],output)

if __name__=="__main__":
    unittest.main()
