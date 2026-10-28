import ast,json,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace as D
from datetime import timedelta
from lsr03_mt5_pilot import run_pilot,_account,_scope,_valuation_spec
from lsr03_mt5_account_pilot import run_account_pilot,current_demo_valuation
import test_lsr03_mt5_pilot as fixture

class MT5(fixture.MT5):
    ORDER_TYPE_BUY=0
    ORDER_TYPE_SELL=1
    def __init__(self):super().__init__();self.profit_calls=0;self.step=.01;self.profit_currency='USD';self.bad_profit=False
    def symbol_info(self,symbol):
        return D(name=symbol,point=self.spec_point,trade_contract_size=100,digits=2,
                 volume_min=.01,volume_max=100.,volume_step=self.step,
                 currency_profit=self.profit_currency,trade_calc_mode=1)
    def order_calc_profit(self,action,symbol,lots,entry,close):
        self.profit_calls+=1
        return None if self.bad_profit else (close-entry)*lots*100*(1 if action==0 else -1)


def config():
    return dict(fixed_distance=6,target_r=1.5,entry_delay_msc=1,entry_window_msc=60000,
                max_holding_msc=7200000,round_trip_cost_per_lot_usd=0,slippage=0,
                cost_source='SYNTHETIC_ONLY_EXPLICIT_ZERO',no_carry_interval_confirmed=True,
                no_carry_evidence_source='SYNTHETIC_TEST_NO_ROLLOVER_ASSERTION',max_profit_calls=100)

class AccountPilotTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.mt5=MT5()
        helper=fixture.PilotTests();helper.setUp();self.addCleanup(helper.temp.cleanup)
        self.capture=self.root/'capture'
        self.run=run_pilot(self.mt5,helper.config,self.capture,now_utc=fixture.END+timedelta(hours=1))
        self.out=self.root/'account'

    def call(self,settings=None):
        return run_account_pilot(self.mt5,self.capture,self.run['run_sha256'],config() if settings is None else settings,self.out)

    def test_full_fake_demo_capture_to_pinned_account_report(self):
        r=self.call()
        self.assertEqual(r['report_status'],'CONFIRMATION_RETEST_INDEPENDENT_ACCOUNT_RESEARCH')
        report=json.loads((self.out/'account_report.json').read_bytes())
        for account in report['accounts'].values():
            self.assertEqual(account['closed_statistics']['trades'],0)
            self.assertFalse(account['execution_allowed'])
        self.assertFalse(report['historical_broker_conditions_verified'])
        self.assertIn('CURRENT_MT5_ENVIRONMENT',report['valuation_basis'])
        self.assertTrue((self.out/'account_run.json').is_file())
        self.assertEqual(report['config']['cohort_start'],int((fixture.END-timedelta(hours=4)).timestamp()))

    def test_changed_or_live_account_rejected_no_profit_calculation(self):
        for name,value in [('login',2),('mode',2)]:
            with self.subTest(name=name):
                old=getattr(self.mt5,name);setattr(self.mt5,name,value)
                with self.assertRaises(ValueError):self.call()
                setattr(self.mt5,name,old)
        self.assertEqual(self.mt5.profit_calls,0)
        self.assertFalse((self.out/'account_run.json').exists())

    def test_changed_volume_or_profit_currency_rejected(self):
        self.mt5.step=.02
        with self.assertRaises(ValueError):self.call()
        self.mt5.step=.01;self.mt5.profit_currency='JPY'
        with self.assertRaises(ValueError):self.call()
        self.assertEqual(self.mt5.profit_calls,0)

    def test_tampered_bundle_or_wrong_pin_rejected(self):
        path=self.capture/'bars.json';path.write_bytes(path.read_bytes()+b' ')
        with self.assertRaises(ValueError):self.call()
        self.assertFalse(self.out.exists())

    def test_missing_cost_or_carry_assertion_blocks(self):
        for key,value in [('round_trip_cost_per_lot_usd',None),('slippage',None),('no_carry_interval_confirmed',False)]:
            with self.subTest(key=key),self.assertRaises(ValueError):
                self.call(dict(config(),**{key:value}))
        self.assertFalse(self.out.exists())

    def test_missing_captured_identity_not_silently_accepted(self):
        from hashlib import sha256
        p=self.capture/'run.json';m=json.loads(p.read_bytes());del m['demo_account_scope_sha256']
        data=json.dumps(m).encode();p.write_bytes(data)
        with self.assertRaises((ValueError,KeyError)):
            run_account_pilot(self.mt5,self.capture,sha256(data).hexdigest(),config(),self.out)

    def test_existing_output_not_overwritten_and_no_raw_identity_saved(self):
        self.call();marker=(self.out/'account_run.json').read_bytes()
        with self.assertRaises(FileExistsError):self.call()
        self.assertEqual((self.out/'account_run.json').read_bytes(),marker)
        for p in self.out.glob('*.json'):
            s=p.read_text();self.assertNotIn('FAKE_DEMO',s);self.assertNotIn('"login"',s)

    def test_direct_profit_estimates_recheck_identity_and_call_budget(self):
        q,check,state=current_demo_valuation(self.mt5,captured_scope=_scope(_account(self.mt5)),
            captured_spec=_valuation_spec(self.mt5,'XAUUSD'),max_calls=1)
        self.assertAlmostEqual(q('XAUUSD','BUY',.1,100,101,1),10)
        with self.assertRaises(ValueError):q('XAUUSD','BUY',.1,100,101,2)
        self.assertEqual(state['profit_calculations'],1)
        self.mt5.login=2
        with self.assertRaises(ValueError):check()

    def test_failed_calc_or_historical_conversion_not_guessed(self):
        q,_,_=current_demo_valuation(self.mt5,captured_scope=_scope(_account(self.mt5)),
            captured_spec=_valuation_spec(self.mt5,'XAUUSD'),max_calls=10)
        with self.assertRaises(ValueError):q('USDJPY','BUY',.1,100,101,1)
        self.mt5.bad_profit=True
        with self.assertRaises(ValueError):q('XAUUSD','BUY',.1,100,101,1)

    def test_new_runner_only_calculates_or_reads_mt5(self):
        tree=ast.parse(Path('lsr03_mt5_account_pilot.py').read_text())
        calls={n.func.attr for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)
               and isinstance(n.func.value,ast.Name) and n.func.value.id=='mt5'}
        self.assertLessEqual(calls,{'initialize','shutdown','order_calc_profit'})
        self.assertIn('order_calc_profit',calls)

if __name__=='__main__':unittest.main()
