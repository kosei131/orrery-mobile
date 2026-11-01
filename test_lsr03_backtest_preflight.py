import copy
import json
import tempfile
import unittest
from pathlib import Path
from lsr03_backtest_preflight import preflight
from lsr04_tick_catalog import save_tick_catalog
import test_lsr04_tick_quality as fixtures


class PreflightTests(unittest.TestCase):
    def setUp(self):
        self.config=json.loads(Path('backtest_3000.json').read_text())

    def test_missing_history_is_not_zero_profit(self):
        r=preflight(self.config)
        self.assertEqual(r['status'],'BACKTEST_NOT_RUN')
        self.assertEqual(r['initial_equity_usd'],3000)
        for field in ('net_profit_usd','ending_equity_usd','return_fraction','max_drawdown_usd','trade_count'):
            self.assertIsNone(r[field])
        self.assertFalse(r['execution_allowed'])

    def test_amount_and_risk_rules_fixed_without_changing_input(self):
        original=copy.deepcopy(self.config);r=preflight(self.config)
        self.assertEqual(self.config,original)
        self.assertEqual(r['initial_planned_risk_usd'],7.5)
        self.assertEqual(r['initial_daily_limit_usd'],30)
        self.assertEqual(r['initial_basket_limit_usd'],30)
        self.assertEqual(r['requested_calendar_days'],183)
        for field,value in (('initial_equity_usd',10000),('risk_fraction',.01)):
            bad=copy.deepcopy(self.config);bad[field]=value
            with self.assertRaises(ValueError):preflight(bad)

    def test_invalid_reference_does_not_run_or_fabricate(self):
        self.config['catalogs']['XAUUSD']=dict(path='not-a-real-dataset',catalog_sha256='a'*64)
        r=preflight(self.config)
        self.assertEqual(r['evidence']['XAUUSD']['status'],'INVALID_OR_UNAVAILABLE_TICK_CATALOG')
        self.assertIsNone(r['net_profit_usd'])

    def test_short_valid_catalog_is_not_six_month_data(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'data'
            options=dict(symbol='XAUUSD',start_utc=fixtures.START,end_utc=fixtures.END,
                source='SYNTHETIC_TEST',broker_spec=fixtures.SPEC,max_spread_points=50,
                windows=[dict(start=fixtures.START,end=fixtures.END,count=1)])
            saved=save_tick_catalog(path,[dict(ticks=[fixtures.tick(0)],audit_options=options)],
                start_utc=fixtures.START,end_utc=fixtures.END)
            self.config['catalogs']['XAUUSD']=dict(path=str(path),catalog_sha256=saved['catalog_sha256'])
            r=preflight(self.config)
            self.assertIn('REQUESTED_SIX_MONTH_HORIZON_NOT_COVERED',r['evidence']['XAUUSD']['reasons'])
            self.assertEqual(r['status'],'BACKTEST_NOT_RUN')
            self.assertIsNone(r['net_profit_usd'])

    def test_warmup_or_horizon_mismatch_not_silently_accepted(self):
        self.config['end_utc']=self.config['start_utc']
        with self.assertRaises(ValueError):preflight(self.config)

    def test_unknown_keys_and_symbols_rejected(self):
        for key,value in (('extra',1),('symbols',['XAUUSD'])):
            bad=copy.deepcopy(self.config);bad[key]=value
            with self.assertRaises(ValueError):preflight(bad)


if __name__=='__main__':unittest.main()
