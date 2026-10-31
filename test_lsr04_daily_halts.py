from contextlib import closing
import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace as D
from lsr02_halts import DailyRiskHaltStore, HaltStore
from lsr04_mt5_account_sync import demo_day_check, daily_halt_keys
import test_lsr04_daily_reconciliation as fixtures
import test_lsr04_mt5_account_sync as history_fixtures

START = datetime(2026, 10, 27, tzinfo=timezone.utc)
SCOPE = 'a'*64
POLICY = 'b'*64


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)/'daily.sqlite3'
        self.store = DailyRiskHaltStore(self.path, create=True)
        self.store.initialize_session(scope=SCOPE, day_start_utc=START, policy=POLICY, verified_start=True)

    def observe(self, store=None, **kw):
        args = dict(scope=SCOPE, day_start_utc=START, now_utc=START+timedelta(hours=12), policy=POLICY, reasons=[])
        args.update(kw)
        return (store or self.store).observe(**args)

    def test_recovery_and_restart_do_not_clear(self):
        self.observe(reasons=['DAILY_DRAWDOWN_STOP'])
        r = self.observe(DailyRiskHaltStore(self.path), now_utc=START+timedelta(hours=13))
        self.assertEqual(r['reasons'], ['DAILY_DRAWDOWN_STOP'])
        self.assertFalse(r['execution_allowed'])

    def test_reason_union_is_durable(self):
        self.observe(reasons=['DAILY_DRAWDOWN_STOP'])
        self.observe(reasons=['LOSS_STREAK_STOP'])
        self.assertEqual(len(self.observe()['reasons']), 2)

    def test_parallel_observations_do_not_overwrite_each_other(self):
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda r:self.observe(reasons=[r]), ['DAILY_DRAWDOWN_STOP','LOSS_STREAK_STOP']))
        self.assertEqual(len(results), 2)
        self.assertEqual(len(self.observe()['reasons']), 2)

    def test_missing_or_deleted_store_not_recreated(self):
        self.path.unlink()
        with self.assertRaises(sqlite3.Error):self.observe()
        self.assertFalse(self.path.exists())
        with self.assertRaises(sqlite3.Error):DailyRiskHaltStore(self.path)

    def test_new_session_is_not_created_by_observation(self):
        with self.assertRaises(ValueError):
            self.observe(day_start_utc=START+timedelta(days=1), now_utc=START+timedelta(days=1,hours=1))
        self.assertEqual(self.observe()['reasons'], [])

    def test_explicit_next_session_retains_old_record(self):
        self.observe(reasons=['DAILY_DRAWDOWN_STOP'])
        tomorrow=START+timedelta(days=1)
        self.store.initialize_session(scope=SCOPE, day_start_utc=tomorrow, policy=POLICY, verified_start=True)
        r=self.observe(day_start_utc=tomorrow, now_utc=tomorrow)
        self.assertEqual(r['reasons'], [])
        with closing(sqlite3.connect(self.path)) as db, db:
            records=db.execute('SELECT reasons FROM daily_risk_halts ORDER BY session').fetchall()
        self.assertEqual(len(records),2)
        self.assertIn('DAILY_DRAWDOWN_STOP', records[0][0])
        with self.assertRaises(ValueError):self.observe()  # cannot replay an obsolete session

    def test_reinitialize_or_overlap_cannot_reset(self):
        for offset in (0, 3600, -86400):
            with self.assertRaises(ValueError):
                self.store.initialize_session(scope=SCOPE, day_start_utc=START+timedelta(seconds=offset), policy=POLICY, verified_start=True)

    def test_other_account_cannot_read_this_session(self):
        with self.assertRaises(ValueError):self.observe(scope='c'*64)

    def test_rule_change_and_time_reversal_block(self):
        self.observe()
        with self.assertRaises(ValueError):self.observe(policy='c'*64)
        with self.assertRaises(ValueError):self.observe(now_utc=START+timedelta(hours=11))

    def test_corrupt_record_and_schema_block(self):
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("UPDATE daily_risk_halts SET reasons='[\"UNKNOWN\"]'")
        with self.assertRaises(ValueError):self.observe()
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute('UPDATE daily_metadata SET version=99')
        with self.assertRaises(ValueError):DailyRiskHaltStore(self.path)

    def test_legacy_store_and_existing_file_not_overwritten(self):
        with self.assertRaises(FileExistsError):DailyRiskHaltStore(self.path, create=True)
        other=Path(self.temp.name)/'legacy.sqlite3'
        HaltStore(other, create=True)
        with self.assertRaises(sqlite3.Error):DailyRiskHaltStore(other)
        self.assertIsNone(HaltStore(other).get('XAUUSD'))

    def test_unverified_initialization_and_unknown_reason_rejected(self):
        with self.assertRaises(ValueError):
            self.store.initialize_session(scope='c'*64, day_start_utc=START, policy=POLICY)
        with self.assertRaises(ValueError):self.observe(reasons=['BASKET_RISK_CAP'])


