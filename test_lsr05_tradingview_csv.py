# SPDX-License-Identifier: GPL-3.0-only
"""Synthetic CSV and static Pine checks; NOT Pine execution/parity tests."""
from contextlib import redirect_stdout
from copy import deepcopy
import csv
from hashlib import sha256
from io import StringIO
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from lsr04_tick_archive import _encode, _decode
from lsr05_halftrend import calculate
import lsr05_tradingview_csv as intake


class TradingViewCSVTests(unittest.TestCase):
    def setUp(self):
        self.columns = {name: 'ORRERY_HT05_' + name for name in intake.COLUMNS}
        self.settings = dict(schema_version=1, symbol='XAUUSD', data_source='SYNTHETIC_TEST_ONLY',
            as_of=33000, interval=300, amplitude=2, channel_deviation=2, absolute_tolerance=1e-8,
            calendar_evidence=None, expected_calendar_sha256=None)
        self.config = dict(schema_version=1, script_sha256=intake._code_pins()[intake.PINE_FILE],
            captured_at=33000, missing_token='', column_map=self.columns, settings=self.settings)
        prices = [100.] * 100 + [102., 104., 106., 100., 98., 96., 104.]
        self.bars = [dict(close_time=(i+1)*300, open=p, high=p+.5, low=p-.5, close=p) for i,p in enumerate(prices)]
        out = calculate(self.bars, as_of=33000, interval=300, enabled=True)
        self.cells = []
        for i, (b, r) in enumerate(zip(self.bars, out['rows'])):
            self.cells.append(dict(SCHEMA=1, INDEX=i, OPEN_MS=(b['close_time']-300)*1000,
                CLOSE_MS=b['close_time']*1000, CONFIRMED=1, STANDARD=1, INTERVAL_SEC=300,
                AMPLITUDE=2, DEVIATION=2, OPEN=b['open'], HIGH=b['high'], LOW=b['low'], CLOSE=b['close'],
                STATE=0 if r['state']=='UP' else 1, LINE=r['line'], ATR100=r['atr'],
                ATR_HIGH=r['atr_high'], ATR_LOW=r['atr_low'],
                SIGNAL={None:0,'BUY':1,'SELL':-1}[r['signal']], READY=int(r['ready'])))

    def csv_bytes(self, *, bom=False, extra=False):
        stream = StringIO(newline='')
        names = list(intake.COLUMNS)
        writer = csv.writer(stream)
        writer.writerow([self.columns[n] for n in names] + (['Unmapped native time'] if extra else []))
        for row in self.cells:
            writer.writerow([self.config['missing_token'] if row[n] is None else row[n] for n in names] + (['ignored'] if extra else []))
        return (b'\xef\xbb\xbf' if bom else b'') + stream.getvalue().encode()

    def normalize(self): return intake.normalize_csv(self.csv_bytes(), self.config)

    def test_synthetic_csv_maps_exact_clocks_and_signals(self):
        payloads, audit, result = self.normalize()
        self.assertEqual(_decode(payloads['bars.json']), self.bars)
        self.assertEqual(result['status'], 'REFERENCE_SAMPLE_MATCHED_NOT_VERIFIED')
        self.assertFalse(audit['pine_compiled_verified'])
        self.assertFalse(result['tradingview_parity_verified'])
        self.assertEqual([r['signal'] for r in _decode(payloads['reference.json'])['rows'][-3:]], ['SELL', None, 'BUY'])

    def test_bom_explicit_prefixed_mapping_and_extra_columns(self):
        self.columns = {name: 'Diagnostic: ' + name for name in intake.COLUMNS}
        self.config['column_map'] = self.columns
        out = intake.normalize_csv(self.csv_bytes(bom=True, extra=True), self.config)
        self.assertEqual(out[2]['status'], 'REFERENCE_SAMPLE_MATCHED_NOT_VERIFIED')

    def test_nonzero_first_index_and_skipped_index_rejected(self):
        for index in (0, 30):
            before = self.cells[index]['INDEX']; self.cells[index]['INDEX'] += 1
            with self.assertRaises(ValueError): self.normalize()
            self.cells[index]['INDEX'] = before

    def test_one_trailing_unconfirmed_row_deferred_not_formal_signal(self):
        last = dict(self.cells[-1], INDEX=107, OPEN_MS=32100000, CLOSE_MS=32400000, CONFIRMED=0, SIGNAL=-1)
        self.cells.append(last)
        payloads, audit, result = self.normalize()
        self.assertEqual(audit['deferred_unconfirmed_rows'], 1)
        self.assertEqual(audit['confirmed_rows'], 107)
        self.assertEqual(len(_decode(payloads['reference.json'])['rows']), 107)
        self.assertEqual(result['status'], 'REFERENCE_SAMPLE_MATCHED_NOT_VERIFIED')
        self.cells.append(dict(last, INDEX=108, OPEN_MS=32400000, CLOSE_MS=32700000))
        with self.assertRaises(ValueError): self.normalize()

    def test_unconfirmed_in_middle_future_closed_and_overlapping_rejected(self):
        for name, value in [('CONFIRMED', 0), ('OPEN_MS', 0), ('CLOSE_MS', 30100000)]:
            before = self.cells[50][name]; self.cells[50][name] = value
            with self.assertRaises(ValueError): self.normalize()
            self.cells[50][name] = before
        self.config['captured_at'] = 32099
        with self.assertRaises(ValueError): self.normalize()

    def test_nonstandard_wrong_setting_or_unsupported_signal_rejected(self):
        for name, value in [('STANDARD', 0), ('AMPLITUDE', 4), ('INTERVAL_SEC', 60),
                            ('READY', 2), ('SIGNAL', 2), ('STATE', -1), ('SCHEMA', 2)]:
            before = self.cells[30][name]; self.cells[30][name] = value
            with self.assertRaises(ValueError): self.normalize()
            self.cells[30][name] = before

    def test_decimal_millisecond_timestamps_not_rounded_from_seconds(self):
        self.cells[30]['CLOSE_MS'] += .5
        with self.assertRaises(ValueError): self.normalize()
        self.cells[30]['CLOSE_MS'] = 9300
        with self.assertRaises(ValueError): self.normalize()

    def test_explicit_missing_token_not_zero_or_inferred_nan(self):
        self.config['missing_token'] = 'NaN'
        self.assertEqual(self.normalize()[2]['status'], 'REFERENCE_SAMPLE_MATCHED_NOT_VERIFIED')
        self.cells[0]['ATR100'] = 'n/a'
        with self.assertRaises(ValueError): self.normalize()
        self.cells[0]['ATR100'] = 0
        self.assertEqual(self.normalize()[2]['status'], 'REFERENCE_MISMATCH')

    def test_headers_ragged_rows_and_bad_prices_rejected(self):
        raw = self.csv_bytes()
        for changed in (raw.replace(b'ORRERY_HT05_INDEX', b'ORRERY_HT05_SCHEMA', 1), raw + b'1,2\n'):
            with self.assertRaises(ValueError): intake.normalize_csv(changed, self.config)
        for value in ('Infinity', '1e999', ' 100', ''):
            self.cells[0]['LINE'] = value
            with self.assertRaises(ValueError): self.normalize()

    def test_wrong_script_pin_or_implicit_mapping_rejected(self):
        original = deepcopy(self.config)
        self.config['script_sha256'] = '0'*64
        with self.assertRaises(ValueError): self.normalize()
        self.config = original; self.config['column_map'].pop('INDEX')
        with self.assertRaises(ValueError): self.normalize()

    def test_prepared_receipt_roundtrip_and_source_tamper_detection(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp); src=root/'input.csv'; cfg=root/'config.json'; dst=root/'prepared'
            src.write_bytes(self.csv_bytes()); cfg.write_bytes(_encode(self.config))
            result=intake.prepare_review(src, cfg, dst, expected_csv_sha256=sha256(src.read_bytes()).hexdigest(),
                expected_config_sha256=sha256(cfg.read_bytes()).hexdigest())
            checked=intake.verify_prepared(dst, expected_receipt_sha256=result['receipt_sha256'])
            self.assertTrue(checked['csv_conversion_recomputed'])
            self.assertTrue(checked['comparison_recomputed'])
            self.assertFalse(checked['execution_allowed'])
            src.unlink(); cfg.unlink()
            self.assertEqual(intake.verify_prepared(dst, expected_receipt_sha256=result['receipt_sha256'])['status'], result['status'])
            (dst/'source.csv').write_bytes(b'changed')
            with self.assertRaises(ValueError): intake.verify_prepared(dst, expected_receipt_sha256=result['receipt_sha256'])

    def test_wrong_raw_pin_no_output_and_no_overwrite(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp); src=root/'in.csv'; cfg=root/'cfg.json'; dst=root/'out'
            src.write_bytes(self.csv_bytes()); cfg.write_bytes(_encode(self.config))
            args=dict(expected_csv_sha256='0'*64, expected_config_sha256=sha256(cfg.read_bytes()).hexdigest())
            with self.assertRaises(ValueError): intake.prepare_review(src, cfg, dst, **args)
            self.assertFalse(dst.exists())
            args['expected_csv_sha256']=sha256(src.read_bytes()).hexdigest()
            intake.prepare_review(src, cfg, dst, **args)
            with self.assertRaises(FileExistsError): intake.prepare_review(src, cfg, dst, **args)

    def test_cli_run_verify_and_partial_case_rejection(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp); src=root/'input.csv'; cfg=root/'config.json'; dst=root/'review case'
            src.write_bytes(self.csv_bytes()); cfg.write_bytes(_encode(self.config))
            command=[sys.executable, str(Path(intake.__file__).resolve()), 'run', '--csv', str(src),
                '--csv-sha256', sha256(src.read_bytes()).hexdigest(), '--config', str(cfg),
                '--config-sha256', sha256(cfg.read_bytes()).hexdigest(), '--output', str(dst)]
            run=subprocess.run(command, capture_output=True, text=True, timeout=20)
            self.assertEqual(run.returncode, 0, run.stdout+run.stderr)
            pin=[line.split('=',1)[1] for line in run.stdout.splitlines() if line.startswith('RECEIPT_SHA256=')][0]
            with redirect_stdout(StringIO()):
                self.assertEqual(intake.main(['verify','--run',str(dst),'--receipt-sha256',pin]),0)
                (dst/'complete.json').unlink()
                self.assertEqual(intake.main(['verify','--run',str(dst),'--receipt-sha256',pin]),1)

    def test_forged_generated_file_cannot_bypass_reconversion(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp); src=root/'in.csv'; cfg=root/'cfg.json'; dst=root/'out'
            src.write_bytes(self.csv_bytes()); cfg.write_bytes(_encode(self.config))
            intake.prepare_review(src,cfg,dst,expected_csv_sha256=sha256(src.read_bytes()).hexdigest(),
                                  expected_config_sha256=sha256(cfg.read_bytes()).hexdigest())
            path=dst/'reference.json'; obj=_decode(path.read_bytes()); obj['rows'][0]['line']=500
            path.write_bytes(_encode(obj)); marker=dst/'complete.json'; receipt=_decode(marker.read_bytes())
            receipt['files']['reference.json']=sha256(path.read_bytes()).hexdigest()
            raw=_encode(receipt); marker.write_bytes(raw)
            with self.assertRaises(ValueError): intake.verify_prepared(dst, expected_receipt_sha256=sha256(raw).hexdigest())

    def test_static_wrapper_preserves_pinned_algorithm_not_pine_execution(self):
        root=Path(intake.__file__).resolve().parent
        original=(root/'research_refs/halftrend/halftrend.pine').read_text()
        wrapper=(root/intake.PINE_FILE).read_text()
        prefix=wrapper.split('// ORRERY_EXPORT_DIAGNOSTICS_V1')[0].rstrip()+'\n'
        restored=prefix.replace("indicator('ORRERY HalfTrend 05 Export Diagnostic', overlay = true, precision = 10)",
                                "indicator('HalfTrend', overlay = true)")
        self.assertEqual(restored,original)
        for name in intake.COLUMNS:
            self.assertEqual(wrapper.count("title = 'ORRERY_HT05_"+name+"'"),1)
        self.assertNotIn('strategy.entry(',wrapper)


if __name__=='__main__': unittest.main()
