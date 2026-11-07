import csv
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from orrery_gold_three_hypotheses_public import run

class PublicThreeHypothesesTests(unittest.TestCase):
    def setUp(self):
        self.tmp=TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.raw=self.root/'source.csv'
        self.raw.write_text('pinned raw bytes',encoding='utf-8')
        self.pin=sha256(self.raw.read_bytes()).hexdigest()
        self.m15=self.root/'m15.csv'

    def write(self,*,gap=False):
        with self.m15.open('w',newline='') as f:
            w=csv.writer(f)
            w.writerow(['timestamp_utc','bid_open','bid_high','bid_low','bid_close'])
            for i in range(23):
                from datetime import datetime,timezone,timedelta
                t=datetime(2026,10,1,tzinfo=timezone.utc)+timedelta(minutes=15*(i+(i>=20 if gap else 0)))
                low=980 if i==21 else 990
                high=1030 if i==22 else 1010
                close=1020 if i==22 else 1000
                w.writerow([t.isoformat(),'1000',high,low,close])

    def test_pinned_public_replay(self):
        self.write()
        r=run(self.raw,self.m15,expected_sha256=self.pin)
        self.assertEqual(r['input_candles'],23)
        self.assertEqual(r['signal_count_by_family']['SWEEP_REVERSAL'],1)
        self.assertFalse(r['quote_basis_verified'])
        self.assertIsNone(r['net_expectancy_r'])

    def test_gap_censors_hypothesis(self):
        self.write(gap=True)
        r=run(self.raw,self.m15,expected_sha256=self.pin)
        self.assertEqual(r['signal_count_by_family']['SWEEP_REVERSAL'],0)

    def test_source_pin_required(self):
        self.write()
        with self.assertRaises(ValueError):
            run(self.raw,self.m15,expected_sha256='0'*64)

    def test_unaligned_timestamp_rejected(self):
        self.write()
        t=self.m15.read_text().replace('2026-10-01T00:00:00+00:00','2026-10-01T00:01:00+00:00')
        self.m15.write_text(t)
        with self.assertRaises(ValueError):
            run(self.raw,self.m15,expected_sha256=self.pin)

    def test_non_exact_decimal_rejected(self):
        self.write()
        t=self.m15.read_text().replace('1000,1010,990,1000','1000.0000001,1010,990,1000',1)
        self.m15.write_text(t)
        with self.assertRaises(ValueError):
            run(self.raw,self.m15,expected_sha256=self.pin)

if __name__=='__main__':
    unittest.main()
