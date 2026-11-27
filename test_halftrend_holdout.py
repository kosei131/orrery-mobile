import copy
import csv
from io import StringIO
from datetime import datetime, timezone
from hashlib import sha256
import json
import unittest
from orrery_halftrend_holdout import code_pins,decode_plan,evaluate,HALFTREND,SCHEMA
from orrery_history_app import PARAMETERS
from test_tradingview_bundle_audit import fixture,pack,iso


def plan():
    return dict(schema=SCHEMA,parameters=PARAMETERS,halftrend_parameters=HALFTREND,
        frozen_at_utc=iso(0),start_open_utc=iso(86400),end_close_utc=iso(29*86400),
        execution_allowed=False,automatic_adoption_allowed=False,code_sha256=code_pins(),
        source_declared='OANDA:XAUUSD via TradingView MCP',discovery_zip_sha256='0'*64,
        discovery_summaries={})


def encoded(p):
    raw=json.dumps(p).encode();return raw,sha256(raw).hexdigest()


class HoldoutTests(unittest.TestCase):
    def setUp(self):
        self.p=plan();files=fixture()
        for name in ('5m.csv','15m.csv','4h.csv'):
            rows=list(csv.reader(StringIO(files[name].decode())))
            for row in rows[1:]:row[0]=str(int(row[0])+86400);row[1]=iso(int(row[0]))
            stream=StringIO();csv.writer(stream).writerows(rows);files[name]=stream.getvalue().encode()
        manifest=json.loads(files['manifest.json']);manifest['cutoff_utc']=iso(100800)
        for row in manifest['reports']:
            for key in ('first_open_utc','last_open_utc','nominal_last_close_utc'):
                from orrery_tradingview_bundle_audit import _utc
                row[key]=iso(_utc(row[key])+86400)
        files['manifest.json']=json.dumps(manifest).encode();self.raw=pack(files)
    def run_study(self,p=None,raw=None,now=None):
        pr,pin=encoded(self.p if p is None else p);raw=self.raw if raw is None else raw
        return evaluate(raw,pr,plan_sha256=pin,zip_sha256=sha256(raw).hexdigest(),
                        now=now or datetime(1970,2,1,tzinfo=timezone.utc))
    def test_partial_new_period_reuses_engine_without_promotion(self):
        r=self.run_study()
        self.assertTrue(r['partial_period'])
        self.assertFalse(r['independent_holdout_verified'])
        self.assertFalse(r['execution_allowed'])
        self.assertIsNone(r['account_return_pct'])
        self.assertEqual(r['prospective_study']['summaries']['LSR02']['candidates'],0)
        self.assertFalse(r['prospective_study']['reversal04_compared'])
    def test_old_or_overlapping_period_rejected(self):
        self.p.update(frozen_at_utc=iso(86400),start_open_utc=iso(100800),end_close_utc=iso(100800+28*86400))
        with self.assertRaisesRegex(ValueError,'outside frozen'):self.run_study()
    def test_same_discovery_zip_rejected(self):
        self.p['discovery_zip_sha256']=sha256(self.raw).hexdigest()
        with self.assertRaisesRegex(ValueError,'Discovery ZIP'):self.run_study()
    def test_code_or_parameter_drift_rejected(self):
        for change in ('code','parameters'):
            p=copy.deepcopy(self.p)
            if change=='code':p['code_sha256']['lsr05_halftrend.py']='0'*64
            else:p['parameters']['target_r']=2.6
            with self.subTest(change=change),self.assertRaises(ValueError):self.run_study(p)
    def test_future_cutoff_rejected(self):
        with self.assertRaisesRegex(ValueError,'Future data'):self.run_study(now=datetime(1970,1,1,tzinfo=timezone.utc))
    def test_plan_pin_and_pre_freeze_start_rejected(self):
        pr,pin=encoded(self.p)
        with self.assertRaises(ValueError):decode_plan(pr,'0'*64)
        self.p['frozen_at_utc']=self.p['start_open_utc']
        with self.assertRaises(ValueError):self.run_study()
    def test_wrong_source_and_automatic_adoption_rejected(self):
        for key,value in (('source_declared','OTHER'),('automatic_adoption_allowed',True)):
            p=copy.deepcopy(self.p);p[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):self.run_study(p)
    def test_recursive_pins_cover_strategy_and_self(self):
        pins=code_pins()
        for name in ('orrery_halftrend_holdout.py','lsr02_replay.py','lsr05_halftrend.py','lsr03_learning_rollup.py'):
            self.assertIn(name,pins)

if __name__=='__main__':unittest.main()
