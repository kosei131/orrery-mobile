from datetime import datetime,timezone
from io import BytesIO
import lzma
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from orrery_duka_source_probe import validate,probe,NoRedirect


def packed(rows):return lzma.compress(b''.join(struct.pack('>IIIff',*r) for r in rows))
GOOD=packed([(0,200100,200000,1,2),(1,200110,200010,1,2)])


class SourceProbeTests(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup)
        self.out=Path(t.name)/'new'
        self.hour=datetime(2026,9,2,12,tzinfo=timezone.utc)
        self.now=datetime(2026,11,1,tzinfo=timezone.utc)

    def test_raw_records_retain_order_and_unknown_scale(self):
        r=validate(GOOD)
        self.assertEqual(r['tick_count'],2)
        self.assertEqual(r['last_offset_msc'],1)
        self.assertFalse(r['price_scale_verified'])
        r=validate(packed([(0,2,1,0,0),(0,3,2,0,0)]))
        self.assertEqual(r['repeated_timestamp_pairs'],1)

    def test_invalid_price_volume_clock_and_order_rejected(self):
        for rows in ([(0,1,2,1,1)],[(0,2,1,float('nan'),1)],
                     [(3600000,2,1,1,1)],[(1,2,1,1,1),(0,2,1,1,1)]):
            with self.subTest(rows=rows),self.assertRaises(ValueError):validate(packed(rows))

    def test_decompressed_budget_enforced(self):
        with patch('orrery_duka_source_probe.MAX_DECODED',20):
            with self.assertRaises(ValueError):validate(GOOD)

    def test_truncated_concatenated_and_bad_framing_rejected(self):
        for raw in (GOOD[:-5],GOOD+GOOD,lzma.compress(b'invalid')):
            with self.subTest(raw=raw),self.assertRaises(ValueError):validate(raw)

    def test_redirect_to_paid_or_other_host_stopped(self):
        with self.assertRaisesRegex(ValueError,'Redirect refused'):
            NoRedirect().redirect_request(None,None,302,'Moved',{},'https://bucket.s3.amazonaws.com/paid')

    def test_success_is_separate_anonymous_archive_not_mt5_or_account_result(self):
        seen=[]
        def download(url):seen.append(url);return GOOD
        r=probe(self.hour,'XAUUSD',self.out,now=self.now,download=download)
        self.assertEqual(seen,['https://datafeed.dukascopy.com/datafeed/XAUUSD/2026/08/02/12h_ticks.bi5'])
        self.assertTrue((self.out/'source.bi5').exists())
        self.assertFalse(r['source_is_user_mt5']);self.assertFalse(r['merged_with_getdata'])
        self.assertFalse(r['paid_route_used']);self.assertIsNone(r['actual_profit_usd'])

    def test_http_error_is_blocked_without_fabricated_tick_count(self):
        def blocked(url):raise HTTPError(url,403,'forbidden',{},BytesIO(b''))
        r=probe(self.hour,'XAUUSD',self.out,now=self.now,download=blocked)
        self.assertEqual(r['http_status'],403)
        self.assertEqual(r['status'],'BLOCKED_SOURCE_FETCH_OR_VALIDATION')
        self.assertNotIn('tick_count',r)
        self.assertFalse((self.out/'source.bi5').exists())

    def test_existing_output_is_preserved(self):
        self.out.mkdir();keep=self.out/'keep';keep.write_text('keep')
        with self.assertRaises(FileExistsError):probe(self.hour,'USDJPY',self.out,now=self.now)
        self.assertEqual(keep.read_text(),'keep')

    def test_non_utc_or_unfinished_hour_rejected_before_output(self):
        for hour in (self.hour.replace(tzinfo=None),self.hour.replace(minute=1),self.now):
            with self.subTest(hour=hour),self.assertRaises(ValueError):
                probe(hour,'XAUUSD',self.out,now=self.now)
        self.assertFalse(self.out.exists())
