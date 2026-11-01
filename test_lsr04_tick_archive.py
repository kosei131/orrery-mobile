import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from lsr04_tick_archive import save_tick_archive, verify_tick_archive
import test_lsr04_tick_quality as fixtures


class ArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'archive'
        self.options=dict(symbol='XAUUSD',start_utc=fixtures.START,end_utc=fixtures.END,
            source='SYNTHETIC_TEST',broker_spec=fixtures.SPEC,max_spread_points=50,
            windows=[dict(start_utc=fixtures.START,end_utc=fixtures.END,accepted_ticks=3)])
        self.rows=[fixtures.tick(0),fixtures.tick(60),fixtures.tick(120)]

    def save(self, rows=None):
        return save_tick_archive(self.path,iter(self.rows if rows is None else rows),audit_options=self.options)

    def verify(self, saved, **kw):
        return verify_tick_archive(self.path,expected_manifest_sha256=saved['manifest_sha256'],**kw)

    def rewrite_manifest(self, manifest):
        data=(json.dumps(manifest,sort_keys=True,separators=(',',':'))+'\n').encode()
        (self.path/'manifest.json').write_bytes(data)
        return dict(manifest_sha256=hashlib.sha256(data).hexdigest())

    def test_stream_roundtrip_and_independent_pin(self):
        saved=self.save();r=self.verify(saved,expected_audit_config_sha256=saved['audit_config_sha256'])
        self.assertEqual(r['row_count'],3)
        self.assertEqual(r['audit']['counts']['valid_rows'],3)
        self.assertFalse(r['completeness_verified'])
        self.assertFalse(r['backtest_ready'])
        self.assertFalse(r['execution_allowed'])

    def test_existing_folder_not_overwritten(self):
        saved=self.save();old=(self.path/'ticks.jsonl').read_bytes()
        with self.assertRaises(FileExistsError):self.save()
        self.assertEqual((self.path/'ticks.jsonl').read_bytes(),old)
        self.verify(saved)

    def test_tick_byte_change_detected(self):
        saved=self.save();p=self.path/'ticks.jsonl'
        p.write_bytes(p.read_bytes().replace(b'100.1',b'100.2',1))
        with self.assertRaises(ValueError):self.verify(saved)

    def test_truncation_and_append_detected(self):
        saved=self.save();p=self.path/'ticks.jsonl';data=p.read_bytes()
        p.write_bytes(data[:-1])
        with self.assertRaises(ValueError):self.verify(saved)
        p.write_bytes(data+data.splitlines(keepends=True)[0])
        with self.assertRaises(ValueError):self.verify(saved)

    def test_audit_tampering_detected(self):
        saved=self.save();p=self.path/'audit.json'
        p.write_bytes(p.read_bytes().replace(b'false',b'true',1))
        with self.assertRaises(ValueError):self.verify(saved)

    def test_manifest_changed_even_if_locally_rehashed(self):
        saved=self.save();p=self.path/'manifest.json';m=json.loads(p.read_bytes())
        m['audit_options']['max_spread_points']=100
        self.rewrite_manifest(m)
        with self.assertRaisesRegex(ValueError,'pin mismatch'):self.verify(saved)

    def test_recompute_detects_forged_stored_audit_under_new_pin(self):
        self.save();p=self.path/'audit.json';data=p.read_bytes().replace(b'"backtest_ready":false',b'"backtest_ready":true')
        p.write_bytes(data);m=json.loads((self.path/'manifest.json').read_bytes())
        m['audit_bytes']=len(data);m['audit_sha256']=hashlib.sha256(data).hexdigest()
        new=self.rewrite_manifest(m)
        with self.assertRaisesRegex(ValueError,'Recomputed audit mismatch'):self.verify(new)

    def test_expected_conditions_mismatch_rejected(self):
        saved=self.save()
        with self.assertRaisesRegex(ValueError,'configuration mismatch'):
            self.verify(saved,expected_audit_config_sha256='a'*64)

    def test_partial_save_never_gets_completion_manifest(self):
        def broken():
            yield self.rows[0]
            raise RuntimeError('capture failed')
        with self.assertRaises(RuntimeError):self.save(broken())
        self.assertFalse((self.path/'manifest.json').exists())
        with self.assertRaises(ValueError):verify_tick_archive(self.path,expected_manifest_sha256='a'*64)

    def test_failed_audit_write_leaves_incomplete_archive(self):
        with patch('lsr04_tick_archive._write_exclusive',side_effect=OSError('disk full')):
            with self.assertRaises(OSError):self.save()
        self.assertFalse((self.path/'manifest.json').exists())

    def test_bad_quality_is_preserved_not_promoted(self):
        rows=[fixtures.tick(60),fixtures.tick(0),fixtures.tick(120,bid=0)]
        saved=self.save(rows);r=self.verify(saved)
        self.assertEqual(saved['quality_status'],'BLOCKED_TICK_QUALITY')
        self.assertEqual(r['audit']['counts']['invalid_rows'],1)
        self.assertEqual(r['audit']['counts']['time_reversals'],1)
        self.assertEqual(r['row_count'],3)

    def test_same_millisecond_records_not_deduplicated(self):
        rows=[self.rows[0],dict(self.rows[0],ask=100.2),self.rows[0]]
        r=self.verify(self.save(rows))
        self.assertEqual(r['row_count'],3)
        self.assertEqual(r['audit']['counts']['normalized_duplicate_rows'],1)

    def test_missing_file_and_wrong_schema_block(self):
        saved=self.save();p=self.path/'manifest.json';m=json.loads(p.read_bytes())
        m['schema_version']=2;new=self.rewrite_manifest(m)
        with self.assertRaises(ValueError):self.verify(new)
        p.unlink()
        with self.assertRaises(ValueError):self.verify(saved)

    def test_duplicate_json_keys_rejected_even_with_new_manifest_pin(self):
        self.save();data=(self.path/'manifest.json').read_bytes()
        data=data.replace(b'{',b'{"schema_version":1,',1)
        (self.path/'manifest.json').write_bytes(data)
        with self.assertRaisesRegex(ValueError,'Duplicate JSON key'):
            self.verify(dict(manifest_sha256=hashlib.sha256(data).hexdigest()))

    def test_different_auditor_version_rejected(self):
        self.save();m=json.loads((self.path/'manifest.json').read_bytes());m['auditor_sha256']='a'*64
        with self.assertRaisesRegex(ValueError,'implementation version mismatch'):self.verify(self.rewrite_manifest(m))

    def test_verification_row_budget_is_independent(self):
        saved=self.save()
        self.assertEqual(self.verify(saved,max_ticks=3)['row_count'],3)
        with self.assertRaises(ValueError):self.verify(saved,max_ticks=2)

    def test_nonfinite_input_and_extra_raw_fields_not_silently_lost(self):
        for rows in ([dict(self.rows[0],bid=float('nan'))],[dict(self.rows[0],flags=1)]):
            path=Path(self.temp.name)/str(len(list(Path(self.temp.name).iterdir())))
            with self.assertRaises(ValueError):save_tick_archive(path,rows,audit_options=self.options)
            self.assertFalse((path/'manifest.json').exists())


if __name__=='__main__':unittest.main()
