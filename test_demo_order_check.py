import unittest
from types import SimpleNamespace
import test_demo_preflight as fixture
from lsr04_demo_order_check import inspect_order


class Broker(fixture.Broker):
    TRADE_ACTION_DEAL=1;ORDER_FILLING_FOK=0;ORDER_TIME_GTC=0
    def __init__(self):super().__init__();self.calls=[];self.mode_exec=2;self.flags=1
    def symbol_info(self,s):
        a=super().symbol_info(s);a.trade_exemode=self.mode_exec;a.filling_mode=self.flags;return a
    def order_send(self,*args):raise AssertionError('Must never send orders')
    def order_check(self,request):
        self.calls.append(request.copy())
        echo=dict(price=0.,**request) if 'price' not in request else request.copy()
        return SimpleNamespace(retcode=0,request=SimpleNamespace(**echo),balance=10000.,
            equity=10000.,profit=0.,margin=100.,margin_free=4900.,margin_level=10000.)


class CheckTests(unittest.TestCase):
    def setUp(self):
        f=fixture.PreflightTests();f.setUp();self.args=f.args.copy();self.args.pop('now_msc')
    def run_check(self,b,**args):return inspect_order(b,clock_msc=lambda:10001,**dict(self.args,**args))
    def test_market_check_preserves_structural_levels_and_never_authorizes(self):
        b=Broker();r=self.run_check(b)
        self.assertEqual(len(b.calls),1);self.assertNotIn('price',b.calls[0])
        self.assertEqual((b.calls[0]['sl'],b.calls[0]['tp'],b.calls[0]['volume']),(98.9,103.,.25))
        self.assertFalse(r['execution_allowed']);self.assertFalse(r['broker_session_verified'])
        self.assertFalse(r['duplicate_order_protection_verified']);self.assertEqual(r['check_retcode'],0)
    def test_request_and_instant_modes_use_entry_even_without_fill_flag(self):
        for mode in (0,1):
            b=Broker();b.mode_exec=mode;b.flags=0;self.run_check(b)
            self.assertEqual(b.calls[0]['price'],100.)
    def test_market_and_exchange_refuse_ioc_only_before_check(self):
        for mode in (2,3):
            b=Broker();b.mode_exec=mode;b.flags=2
            with self.assertRaisesRegex(ValueError,'FOK'):self.run_check(b)
            self.assertEqual(b.calls,[])
    def test_real_account_never_reaches_check(self):
        b=Broker();b.mode=2
        with self.assertRaises(ValueError):self.run_check(b)
        self.assertEqual(b.calls,[])
    def test_unavailable_rejected_and_send_success_code_are_not_check_success(self):
        for code in (None,10019,10009,False):
            class Bad(Broker):
                def order_check(self,req):
                    r=super().order_check(req);r.retcode=code;return r if code is not None else None
            with self.assertRaises(ValueError):self.run_check(Bad())
    def test_echo_mutation_and_invalid_financial_data_refused(self):
        for field,value in (('margin_free',-1.),('equity',float('nan')),('margin',None),('request',None)):
            class Bad(Broker):
                def order_check(self,req):
                    r=super().order_check(req);setattr(r,field,value);return r
            with self.assertRaises(ValueError):self.run_check(Bad())
        class Changed(Broker):
            def order_check(self,req):
                r=super().order_check(req);r.request.sl=98.;return r
        with self.assertRaisesRegex(ValueError,'request differs'):self.run_check(Changed())
    def test_quote_change_after_check_refused(self):
        class Changed(Broker):
            def order_check(self,req):
                r=super().order_check(req);self.changed=True;return r
        with self.assertRaises(ValueError):self.run_check(Changed())
    def test_fill_spec_change_after_check_refused(self):
        class Changed(Broker):
            def order_check(self,req):
                r=super().order_check(req);self.flags=3;return r
        with self.assertRaisesRegex(ValueError,'context changed'):self.run_check(Changed())
    def test_check_elapsed_beyond_quote_expiry_or_clock_reversal_refused(self):
        for times in ((10001,15001),(10001,10000),(10001,10002,15001),(10001,10002,10001)):
            it=iter(times)
            with self.assertRaises(ValueError):inspect_order(Broker(),clock_msc=lambda:next(it),**self.args)
