# SPDX-License-Identifier: GPL-3.0-only
import unittest
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
from lsr05_halftrend import calculate, compare_amplitudes, SOURCE_SHA256


def bars(prices,interval=300):
    return [dict(close_time=(i+1)*interval,open=p,high=p+.5,low=p-.5,close=p)
            for i,p in enumerate(prices)]


class HalfTrendTests(unittest.TestCase):
    def run_calc(self,data,**changes):
        settings=dict(as_of=data[-1]['close_time'] if data else 0,interval=300,enabled=True)
        settings.update(changes)
        return calculate(data,**settings)

    def test_default_off_and_no_order_permission(self):
        out=calculate(None,as_of=0,interval=300)
        self.assertEqual(out['status'],'DISABLED'); self.assertEqual(out['rows'],[])
        self.assertFalse(out['execution_allowed'])

    def test_atr_warmup_and_flat_channel_hand_calculation(self):
        out=self.run_calc(bars([100.]*100))
        self.assertIsNone(out['rows'][98]['atr'])
        last=out['rows'][99]
        self.assertEqual(last['atr'],1.)
        self.assertEqual(last['line'],99.5)
        self.assertEqual((last['atr_high'],last['atr_low']),(100.5,98.5))
        self.assertEqual(out['signals'],[])

    def test_recursive_atr_accounts_for_price_gap(self):
        out=self.run_calc(bars([100.]*100+[102.]))
        self.assertAlmostEqual(out['rows'][-1]['atr'],(99+2.5)/100)

    def test_sell_and_buy_transitions_with_manual_expected_lines(self):
        data=bars([100.]*100+[102.,104.,106.,100.,98.,96.,104.])
        out=self.run_calc(data)
        self.assertEqual([(r['at'],r['signal']) for r in out['signals']],
                         [(data[104]['close_time'],'SELL'),(data[106]['close_time'],'BUY')])
        self.assertEqual(out['rows'][104]['line'],103.5)
        self.assertEqual(out['rows'][106]['line'],98.5)
        for row in out['signals']:
            self.assertEqual(row['signal_known_at'],row['at'])

    def test_deviation_changes_channels_not_state_or_signal(self):
        data=bars([100.]*100+[102.,104.,106.,100.,98.,96.,104.])
        a=self.run_calc(data,channel_deviation=1); b=self.run_calc(data,channel_deviation=4)
        self.assertEqual([(r['state'],r['signal'],r['line']) for r in a['rows']],
                         [(r['state'],r['signal'],r['line']) for r in b['rows']])
        self.assertNotEqual(a['rows'][-1]['atr_high'],b['rows'][-1]['atr_high'])

    def test_append_future_bars_does_not_rewrite_previous_output(self):
        data=bars([100.]*100+[102.,104.,106.,100.,98.,96.,104.]*5)
        prefix=self.run_calc(data[:110]); full=self.run_calc(data)
        self.assertEqual(prefix['rows'],full['rows'][:110])

    def test_no_published_signal_during_atr_warmup(self):
        data=bars([100.,102.,104.,106.,100.,98.,96.,104.]*4)
        out=self.run_calc(data)
        self.assertTrue(any(r['internal_transition'] for r in out['rows']))
        self.assertEqual(out['signals'],[])
        self.assertEqual(out['status'],'INSUFFICIENT_HISTORY')

    def test_future_and_explicit_unclosed_bar_rejected(self):
        data=bars([100.]*101)
        with self.assertRaises(ValueError): self.run_calc(data,as_of=data[-2]['close_time'])
        data[-1]['is_closed']=False
        with self.assertRaises(ValueError): self.run_calc(data)

    def test_gap_duplicate_and_bad_ohlc_rejected(self):
        data=bars([100.]*101)
        for changes in (dict(close_time=data[-2]['close_time']),dict(close_time=data[-1]['close_time']+300),
                        dict(low=101.),dict(close=float('nan')),dict(open=True)):
            bad=deepcopy(data); bad[-1].update(changes)
            with self.assertRaises(ValueError): self.run_calc(bad)

    def test_amplitude_grid_reports_no_best_setting(self):
        data=bars([100.]*105)
        out=compare_amplitudes(data,as_of=data[-1]['close_time'],interval=300)
        self.assertEqual(set(out['results']),{'2','4','6','8'})
        self.assertIsNone(out['best_amplitude'])
        self.assertFalse(out['execution_allowed'])

    def test_invalid_settings_are_rejected(self):
        for changes in (dict(amplitude=3),dict(amplitude=True),dict(channel_deviation=-1),
                        dict(channel_deviation=float('inf')),dict(interval=60),dict(enabled='yes')):
            with self.assertRaises(ValueError): self.run_calc(bars([100.]*100),**changes)

    def test_m15_scope_and_input_not_mutated(self):
        data=bars([100.]*100,interval=900); before=deepcopy(data)
        out=self.run_calc(data,interval=900)
        self.assertEqual(data,before)
        self.assertFalse(out['tradingview_parity_verified'])
        self.assertFalse(out['nonrepainting_verified'])

    def test_pinned_upstream_source_and_license_preserved(self):
        root=Path(__file__).resolve().parent/'research_refs'/'halftrend'
        # Git's Windows checkout may use CRLF; upstream pin is raw LF bytes.
        source=(root/'halftrend.pine').read_text(encoding='utf-8').encode('utf-8')
        self.assertEqual(sha256(source).hexdigest(),SOURCE_SHA256)
        self.assertIn('Alex Orekhov',source.decode())
        self.assertIn('GNU GENERAL PUBLIC LICENSE',(root/'COPYING').read_text())


if __name__=='__main__': unittest.main()
