import csv
from hashlib import sha256
from pathlib import Path
import tempfile
import unittest
from orrery_m1_revision_compare import compare,PREFIX


class RevisionCompareTests(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup)
        self.root=Path(t.name);self.old=self.root/'old.csv';self.new=self.root/'new.csv'
        self.write(self.old,[0,2]);self.write(self.new,[0,2])
        self.targets=[dict(start_utc='2026-09-02T22:01:00Z',end_utc_exclusive='2026-09-02T22:02:00Z')]

    def write(self,path,minutes,price=100):
        with path.open('w',newline='') as f:
            w=csv.writer(f);w.writerow(['datetime','open','high','low','close','volume'])
            for m in minutes:w.writerow([f'2026-09-02T22:{m:02d}:00Z',price,price+1,price-1,price,10])

    def call(self,**extra):
        kw=dict(original_sha256=sha256(self.old.read_bytes()).hexdigest(),
            candidate_sha256=sha256(self.new.read_bytes()).hexdigest(),candidate_revision='a'*40,
            candidate_url=PREFIX+'a'*40+'/XAUUSD_1m.csv',target_intervals=self.targets)
        return compare(self.old,self.new,**dict(kw,**extra))

    def test_identical_revision_does_not_explain_absent_minute(self):
        r=self.call();self.assertTrue(r['byte_identical'])
        self.assertEqual(r['requested_minutes_still_absent'],1)
        self.assertEqual(r['no_update_or_missing_cause'],'UNRESOLVED')
        self.assertFalse(r['history_merged']);self.assertIsNone(r['actual_profit_usd'])

    def test_added_requested_bar_is_detected_but_never_automatically_accepted(self):
        self.write(self.new,[0,1,2]);r=self.call()
        self.assertEqual(r['requested_minutes_present'],1)
        self.assertEqual(r['added_rows'],1)
        self.assertEqual(r['changed_overlap_ohlc_rows'],0)
        self.assertFalse(r['repaired_history_accepted'])
        self.assertFalse(r['source_identity_authenticated'])

    def test_revised_overlap_prices_are_counted(self):
        self.write(self.new,[0,1,2],price=101);r=self.call()
        self.assertEqual(r['changed_overlap_ohlc_rows'],2)
        self.assertEqual(r['requested_minutes_present'],1)
        self.assertFalse(r['history_merged'])

    def test_missing_retained_bar_is_separate_from_requested_minute(self):
        self.write(self.new,[2]);r=self.call()
        self.assertEqual(r['removed_rows'],1)
        self.assertEqual(r['requested_minutes_still_absent'],1)

    def test_wrong_hash_feed_url_or_overlapping_target_rejected(self):
        for change in (dict(candidate_sha256='0'*64),dict(candidate_url='https://another-feed.test/a.csv'),
                       dict(target_intervals=self.targets*2)):
            with self.subTest(change=change),self.assertRaises(ValueError):self.call(**change)

    def test_non_utc_duplicates_and_invalid_ohlc_rejected(self):
        for text in ('2026-09-02T22:00:00+01:00,100,101,99,100,10\n',
                     '2026-09-02T22:00:00Z,100,101,99,100,10\n'*2,
                     '2026-09-02T22:00:00Z,100,101,102,100,10\n'):
            self.new.write_text('datetime,open,high,low,close,volume\n'+text)
            with self.subTest(text=text),self.assertRaises(ValueError):self.call()
