import hashlib
import json
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
from lsr04_tick_catalog import save_tick_catalog, verify_tick_catalog
import test_lsr04_tick_quality as fixtures


class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'dataset'
        self.start=fixtures.START;self.end=fixtures.END

    def chunk(self,a,b,seconds):
        return dict(ticks=(fixtures.tick(t) for t in seconds),audit_options=dict(
            symbol='XAUUSD',start_utc=self.start+timedelta(seconds=a),
            end_utc=self.start+timedelta(seconds=b),source='SYNTHETIC_TEST',
            broker_spec=fixtures.SPEC,max_spread_points=50,
            windows=[dict(start=self.start+timedelta(seconds=a),
                          end=self.start+timedelta(seconds=b),count=len(seconds))]))

    def chunks(self):return [self.chunk(0,90,[0,60]),self.chunk(90,180,[90,120])]

    def save(self,chunks=None,**kw):
        return save_tick_catalog(self.path,self.chunks() if chunks is None else chunks,
                                 start_utc=self.start,end_utc=self.end,**kw)

    def verify(self,saved,**kw):
        return verify_tick_catalog(self.path,expected_catalog_sha256=saved['catalog_sha256'],**kw)

    def rewrite(self,catalog):
        data=(json.dumps(catalog,sort_keys=True,separators=(',',':'))+'\n').encode()
        (self.path/'catalog.json').write_bytes(data)
        return dict(catalog_sha256=hashlib.sha256(data).hexdigest())

    def test_generator_roundtrip_with_root_pin(self):
        saved=self.save(iter(self.chunks()))
        r=self.verify(saved,expected_shared_options_sha256=saved['shared_options_sha256'])
        self.assertEqual(r['chunk_count'],2)
        self.assertEqual(r['total_rows'],4)
        self.assertEqual(r['blocked_quality_chunks'],0)
        self.assertFalse(r['completeness_verified'])
        self.assertFalse(r['backtest_ready'])
        self.assertFalse(r['execution_allowed'])

    def test_boundary_quotes_assigned_to_later_chunk(self):
        r=self.verify(self.save())
        self.assertEqual(r['total_rows'],4)
        rows=(self.path/'chunk-000001'/'ticks.jsonl').read_text().splitlines()
        self.assertEqual(json.loads(rows[0])['time_msc'],fixtures.T+90000)

    def test_missing_interval_not_silently_filled(self):
        with self.assertRaisesRegex(ValueError,'gap'):
            self.save([self.chunk(0,60,[0]),self.chunk(90,180,[90])])
        self.assertFalse((self.path/'catalog.json').exists())

    def test_overlapping_chunks_rejected(self):
        with self.assertRaisesRegex(ValueError,'overlap'):
            self.save([self.chunk(0,120,[0]),self.chunk(90,180,[90])])

    def test_incomplete_tail_and_empty_dataset_rejected(self):
        with self.assertRaisesRegex(ValueError,'incomplete'):self.save([self.chunk(0,90,[0])])
        other=Path(self.temp.name)/'empty'
        with self.assertRaisesRegex(ValueError,'Empty'):
            save_tick_catalog(other,[],start_utc=self.start,end_utc=self.end)

    def test_policy_source_symbol_and_spec_mixing_rejected(self):
        for index,key in enumerate(('source','max_spread_points','symbol','broker_spec')):
            chunks=self.chunks()
            if key=='source':chunks[1]['audit_options'][key]='OTHER_SOURCE'
            elif key=='max_spread_points':chunks[1]['audit_options'][key]=100
            elif key=='symbol':
                chunks[1]['audit_options'][key]='USDJPY'
                chunks[1]['audit_options']['broker_spec']=dict(fixtures.SPEC,symbol='USDJPY')
            else:chunks[1]['audit_options'][key]=dict(fixtures.SPEC,point=.001)
            path=Path(self.temp.name)/f'mixed-{index}'
            with self.assertRaisesRegex(ValueError,'Mixed'):
                save_tick_catalog(path,chunks,start_utc=self.start,end_utc=self.end)

    def test_child_modified_or_missing_blocks_whole_verification(self):
        saved=self.save();p=self.path/'chunk-000001'/'ticks.jsonl';data=p.read_bytes()
        p.write_bytes(data.replace(b'100.1',b'100.2',1))
        with self.assertRaises(ValueError):self.verify(saved)
        p.unlink()
        with self.assertRaises(ValueError):self.verify(saved)

    def test_catalog_tampering_detected_by_independent_pin(self):
        saved=self.save();m=json.loads((self.path/'catalog.json').read_bytes());m['total_rows']=99
        self.rewrite(m)
        with self.assertRaisesRegex(ValueError,'pin mismatch'):self.verify(saved)

    def test_repinned_false_horizon_still_disagrees_with_child(self):
        self.save();m=json.loads((self.path/'catalog.json').read_bytes())
        m['chunks'][0]['end_msc']-=1
        with self.assertRaises(ValueError):self.verify(self.rewrite(m))

    def test_path_traversal_reference_rejected(self):
        self.save();m=json.loads((self.path/'catalog.json').read_bytes())
        m['chunks'][0]['directory']='../outside'
        with self.assertRaisesRegex(ValueError,'unsafe'):self.verify(self.rewrite(m))

    def test_existing_catalog_not_overwritten(self):
        saved=self.save()
        with self.assertRaises(FileExistsError):self.save()
        self.assertEqual(self.verify(saved)['total_rows'],4)

    def test_chunk_and_total_row_budgets(self):
        with self.assertRaises(ValueError):self.save(max_chunks=1)
        other=Path(self.temp.name)/'budget'
        with self.assertRaises(ValueError):
            save_tick_catalog(other,self.chunks(),start_utc=self.start,end_utc=self.end,max_total_ticks=3)
        self.assertFalse((other/'catalog.json').exists())

    def test_verifier_budgets_do_not_return_prefix_success(self):
        saved=self.save()
        with self.assertRaises(ValueError):self.verify(saved,max_chunks=1)
        with self.assertRaises(ValueError):self.verify(saved,max_total_ticks=3)
        self.assertEqual(self.verify(saved,max_total_ticks=4)['total_rows'],4)

    def test_empty_chunk_preserved_as_quality_block(self):
        chunks=[self.chunk(0,60,[0]),self.chunk(60,120,[]),self.chunk(120,180,[120])]
        r=self.verify(self.save(chunks))
        self.assertEqual(r['chunk_count'],3)
        self.assertEqual(r['total_rows'],2)
        self.assertEqual(r['blocked_quality_chunks'],1)
        self.assertFalse(r['backtest_ready'])

    def test_capture_failure_has_no_catalog_completion_marker(self):
        def chunks():
            yield self.chunk(0,90,[0])
            raise RuntimeError('disconnected')
        with self.assertRaises(RuntimeError):self.save(chunks())
        self.assertFalse((self.path/'catalog.json').exists())
        with self.assertRaises((ValueError,FileNotFoundError)):
            verify_tick_catalog(self.path,expected_catalog_sha256='a'*64)

    def test_unexpected_member_and_wrong_expected_policy_block(self):
        saved=self.save()
        with self.assertRaisesRegex(ValueError,'policy mismatch'):
            self.verify(saved,expected_shared_options_sha256='a'*64)
        (self.path/'extra').write_text('unexpected')
        with self.assertRaisesRegex(ValueError,'unexpected'):self.verify(saved)


if __name__=='__main__':unittest.main()
