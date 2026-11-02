import io,zipfile,tempfile,unittest
from pathlib import Path
from orrery_h4_pc_bootstrap import prepare,PINS,REVISION

class BootstrapTests(unittest.TestCase):
    def archive(self,change=None,omit=None,duplicate=None):
        out=io.BytesIO();prefix='orrery-mobile-'+REVISION+'/'
        with zipfile.ZipFile(out,'w') as z:
            for n in PINS:
                if n==omit:continue
                raw=(Path('test_fixtures/pinned_lsr02_replay.py.txt') if n=='lsr02_replay.py' else Path(n)).read_bytes().replace(b"\r\n",b"\n");z.writestr(prefix+n,b'changed' if n==change else raw)
                if n==duplicate:z.writestr(prefix+n,raw)
            z.writestr('../../escape.txt','never extracted')
        return out.getvalue()
    def test_only_pinned_sources_prepared_without_importing_mt5(self):
        with tempfile.TemporaryDirectory() as d:
            root=prepare(d,archive=self.archive())
            self.assertEqual(len(list(root.glob('*.py'))),26)
            self.assertEqual((root/'SOURCE_REVISION.txt').read_text().strip(),REVISION)
            self.assertFalse((Path(d)/'escape.txt').exists())
    def test_bad_or_missing_source_does_not_create_output(self):
        for kwargs in (dict(change=next(iter(PINS))),dict(omit=next(iter(PINS)))):
            with tempfile.TemporaryDirectory() as d:
                with self.assertRaises(ValueError):prepare(d,archive=self.archive(**kwargs))
                self.assertEqual(list(Path(d).iterdir()),[])
    def test_existing_parent_files_untouched(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'old.txt';p.write_text('keep');prepare(d,archive=self.archive())
            self.assertEqual(p.read_text(),'keep')