class Integration(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'daily.sqlite3'
        self.store=DailyRiskHaltStore(self.path,create=True)
        self.b,self.kw=fixtures.Integration().setup_run(balance=9900,equity=9900)
        self.b.history_deals_get(None,None)[1].profit=-98
        scope,policy=daily_halt_keys(self.b.account_info(),10000)
        self.store.initialize_session(scope=scope,day_start_utc=START,policy=policy,verified_start=True)
        self.kw['risk_halt_store']=self.store

    def test_daily_stop_survives_recovery_and_restart(self):
        r=demo_day_check(self.b,**self.kw)
        self.assertEqual(r['status'],'BLOCKED_LATCHED_ACCOUNT_STOP')
        previous=self.b.account_info
        def recovered():
            a=previous();a.equity=10000;return a
        self.b.account_info=recovered
        self.kw['risk_halt_store']=DailyRiskHaltStore(self.path)
        self.kw['now_utc']+=timedelta(seconds=1)
        r=demo_day_check(self.b,**self.kw)
        self.assertEqual(r['daily_halt']['reasons'],['DAILY_DRAWDOWN_STOP'])
        self.assertTrue(r['halt_persistence_verified'])
        self.assertFalse(r['execution_allowed'])

    def test_write_failure_blocks(self):
        class Broken:
            def observe(self,**kw):raise sqlite3.OperationalError('write failed')
        self.kw['risk_halt_store']=Broken()
        self.assertEqual(demo_day_check(self.b,**self.kw)['status'],'BLOCKED_RISK_HALT_STORE')

    def test_missing_baseline_does_not_claim_persistence(self):
        del self.kw['day_start_snapshot']
        r=demo_day_check(self.b,**self.kw)
        self.assertEqual(r['status'],'BLOCKED_HALT_RECONCILIATION_REQUIRED')
        self.assertFalse(r['halt_persistence_verified'])

    def test_unknown_streak_does_not_hide_daily_breach(self):
        self.b.positions_get=lambda:[D(identifier=1)]
        r=demo_day_check(self.b,**self.kw)
        self.assertIsNone(r['grouping']['consecutive_losses'])
        self.assertEqual(r['daily_halt']['reasons'],['DAILY_DRAWDOWN_STOP'])

    def test_changed_baseline_policy_blocks(self):
        self.kw['day_start_equity']=11000
        self.kw['day_start_snapshot']['equity']=11000
        self.assertEqual(demo_day_check(self.b,**self.kw)['status'],'BLOCKED_RISK_HALT_STORE')

    def test_account_digest_is_account_specific_and_contains_no_raw_id(self):
        a=self.b.account_info();scope,_=daily_halt_keys(a,10000)
        a.login=2;other,_=daily_halt_keys(a,10000)
        self.assertNotEqual(scope,other)
        self.assertEqual(len(scope),64)

    def test_three_completed_losses_are_persisted_without_daily_breach(self):
        helper=history_fixtures.Bridge()
        rows=[]
        for pid in range(1,4):
            rows += [helper.row(pid,pid*2,0),helper.row(pid,pid*2+1,1,profit=-10)]
        self.b.history_deals_get=lambda a,b:rows
        old=self.b.account_info
        def account():
            a=old();a.balance=9964;a.equity=9964;return a
        self.b.account_info=account
        r=demo_day_check(self.b,**self.kw)
        self.assertEqual(r['daily_halt']['reasons'],['LOSS_STREAK_STOP'])
        self.assertEqual(r['status'],'BLOCKED_LATCHED_ACCOUNT_STOP')

    def test_daily_breach_is_stored_before_failed_stop_valuation(self):
        self.kw['stop_cost_allowances']={99:0}
        r=demo_day_check(self.b,**self.kw)
        self.assertEqual(r['status'],'BLOCKED_LATCHED_ACCOUNT_STOP')
        self.assertEqual(r['daily_halt']['reasons'],['DAILY_DRAWDOWN_STOP'])


if __name__=='__main__':unittest.main()
