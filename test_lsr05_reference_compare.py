# SPDX-License-Identifier: GPL-3.0-only
"""Synthetic comparator tests; local output is NOT an independent reference."""
import unittest
from copy import deepcopy
from lsr05_halftrend import calculate, SOURCE_SHA256
from lsr05_reference_compare import compare_reference, reference_sha256, FIELDS


class ReferenceCompareTests(unittest.TestCase):
    def setUp(self):
        prices = [100.] * 100 + [102., 104., 106., 100., 98., 96., 104.]
        self.bars = [dict(close_time=(i + 1) * 300, open=p, high=p + .5, low=p - .5, close=p)
                     for i, p in enumerate(prices)]
        self.settings = dict(symbol='XAUUSD', data_source='SYNTHETIC_TEST_ONLY',
                             as_of=33000, interval=300, amplitude=2, channel_deviation=2,
                             absolute_tolerance=1e-8)
        out = calculate(self.bars, as_of=33000, interval=300, enabled=True)
        self.ref = dict(schema_version=1, platform='TRADINGVIEW',
                        implementation_label='SYNTHETIC comparator fixture, not exported Pine',
                        implementation_sha256='a' * 64, source_sha256=SOURCE_SHA256,
                        symbol='XAUUSD', data_source='SYNTHETIC_TEST_ONLY', captured_at=33000,
                        interval=300, amplitude=2, channel_deviation=2, calendar_sha256=None,
                        bars=deepcopy(self.bars), rows=[{k: r[k] for k in FIELDS} for r in out['rows']])

    def compare(self, **settings):
        return compare_reference(self.bars, self.ref, expected_reference_sha256=reference_sha256(self.ref),
                                 **(self.settings | settings))

    def test_equal_synthetic_fixture_does_not_certify_parity(self):
        before = deepcopy(self.ref)
        result = self.compare()
        self.assertEqual(result['status'], 'REFERENCE_SAMPLE_MATCHED_NOT_VERIFIED')
        self.assertEqual(result['compared_bars'], 107)
        for key in ('independent_reference_verified', 'tradingview_parity_verified',
                    'mt5_parity_verified', 'nonrepainting_verified', 'market_edge_verified', 'execution_allowed'):
            self.assertFalse(result[key])
        self.assertEqual(self.ref, before)

    def test_line_atr_and_signal_changes_identified_at_original_clock(self):
        self.ref['rows'][104]['line'] += .1
        self.ref['rows'][104]['atr'] += .2
        self.ref['rows'][104]['signal'] = None
        out = self.compare()
        self.assertEqual(out['status'], 'REFERENCE_MISMATCH')
        self.assertEqual(out['mismatch_counts']['signal'], 1)
        self.assertEqual(out['mismatch_examples'][0]['at'], 31500)
        self.assertAlmostEqual(out['maximum_absolute_differences']['atr'], .2)

    def test_missing_extra_or_shifted_rows_never_match(self):
        self.ref['rows'].pop(50)
        self.ref['rows'][-1]['at'] += 300
        out = self.compare()
        self.assertEqual((out['missing_bars'], out['extra_bars']), (2, 1))
        self.assertEqual(out['status'], 'REFERENCE_MISMATCH')

    def test_changed_ohlc_history_seed_feed_or_settings_block_comparison(self):
        original = deepcopy(self.ref)
        for key, value in [('symbol', 'USDJPY'), ('amplitude', 4), ('interval', True),
                           ('source_sha256', 'b' * 64), ('data_source', 'OTHER')]:
            self.ref = deepcopy(original)
            self.ref[key] = value
            self.assertEqual(self.compare()['status'], 'BLOCKED_REFERENCE_CONTEXT')
        self.ref = deepcopy(original)
        self.ref['bars'][0]['close'] += .01
        self.assertIn('input_bars_or_history_seed', self.compare()['context_mismatches'])
        self.ref = deepcopy(original)
        self.ref['bars'].pop(0)
        self.assertEqual(self.compare()['status'], 'BLOCKED_REFERENCE_CONTEXT')

    def test_pin_tampering_and_future_capture_rejected(self):
        pin = reference_sha256(self.ref)
        self.ref['implementation_label'] = 'changed'
        with self.assertRaises(ValueError):
            compare_reference(self.bars, self.ref, expected_reference_sha256=pin, **self.settings)
        self.ref['captured_at'] = 33001
        with self.assertRaises(ValueError): self.compare()
        self.ref['captured_at'] = 30000
        with self.assertRaises(ValueError): self.compare()

    def test_explicit_small_tolerance_only_applies_to_prices(self):
        self.ref['rows'][-1]['line'] += .00001
        self.assertEqual(self.compare()['status'], 'REFERENCE_MISMATCH')
        self.assertEqual(self.compare(absolute_tolerance=.0001)['status'], 'REFERENCE_SAMPLE_MATCHED_NOT_VERIFIED')
        self.ref['rows'][-1]['state'] = 'DOWN'
        self.assertEqual(self.compare(absolute_tolerance=.0001)['status'], 'REFERENCE_MISMATCH')
        for value in (True, -.1, .02, float('nan')):
            with self.assertRaises(ValueError): self.compare(absolute_tolerance=value)

    def test_null_atr_is_not_zero_and_readiness_is_compared(self):
        self.ref['rows'][0]['atr'] = 0.
        self.ref['rows'][0]['ready'] = True
        out = self.compare()
        self.assertEqual(out['mismatch_counts']['atr'], 1)
        self.assertEqual(out['mismatch_counts']['ready'], 1)

    def test_malformed_and_duplicate_output_rejected(self):
        original = deepcopy(self.ref)
        for change in (dict(at=True), dict(line=float('inf')), dict(ready=1), dict(signal='WAIT')):
            self.ref = deepcopy(original)
            self.ref['rows'][-1].update(change)
            with self.assertRaises(ValueError): self.compare()
        self.ref = deepcopy(original)
        self.ref['rows'][-1]['at'] = self.ref['rows'][-2]['at']
        with self.assertRaises(ValueError): self.compare()

    def test_empty_output_and_warmup_do_not_match(self):
        self.ref['rows'] = []
        out = self.compare()
        self.assertEqual(out['status'], 'REFERENCE_MISMATCH')
        self.assertEqual(out['missing_bars'], 107)
        self.bars = self.bars[:50]
        self.ref['bars'] = deepcopy(self.bars)
        self.assertIn('local_history_not_ready', self.compare()['context_mismatches'])

    def test_session_calendar_is_pinned_and_not_silently_changed(self):
        from datetime import datetime, timezone
        from lsr05_session_clock import evidence_sha256
        start = int(datetime(2026, 10, 26, tzinfo=timezone.utc).timestamp())
        for i, bar in enumerate(self.bars):
            bar['close_time'] = start + (i + 1 + (12 if i >= 50 else 0)) * 300
        evidence = dict(symbol='XAUUSD', data_source='SYNTHETIC_TEST_ONLY',
            known_at_utc='2026-10-25T00:00:00+00:00', source_document_sha256='c' * 64,
            calendar=dict(source='SYNTHETIC_TEST_ONLY', intervals=[
                dict(start_utc='2026-10-26T00:00:00+00:00', end_utc='2026-10-26T04:10:00+00:00', state='OPEN'),
                dict(start_utc='2026-10-26T04:10:00+00:00', end_utc='2026-10-26T05:10:00+00:00', state='CLOSED'),
                dict(start_utc='2026-10-26T05:10:00+00:00', end_utc='2026-10-26T09:55:00+00:00', state='OPEN')]))
        pin = evidence_sha256(evidence)
        self.settings.update(as_of=self.bars[-1]['close_time'], calendar_evidence=evidence,
                             expected_calendar_sha256=pin)
        local = calculate(self.bars, as_of=self.settings['as_of'], interval=300, enabled=True,
                          symbol='XAUUSD', data_source='SYNTHETIC_TEST_ONLY',
                          calendar_evidence=evidence, expected_calendar_sha256=pin)
        self.ref.update(captured_at=self.settings['as_of'], calendar_sha256=pin,
                        bars=deepcopy(self.bars), rows=[{k: r[k] for k in FIELDS} for r in local['rows']])
        self.assertEqual(self.compare()['status'], 'REFERENCE_SAMPLE_MATCHED_NOT_VERIFIED')
        self.ref['calendar_sha256'] = None
        self.assertIn('calendar_sha256', self.compare()['context_mismatches'])

    def test_m15_mt5_and_usdjpy_context_remain_separate(self):
        for row in self.bars: row['close_time'] *= 3
        self.settings.update(symbol='USDJPY', interval=900, as_of=100000)
        local = calculate(self.bars, as_of=100000, interval=900, enabled=True)
        self.ref.update(platform='MT5', symbol='USDJPY', interval=900, captured_at=100000,
                        bars=deepcopy(self.bars), rows=[{k: r[k] for k in FIELDS} for r in local['rows']])
        self.assertEqual(self.compare()['status'], 'REFERENCE_SAMPLE_MATCHED_NOT_VERIFIED')


if __name__ == '__main__': unittest.main()
