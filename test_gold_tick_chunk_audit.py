from datetime import datetime,timezone
from hashlib import sha256
import json,zipfile
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
import orrery_gold_tick_chunk_audit as gold


class GoldChunkTests(unittest.TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.source=self.root/'source.zip';self.out=self.root/'out';self.now=datetime(2026,11,3,tzinfo=timezone.utc)

    def source_file(self,data,name='DAT_ASCII_XAUUSD_T_202610.csv'):
        with zipfile.ZipFile(self.source,'w',zipfile.ZIP_DEFLATED) as z:z.writestr(name,data)
        return sha256(self.source.read_bytes()).hexdigest()

    def run_it(self,pin):return gold.run(self.source,self.out,expected_sha256=pin,month='202610',now=self.now)

    def test_partition_keeps_every_original_byte_and_boundary_record(self):
        raw=b'20261001 000000000,4000,4000.2,0\r\n20261001 000001000,4001,4001.2,0\r\n20261001 000001000,4002,4002.2,0\r\n'
        pin=self.source_file(raw)
        with patch.object(gold,'CHUNK_ROWS',1):r=self.run_it(pin)
        self.assertEqual(r['chunk_count'],3);self.assertEqual(r['ticks'],3)
        self.assertTrue(r['byte_exact_reconstruction_verified'])
        self.assertEqual(r['original_csv_sha256'],sha256(raw).hexdigest())
        self.assertEqual(r['reconstructed_csv_sha256'],sha256(raw).hexdigest())
        self.assertEqual(r['same_timestamp_adjacent_pairs'],1)
        self.assertEqual(sha256(self.source.read_bytes()).hexdigest(),pin)
        recovered=b''.join(zipfile.ZipFile(self.out/c['path']).read('DAT_ASCII_XAUUSD_T_202610.csv') for c in r['chunks'])
        self.assertEqual(recovered,raw)

    def test_reverse_clock_crossing_chunk_boundary_remains_visible(self):
        pin=self.source_file('20261001 000001000,4000,4000.2,0\n20261001 000000000,4000,4000.2,0\n')
        with patch.object(gold,'CHUNK_ROWS',1):r=self.run_it(pin)
        self.assertEqual(r['out_of_order_pairs'],1);self.assertEqual(r['maximum_backward_step_msc'],1000)
        self.assertEqual(sum(c['out_of_order_pairs'] for c in r['chunks']),0)
        self.assertFalse(r['raw_ticks_reordered']);self.assertFalse(r['chronological_bar_exported'])
        self.assertFalse(r['strategy_replay_allowed'])

    def test_expanded_budget_is_checked_before_partitioning(self):
        pin=self.source_file('20261001 000000000,4000,4000.2,0\n')
        with patch.object(gold,'MAX_TOTAL',10):
            with self.assertRaises(ValueError):self.run_it(pin)
        self.assertFalse(self.out.exists())

    def test_wrong_gold_identity_hash_and_unsafe_path_fail(self):
        text='20261001 000000000,4000,4000.2,0\n'
        for name in ('DAT_ASCII_USDJPY_T_202610.csv','../DAT_ASCII_XAUUSD_T_202610.csv'):
            pin=self.source_file(text,name)
            with self.assertRaises(ValueError):self.run_it(pin)
        self.source_file(text)
        with self.assertRaises(ValueError):self.run_it('0'*64)

    def test_invalid_quote_and_schema_never_publish_an_output(self):
        for raw in ('20261001 000000000,4001,4000,0\n','20261001 000000000,0,4000,0\n',
                    '20261001 000000000,4000,4001,NaN\n','20261001 000000000;4000;4001;0\n'):
            with self.subTest(raw=raw):
                pin=self.source_file(raw)
                with self.assertRaises(ValueError):self.run_it(pin)
                self.assertFalse(self.out.exists())

    def test_existing_output_is_preserved(self):
        pin=self.source_file('20261001 000000000,4000,4000.2,0\n')
        self.out.mkdir();(self.out/'keep').write_text('preserve')
        with self.assertRaises(FileExistsError):self.run_it(pin)
        self.assertEqual((self.out/'keep').read_text(),'preserve')

    def test_actual_gold_receipt_preserves_chunk_and_replay_guards(self):
        root=Path(__file__).resolve().parent
        r=json.loads((root/'research_evidence/local-history-20261101/gold_histdata_tick_audit_20261103.json').read_text())
        self.assertEqual(r['symbol'],'XAUUSD');self.assertEqual(r['ticks'],6446239)
        self.assertEqual(r['original_csv_bytes'],290080755);self.assertEqual(r['chunk_count'],6)
        self.assertTrue(r['byte_exact_reconstruction_verified'])
        self.assertEqual(r['original_csv_sha256'],r['reconstructed_csv_sha256'])
        self.assertEqual(sum(c['ticks'] for c in r['chunks']),r['ticks'])
        for c in r['chunks']:
            self.assertLessEqual(c['csv_bytes'],r['chunk_csv_byte_limit'])
            self.assertLessEqual(c['ticks'],r['chunk_row_limit'])
            self.assertFalse(c['chronological_bar_exported'])
        self.assertFalse(r['strategy_replay_allowed']);self.assertIsNone(r['win_rate_pct']);self.assertIsNone(r['account_return_pct'])
        for name,pin in r['engine_code_sha256'].items():self.assertEqual(sha256((root/name).read_bytes()).hexdigest(),pin)
