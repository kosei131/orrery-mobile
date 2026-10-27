"""Offline integration tests for ORRERY MT5 local dashboard. Stdlib only."""
import json
import re
import subprocess
import sys
import time
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

BASE = "http://127.0.0.1:8765"

class DashboardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.process = subprocess.Popen([sys.executable, "-u", "mt5_local_dashboard.py", "--test-data"],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        try:
            line1 = cls.process.stdout.readline()
            line2 = cls.process.stdout.readline()
            cls.assert_token = re.search(r"http://127\.0\.0\.1:8765/#([\w-]+)", line2)
            if cls.assert_token is None:
                raise RuntimeError("Dashboard did not provide local token: " + line1 + " " + line2)
            cls.token = cls.assert_token.group(1)
            for _ in range(30):
                try:
                    with urlopen(BASE + "/", timeout=1) as response:
                        if response.status == 200:
                            break
                except Exception:
                    time.sleep(.1)
            else:
                raise RuntimeError("Local server failed to respond")
        except BaseException:
            cls.process.terminate()
            cls.process.wait(timeout=5)
            raise

    @classmethod
    def tearDownClass(cls):
        cls.process.terminate()
        try:
            cls.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            cls.process.kill()

    def test_page_is_served(self):
        with urlopen(BASE + "/") as response:
            html = response.read().decode("utf8")
        self.assertIn("ORRERY FX", html)
        self.assertIn("10秒", html)

    def test_unauthorized_request_is_rejected(self):
        with self.assertRaises(HTTPError) as err:
            urlopen(BASE + "/api/snapshot", timeout=3)
        self.assertEqual(err.exception.code, 403)

    def test_simulated_snapshot_only(self):
        req = Request(BASE + "/api/snapshot", headers={"X-Orrery-Token": self.token})
        with urlopen(req, timeout=3) as response:
            data = json.load(response)
            self.assertEqual(response.headers.get("Cache-Control"), "no-store")
        self.assertEqual(data["status"], "SIMULATED_TEST_DATA")
        self.assertEqual(data["account_last4"], "0000")
        self.assertEqual(data["balance"], 10000)
        self.assertEqual(data["positions"][0]["symbol"], "XAUUSD-TEST")

    def test_dns_rebinding_host_rejected(self):
        req = Request(BASE + "/api/snapshot", headers={
            "X-Orrery-Token": self.token, "Host": "attacker.example:8765"})
        with self.assertRaises(HTTPError) as err:
            urlopen(req, timeout=3)
        self.assertEqual(err.exception.code, 403)

    def test_cross_origin_rejected(self):
        req = Request(BASE + "/api/snapshot", headers={
            "X-Orrery-Token": self.token, "Origin": "https://example.org"})
        with self.assertRaises(HTTPError) as err:
            urlopen(req, timeout=3)
        self.assertEqual(err.exception.code, 403)

if __name__ == "__main__":
    unittest.main()
