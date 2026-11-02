import unittest
from orrery_indicator_diagnostics import diagnostics

def bars(n=90):
    return [dict(close_time=(i+1)*900,open=2000+i,high=2002+i,
                 low=1999+i,close=2001+i) for i in range(n)]

class IndicatorDiagnosticsTests(unittest.TestCase):
    def test_well_formed_closed_bars_are_diagnostics_not_forecast(self):
        b=bars()
        r=diagnostics(b,as_of=b[-1]['close_time'],interval=900)
        self.assertEqual(r['status'],'DIAGNOSTICS_ONLY_NO_FORECAST')
        self.assertIsNotNone(r['ema_fast'])
        self.assertIsNotNone(r['adx'])
        self.assertIsNotNone(r['atr'])
        self.assertIsNotNone(r['ichimoku'])
        self.assertLess(r['donchian']['previous_upper'], b[-1]['high'])
        self.assertIsNone(r['forecast_candles'])
        self.assertIsNone(r['up_probability'])
        self.assertFalse(r['execution_allowed'])

    def test_future_or_gap_is_rejected(self):
        b=bars()
        with self.assertRaises(ValueError): diagnostics(b,as_of=b[-2]['close_time'],interval=900)
        b[5]['close_time']+=1
        with self.assertRaises(ValueError): diagnostics(b,as_of=b[-1]['close_time'],interval=900)

    def test_warmup_shortage_remains_unknown(self):
        b=bars(5)
        r=diagnostics(b,as_of=b[-1]['close_time'],interval=900)
        self.assertIsNone(r['adx'])
        self.assertIsNone(r['ichimoku'])
        self.assertIsNone(r['donchian'])
        self.assertIsNone(r['ema_fast'])

    def test_invalid_prices_and_settings_rejected(self):
        b=bars()
        b[0]['high']=b[0]['low']-1
        with self.assertRaises(ValueError): diagnostics(b,as_of=b[-1]['close_time'],interval=900)
        b=bars()
        with self.assertRaises(ValueError): diagnostics(b,as_of=b[-1]['close_time'],interval=900,cloud=(52,26,9))

if __name__=='__main__':unittest.main()
