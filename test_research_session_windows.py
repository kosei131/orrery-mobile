"""Real CMD argument/exit behavior, with a fake session script and no MT5."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


@unittest.skipUnless(os.name=='nt','Windows CMD integration only')
class SessionCmdTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve()
        self.source=self.root/'source with spaces'; self.source.mkdir()
        shutil.copyfile('START_RESEARCH_SESSION.cmd',self.source/'START_RESEARCH_SESSION.cmd')
        self.runner=self.source/'orrery_research_session.py'
        self.runner.write_text("import os,sys\nfrom pathlib import Path\n"
            "assert sys.version_info[:2]==(3,12)\n"
            "assert sys.argv[1:]==['--config',os.environ['ORRERY_TEST_CONFIG']]\n"
            "Path(os.environ['ORRERY_TEST_CALLED']).write_text('synthetic only')\n"
            "raise SystemExit(2)\n")
        self.local=self.root/'local data'; self.local.mkdir()
        self.config=self.local/'ORRERYFX'/'research'/'settings'/'session.local.json'
        self.config.parent.mkdir(parents=True)
        self.marker=self.root/'py_called'
        self.env=dict(os.environ,LOCALAPPDATA=str(self.local),
            ORRERY_TEST_CONFIG=str(self.config),ORRERY_TEST_CALLED=str(self.marker))

    def call(self):
        return subprocess.run(['cmd.exe','/d','/c','START_RESEARCH_SESSION.cmd'],cwd=self.source,
            env=self.env,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=15)

    def test_missing_private_settings_does_not_start_python(self):
        result=self.call(); self.assertEqual(result.returncode,1)
        self.assertFalse(self.marker.exists()); self.assertIn(b'SETUP NEEDED',result.stdout)

    def test_python_312_quoted_paths_and_failure_code_are_preserved(self):
        self.config.write_text('{}')
        result=self.call(); self.assertEqual(result.returncode,2)
        self.assertTrue(self.marker.exists()); self.assertNotIn(b'[DONE]',result.stdout)
        self.assertIn(b'[STOPPED]',result.stdout)


if __name__=='__main__': unittest.main()
