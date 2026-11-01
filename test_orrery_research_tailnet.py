"""Serve-header simulation only; does not prove actual Tailscale/TLS/iPhone."""
from hashlib import sha256
import json
import threading
import unittest
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from lsr04_tick_archive import _encode
from orrery_research_tailnet import make_tailnet_server, settings
import test_orrery_research_worker as fixture


class TailnetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = fixture.WorkerTests(); cls.fixture.setUp(); cls.addClassCleanup(cls.fixture.doCleanups)
        receipt = cls.fixture.job(); cls.run_id = receipt['run_id']
        cls.receipt_path = cls.fixture.root/'receipt.json'; cls.receipt_path.write_bytes(_encode(receipt))
        cls.owner = 'test-owner@example.invalid'; cls.host = 'research.test-tail.ts.net'; cls.token='a'*43
        cls.cfg = dict(enabled=True, public_host=cls.host,
                       allowed_login_sha256=sha256(cls.owner.encode()).hexdigest())
        cls.server = make_tailnet_server(cls.fixture.folder(receipt), cls.receipt_path, cls.token, cls.cfg, port=0)
        cls.addClassCleanup(cls.server.server_close)
        cls.thread = threading.Thread(target=cls.server.serve_forever,daemon=True); cls.thread.start()
        cls.addClassCleanup(cls.thread.join,5); cls.addClassCleanup(cls.server.shutdown)
        cls.base=f'http://127.0.0.1:{cls.server.server_port}'

    def request(self, path='/api/runs', **changes):
        headers={'Host':self.host, 'Tailscale-User-Login':self.owner,'Authorization':'Bearer '+self.token}
        headers.update(changes)
        headers={k:v for k,v in headers.items() if v is not None}
        return urlopen(Request(self.base+path, headers=headers),timeout=3)

    def test_owner_and_viewer_key_reach_same_audited_snapshot(self):
        with self.request(f'/api/runs/{self.run_id}/summary') as response: data=json.load(response)
        self.assertEqual(data['audit_status'],'CONSISTENT_RESEARCH_ARTIFACTS')
        self.assertTrue(data['snapshot_is_fixed']); self.assertFalse(data['execution_allowed'])
        self.assertNotIn(self.owner,json.dumps(data)); self.assertNotIn(self.cfg['allowed_login_sha256'],json.dumps(data))
        with self.request('/',**{'Authorization':None}) as response:
            self.assertIn('保存した検証結果',response.read().decode())

    def test_missing_or_other_identity_blocks_even_shell(self):
        for value in (None,'another@example.invalid','é',''):
            with self.subTest(value=value),self.assertRaises(HTTPError) as error:
                self.request('/',**{'Tailscale-User-Login':value})
            self.assertEqual(error.exception.code,403)

    def test_identity_cannot_replace_api_key(self):
        for auth in (None,'Bearer wrong'):
            with self.subTest(auth=auth),self.assertRaises(HTTPError) as error:
                self.request(**{'Authorization':auth})
            self.assertEqual(error.exception.code,403)

    def test_external_host_and_origin_validated_before_adaptation(self):
        for headers in ({'Host':'evil.example'}, {'Host':f'127.0.0.1:{self.server.server_port}'},
                        {'Origin':'https://evil.example'}, {'Origin':'http://'+self.host},
                        {'Sec-Fetch-Site':'cross-site'}, {'Sec-Fetch-Site':'same-site'}):
            with self.subTest(headers=headers),self.assertRaises(HTTPError) as error: self.request(**headers)
            self.assertEqual(error.exception.code,403)
        with self.request(**{'Origin':'https://'+self.host,'Sec-Fetch-Site':'same-origin'}) as response:
            self.assertEqual(response.status,200)

    def test_bad_config_fails_closed(self):
        for change in (dict(enabled=False),dict(public_host='evil.example'),dict(public_host='https://a.b.ts.net'),
                       dict(allowed_login_sha256=None),dict(public_host='a.b.ts.net/path')):
            with self.subTest(change=change),self.assertRaises(ValueError): settings(dict(self.cfg,**change))

    def test_example_stays_disabled_and_policy_has_only_phone_tcp_https(self):
        from pathlib import Path
        example=json.loads(Path('research_tailnet_settings.example.json').read_bytes())
        with self.assertRaises(ValueError): settings(example)
        policy=json.loads(Path('research_tailnet_policy.example.json').read_bytes())
        self.assertEqual(policy['acls'],[dict(action='accept',src=['orrery-iphone'],dst=['orrery-windows:443'],proto='tcp')])
        self.assertNotIn('*',json.dumps(policy))
        self.assertIn('orrery-windows:8767',policy['tests'][0]['deny'])

    def test_private_binding_and_no_file_or_job_paths(self):
        self.assertEqual(self.server.server_address[0],'127.0.0.1')
        for path in ('/settings.json','/api/runs/../../settings.json','/api/runs?token=secret'):
            with self.subTest(path=path),self.assertRaises(HTTPError) as error: self.request(path)
            self.assertIn(error.exception.code,(400,404))


if __name__ == '__main__': unittest.main()
