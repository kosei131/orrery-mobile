import csv
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from lsr03_account_study import build_account_plans
from orrery_tradingview_window_replay import (_reference_outcome, _summary, _one_window,
    _aligned_windows, replay_bundle, main)
from test_lsr02_paths import fixture as structural_fixture
from test_tradingview_bundle_audit import fixture, pack

P = dict(buffer=.1, target_r=2, period=2, min_vhf=0, left=1, right=1, lifetime=6000)


def plan(side='BUY'):
    return dict(known_at_msc=300000, side=side, stop=99 if side == 'BUY' else 101,
                target=102 if side == 'BUY' else 98)


def candle(at, opening=100, high=100.5, low=99.5, close=100):
    return dict(close_time=at, open=opening, high=high, low=low, close=close)


def window(sell=False):
    h4, m15, m5 = structural_fixture(sell)
    return dict(start_s=m5[0]['close_time']-300, end_s=m5[-1]['close_time'], h4=h4, m15=m15, m5=m5)


class WindowReplayTests(unittest.TestCase):
    def test_target_and_stop_are_reference_r_without_money_or_cost_claim(self):
        for side, bar, value in (
            ('BUY', candle(600, high=103, close=102), 2),
            ('SELL', candle(600, low=97, close=98), 2),
            ('BUY', candle(600, low=98, close=99), -1)):
            with self.subTest(side=side, value=value):
                r = _reference_outcome(plan(side), [candle(300), bar], 600)
                self.assertEqual(r['reference_r'], value)
                self.assertIsNone(r['net_r']); self.assertIsNone(r['profit_usd'])

    def test_same_bar_stop_and_target_remains_unknown(self):
        r = _reference_outcome(plan(), [candle(300), candle(600, high=103, low=98)], 600)
        self.assertEqual(r['reference_status'], 'AMBIGUOUS_INTRABAR')
        self.assertIsNone(r['reference_r']); self.assertEqual(r['stop_first_reference_r'], -1)
        s = _summary([r])
        self.assertEqual(s['ambiguous'], 1); self.assertIsNone(s['total_all_candidates_gross_reference_r'])

    def test_observed_adverse_open_gap_can_exceed_minus_one_r(self):
        r = _reference_outcome(plan(), [candle(300), candle(600, opening=97, high=103, low=96)], 600)
        self.assertEqual(r['reference_r'], -3)
        self.assertEqual(r['exit_reference_reason'], 'STOP_GAP')

    def test_censored_is_unknown_and_suppresses_full_cohort_metrics(self):
        closed = _reference_outcome(plan(), [candle(300), candle(600, high=103)], 600)
        pending = _reference_outcome(plan(), [candle(300), candle(600)], 600)
        s = _summary([closed, pending])
        self.assertEqual(s['closed_reference'], 1); self.assertEqual(s['censored'], 1)
        self.assertEqual(s['mean_closed_gross_reference_r'], 2)
        self.assertIsNone(s['total_all_candidates_gross_reference_r'])
        self.assertIsNone(s['closed_reference_sequence']['max_drawdown_at_exit_batches_r'])

    def test_entry_bar_extremes_are_not_post_decision_fills(self):
        r = _reference_outcome(plan(), [candle(300, high=103, low=98)], 300)
        self.assertEqual(r['reference_status'], 'CENSORED_AT_WINDOW_END')
        self.assertIsNone(r['reference_r'])

    def test_existing_plan_geometry_and_candidate_ids_are_preserved(self):
        for sell in (False, True):
            w = window(sell)
            native = build_account_plans('XAUUSD', w['h4'], w['m15'], w['m5'], as_of=w['end_s'], **P)
            rows, _ = _one_window(w, P)
            self.assertTrue(rows)
            self.assertEqual([r['plan'] for r in rows], native['plans'])

    def test_future_outcomes_do_not_rewrite_earlier_plan(self):
        w = window(); rows, _ = _one_window(w, P); at = rows[0]['plan']['known_at_msc'] // 1000
        prefix = dict(w, end_s=at, **{f: [b for b in w[f] if b['close_time'] <= at] for f in ('h4','m15','m5')})
        earlier, _ = _one_window(prefix, P)
        self.assertEqual([r['plan'] for r in earlier], [r['plan'] for r in rows if r['plan']['known_at_msc'] <= at*1000])
        self.assertEqual(earlier[0]['entry_context'], rows[0]['entry_context'])
        self.assertEqual(earlier[0]['reference_status'], 'CENSORED_AT_WINDOW_END')

    def test_reset_does_not_carry_sweep_into_later_window(self):
        w = window(); native, _ = _one_window(w, P); self.assertEqual(len(native), 1)
        # Split before the RETEST. Later M5 data may not inherit the earlier sweep.
        at = native[0]['plan']['known_at_msc'] // 1000
        before = dict(w, end_s=at-300, m5=[b for b in w['m5'] if b['close_time'] < at])
        before['m15'] = [b for b in w['m15'] if b['close_time'] <= before['end_s']]
        after = dict(w, m5=[b for b in w['m5'] if b['close_time'] >= at])
        first, _ = _one_window(before, P); second, _ = _one_window(after, P)
        self.assertEqual(first + second, [])

    def test_window_alignment_never_concatenates_gap(self):
        frames = {'5m': [candle(14700), candle(15000), candle(15600), candle(15900)],
                  '15m': [candle(14400), candle(15300), candle(16200)], '4h': [candle(14400), candle(28800)]}
        windows = list(_aligned_windows(frames))
        self.assertEqual([[b['close_time'] for b in w['m5']] for w in windows], [[14700,15000],[15600,15900]])
        self.assertLessEqual(windows[0]['end_s'], windows[1]['start_s'])

    def test_mismatch_before_common_range_is_retained_but_not_used_as_warmup(self):
        from test_tradingview_bundle_audit import iso
        files = fixture(); manifest = json.loads(files['manifest.json'])
        for frame, step in (('5m',300), ('15m',900), ('4h',14400)):
            reader = list(csv.reader(StringIO(files[frame+'.csv'].decode())))
            header, old = reader[0], reader[1:]
            later = [[str(int(r[0])+14400),iso(int(r[0])+14400),*r[2:]] for r in old]
            rows = later if frame == '5m' else old + later
            if frame == '4h': rows[0][4] = '98'
            s = StringIO(); w = csv.writer(s); w.writerow(header); w.writerows(rows)
            files[frame+'.csv'] = s.getvalue().encode()
            declared = next(r for r in manifest['reports'] if r['interval'] == frame)
            declared.update(saved=len(rows),first_open_utc=iso(int(rows[0][0])),
                last_open_utc=iso(int(rows[-1][0])),nominal_last_close_utc=iso(28800))
        manifest['cutoff_utc'] = iso(28800); files['manifest.json'] = json.dumps(manifest).encode()
        r = replay_bundle(pack(files), P)
        self.assertEqual(r['bundle_audit']['nominal_aggregation']['15m_to_4h']['mismatch_count'], 1)
        self.assertEqual(r['bundle_audit']['common_range_nominal_aggregation']['15m_to_4h']['mismatch_count'], 0)
        self.assertFalse(r['warmup_before_common_range_used'])
        self.assertEqual(r['windows'][0]['bars']['h4'], 1)

    def test_bundle_common_mismatch_stops_before_strategy_compiler(self):
        files = fixture(); files['4h.csv'] = files['4h.csv'].replace(b',99,', b',98,')
        with patch('orrery_tradingview_window_replay.build_account_plans') as compiler:
            with self.assertRaisesRegex(ValueError, 'consistency'):
                replay_bundle(pack(files), P)
            compiler.assert_not_called()

    def test_no_signal_does_not_fabricate_profit_and_budgets_fail_closed(self):
        r = replay_bundle(pack(fixture()), P)
        self.assertEqual(r['candidates'], [])
        self.assertIsNone(r['actual_profit_usd']); self.assertFalse(r['execution_allowed'])
        self.assertIsNone(r['summaries']['LSR02']['mean_closed_gross_reference_r'])
        for kw in ({'max_work':1}, {'max_windows':0}):
            with self.assertRaises(ValueError):
                replay_bundle(pack(fixture()), P, **kw)
        for change in ({'buffer':True}, {'target_r':float('nan')}, {'min_vhf':2}):
            with self.assertRaises(ValueError):
                replay_bundle(pack(fixture()), dict(P, **change))

    def test_cli_is_read_only_and_exclusive(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); source = root/'bars.zip'; config = root/'params.json'; output = root/'result.json'
            raw = pack(fixture()); source.write_bytes(raw); config.write_text(json.dumps(P))
            self.assertEqual(main([str(source),'--parameters',str(config),'--output',str(output)]), 0)
            self.assertEqual(source.read_bytes(), raw)
            self.assertFalse(json.loads(output.read_text())['account_risk_controls_applied'])
            with self.assertRaises(FileExistsError):
                main([str(source),'--parameters',str(config),'--output',str(output)])


if __name__ == '__main__':
    unittest.main()
