"""Actual loopback HTTP integration with synthetic audited archive, no MT5 IPC."""
import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from lsr04_tick_archive import _encode
from orrery_research_status import make_server, token_file
import test_orrery_research_worker as fixture


class ViewerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = fixture.WorkerTests(); cls.fixture.setUp()
        cls.addClassCleanup(cls.fixture.doCleanups)
        receipt = cls.fixture.job(); cls.folder = cls.fixture.folder(receipt)
        cls.receipt_path = cls.fixture.root/'receipt.json'; cls.receipt_path.write_bytes(_encode(receipt))
        cls.token = 'a'*43
        cls.server = make_server(cls.folder, cls.receipt_path, cls.token, port=0)
        cls.addClassCleanup(cls.server.server_close)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True); cls.thread.start()
        cls.addClassCleanup(cls.thread.join, 5); cls.addClassCleanup(cls.server.shutdown)
        cls.base = f'http://127.0.0.1:{cls.server.server_port}'
        cls.run_id = receipt['run_id']

    def get(self, path, *, auth=True, headers=None):
        values = {'Authorization': 'Bearer '+self.token} if auth else {}
        values.update(headers or {})
        return urlopen(Request(self.base+path, headers=values), timeout=3)

    def test_shell_has_no_private_data_and_strict_headers(self):
        with self.get('/', auth=False) as response:
            html = response.read().decode()
            self.assertIn('保存した検証結果', html)
            self.assertNotIn(self.token, html); self.assertNotIn(self.run_id, html)
            self.assertEqual(response.headers['Cache-Control'], 'no-store')
            self.assertIn("frame-ancestors 'none'", response.headers['Content-Security-Policy'])
            self.assertNotIn('unsafe-inline', response.headers['Content-Security-Policy'])

    def test_every_api_requires_key(self):
        for path in ('/api/health','/api/runs',f'/api/runs/{self.run_id}/summary'):
            for auth in ('Bearer wrong','Bearer '+'é'*43, ''):
                with self.subTest(path=path,auth=auth[:10]), self.assertRaises(HTTPError) as error:
                    self.get(path, auth=False, headers={'Authorization':auth})
                self.assertEqual(error.exception.code, 403)

    def test_snapshot_allows_only_audited_summary(self):
        with self.get('/api/runs') as response: index = json.load(response)
        self.assertEqual(index['runs'][0]['run_id'], self.run_id)
        with self.get(f'/api/runs/{self.run_id}/summary') as response: data = json.load(response)
        self.assertEqual(data['accounts']['CONFIRMATION']['closed_trades'], 0)
        self.assertIsNone(data['accounts']['RETEST']['win_rate_fraction'])
        self.assertTrue(data['snapshot_is_fixed']); self.assertFalse(data['worker_liveness_verified'])
        text = json.dumps(data)
        for private in (str(self.folder), 'FAKE_DEMO', 'account_last4', 'terminal_path', 'demo_account_scope_sha256'):
            self.assertNotIn(private, text)

    def test_health_distinguishes_viewer_from_worker(self):
        with self.get('/api/health') as response: data = json.load(response)
        self.assertTrue(data['viewer_online']); self.assertFalse(data['worker_liveness_verified'])
        self.assertFalse(data['execution_allowed'])

    def test_host_origin_and_cross_site_are_rejected(self):
        for headers in ({'Host':'evil.example'}, {'Origin':self.base},
                        {'Sec-Fetch-Site':'cross-site'}, {'Sec-Fetch-Site':'same-site'}):
            with self.subTest(headers=headers), self.assertRaises(HTTPError) as error:
                self.get('/api/runs',headers=headers)
            self.assertEqual(error.exception.code,403)

    def test_duplicate_host_and_auth_are_rejected(self):
        for name, values in [('Host',[f'127.0.0.1:{self.server.server_port}']*2),
                             ('Authorization',['Bearer '+self.token]*2)]:
            connection = http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=3)
            try:
                connection.putrequest('GET','/api/runs',skip_host=True)
                if name != 'Host': connection.putheader('Host',f'127.0.0.1:{self.server.server_port}')
                for value in values: connection.putheader(name,value)
                connection.endheaders(); response = connection.getresponse()
                self.assertEqual(response.status,403); response.read()
            finally: connection.close()

    def test_queries_and_paths_cannot_retrieve_files(self):
        for path in ('/settings.json','/../settings.json','/api/runs/../../settings.json',
                     '/api/runs/%2e%2e/summary',f'/api/runs?token={self.token}'):
            with self.subTest(path=path), self.assertRaises(HTTPError) as error: self.get(path)
            self.assertIn(error.exception.code,(400,404))

    def test_write_methods_are_disabled(self):
        for method in ('POST','PUT','PATCH','DELETE','OPTIONS','HEAD'):
            with self.subTest(method=method), self.assertRaises(HTTPError) as error:
                urlopen(Request(self.base+'/api/runs', method=method), timeout=3)
            self.assertEqual(error.exception.code,405)

    def test_large_path_is_bounded(self):
        with self.assertRaises(HTTPError) as error: self.get('/api/'+('a'*600))
        self.assertEqual(error.exception.code,413)

    def test_blocked_audit_has_no_metrics(self):
        path = self.fixture.root/'bad_receipt.json'; path.write_bytes(_encode({'state':'FAILED'}))
        server = make_server(self.folder,path,self.token,port=0)
        thread = threading.Thread(target=server.serve_forever,daemon=True); thread.start()
        try:
            request = Request(f'http://127.0.0.1:{server.server_port}/api/runs/{self.run_id}/summary',
                              headers={'Authorization':'Bearer '+self.token})
            with urlopen(request,timeout=3) as response: data=json.load(response)
            self.assertEqual(data['audit_status'],'AUDIT_BLOCKED'); self.assertIsNone(data['accounts'])
        finally: server.shutdown(); thread.join(5); server.server_close()

    def test_key_file_is_strong_persistent_and_never_overwritten(self):
        path = self.fixture.root/'key.local'; key = token_file(path)
        self.assertEqual(len(key),43); self.assertEqual(token_file(path),key)
        path.write_text('short')
        with self.assertRaises(ValueError): token_file(path)
        self.assertEqual(path.read_text(),'short')


if __name__ == '__main__': unittest.main()
