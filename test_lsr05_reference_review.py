# SPDX-License-Identifier: GPL-3.0-only
"""Synthetic file workflow tests, not an actual external reference comparison."""
from copy import deepcopy
from contextlib import redirect_stdout
from io import StringIO
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import subprocess
import sys
import unittest

from lsr04_tick_archive import _encode, _decode
from lsr05_halftrend import calculate, SOURCE_SHA256
from lsr05_reference_compare import FIELDS
import lsr05_reference_review as review


class ReferenceReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        bars = [dict(close_time=(i + 1) * 300, open=100., high=100.5, low=99.5, close=100.) for i in range(100)]
        rows = calculate(bars, as_of=30000, interval=300, enabled=True)['rows']
        settings = dict(schema_version=1, symbol='XAUUSD', data_source='SYNTHETIC_TEST_ONLY',
                        as_of=30000, interval=300, amplitude=2, channel_deviation=2,
                        absolute_tolerance=1e-8, calendar_evidence=None, expected_calendar_sha256=None)
        reference = dict(schema_version=1, platform='TRADINGVIEW',
            implementation_label='Synthetic comparator fixture, not external Pine output', implementation_sha256='a' * 64,
            source_sha256=SOURCE_SHA256, symbol='XAUUSD', data_source='SYNTHETIC_TEST_ONLY',
            captured_at=30000, interval=300, amplitude=2, channel_deviation=2, calendar_sha256=None,
            bars=deepcopy(bars), rows=[{k: r[k] for k in FIELDS} for r in rows])
        self.objects = dict(zip(review.INPUTS, (bars, reference, settings)))
        self.paths = {name: self.root / name for name in review.INPUTS}
        self.output = self.root / 'new review'
        self.write_inputs()

    def write_inputs(self):
        for name, obj in self.objects.items(): self.paths[name].write_bytes(_encode(obj))

    def args(self):
        return dict(bars_path=self.paths['bars.json'], bars_sha256=sha256(self.paths['bars.json'].read_bytes()).hexdigest(),
            reference_path=self.paths['reference.json'], reference_raw_sha256=sha256(self.paths['reference.json'].read_bytes()).hexdigest(),
            settings_path=self.paths['settings.json'], settings_sha256=sha256(self.paths['settings.json'].read_bytes()).hexdigest())

    def save(self): return review.save_review(self.output, **self.args())

    def verify(self, pin): return review.verify_review(self.output, expected_receipt_sha256=pin)

    def test_copies_exact_bytes_and_replays_without_source_files(self):
        result = self.save()
        for name, path in self.paths.items():
            self.assertEqual(path.read_bytes(), (self.output / name).read_bytes())
            path.unlink()
        checked = self.verify(result['receipt_sha256'])
        self.assertTrue(checked['comparison_recomputed'])
        self.assertEqual(checked['status'], 'REFERENCE_SAMPLE_MATCHED_NOT_VERIFIED')
        self.assertFalse(checked['external_export_authenticity_verified'])
        self.assertFalse(checked['execution_allowed'])

    def test_wrong_input_pin_stops_before_output_creation(self):
        args = self.args(); args['reference_raw_sha256'] = '0' * 64
        with self.assertRaises(ValueError): review.save_review(self.output, **args)
        self.assertFalse(self.output.exists())

    def test_duplicate_json_key_or_unbounded_input_stops(self):
        self.paths['settings.json'].write_bytes(b'{"schema_version":1,"schema_version":1}')
        with self.assertRaises(ValueError): self.save()
        self.assertFalse(self.output.exists())
        self.write_inputs()
        with patch.object(review, 'MAX_INPUT_BYTES', 32):
            with self.assertRaises(ValueError): self.save()
        self.assertFalse(self.output.exists())

    def test_existing_output_never_overwritten(self):
        self.output.mkdir(); marker = self.output / 'keep.txt'; marker.write_text('keep')
        with self.assertRaises(FileExistsError): self.save()
        self.assertEqual(marker.read_text(), 'keep')

    def test_mismatch_and_context_block_saved_without_success_exit(self):
        for number, mutate in enumerate((lambda r: r['rows'][99].update(line=101.),
                                        lambda r: r.update(data_source='OTHER'))):
            self.output = self.root / str(number)
            mutate(self.objects['reference.json']); self.write_inputs()
            result = self.save()
            self.assertIn(result['status'], ('REFERENCE_MISMATCH', 'BLOCKED_REFERENCE_CONTEXT'))
            self.assertEqual(review._exit_code(result['status']), 2)
            self.assertEqual(self.verify(result['receipt_sha256'])['status'], result['status'])
            with redirect_stdout(StringIO()):
                self.assertEqual(review.main(['verify', '--run', str(self.output),
                    '--receipt-sha256', result['receipt_sha256']]), 2)

    def test_saved_input_and_result_mutations_rejected(self):
        result = self.save()
        for name in ('reference.json', 'result.json', 'settings.json', 'bars.json'):
            path = self.output / name; before = path.read_bytes(); path.write_bytes(before + b' ')
            with self.assertRaises(ValueError): self.verify(result['receipt_sha256'])
            path.write_bytes(before)

    def test_missing_marker_extra_member_and_stale_receipt_rejected(self):
        result = self.save(); marker = self.output / 'complete.json'; raw = marker.read_bytes()
        marker.unlink()
        with self.assertRaises(ValueError): self.verify(result['receipt_sha256'])
        marker.write_bytes(raw)
        extra = self.output / 'extra.json'; extra.write_text('{}')
        with self.assertRaises(ValueError): self.verify(result['receipt_sha256'])
        extra.unlink()
        with self.assertRaises(ValueError): self.verify('0' * 64)

    def test_replay_detects_forged_result_even_with_new_receipt_pin(self):
        self.save()
        result_file = self.output / 'result.json'; result = _decode(result_file.read_bytes())
        result['compared_bars'] = 999
        raw = _encode(result); result_file.write_bytes(raw)
        marker = self.output / 'complete.json'; receipt = _decode(marker.read_bytes())
        receipt['files']['result.json'] = dict(bytes=len(raw), sha256=sha256(raw).hexdigest())
        raw = _encode(receipt); marker.write_bytes(raw)
        with self.assertRaises(ValueError): self.verify(sha256(raw).hexdigest())

    def test_code_version_change_refuses_replay(self):
        result = self.save()
        with patch.object(review, '_code_pins', return_value={'changed': 'b' * 64}):
            with self.assertRaises(ValueError): self.verify(result['receipt_sha256'])

    def test_partial_write_is_not_resumed_or_verified(self):
        real = review._write_exclusive
        def fail(path, data):
            if path.name == 'result.json': raise OSError('simulated interrupted write')
            real(path, data)
        with patch.object(review, '_write_exclusive', side_effect=fail):
            with self.assertRaises(OSError): self.save()
        self.assertFalse((self.output / 'complete.json').exists())
        with self.assertRaises(ValueError): self.verify('0' * 64)
        with self.assertRaises(FileExistsError): self.save()

    def test_cli_roundtrip_and_bad_pin_exit(self):
        argv = [sys.executable, str(Path(review.__file__).resolve()), 'run', '--output', str(self.output)]
        for name, value in self.args().items():
            option = {'bars_path': 'bars', 'reference_path': 'reference', 'settings_path': 'settings'}.get(name, name.replace('_', '-'))
            argv.extend(['--' + option, str(value)])
        run = subprocess.run(argv, capture_output=True, text=True, timeout=20)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        pin = [line.split('=', 1)[1] for line in run.stdout.splitlines() if line.startswith('RECEIPT_SHA256=')][0]
        verified = subprocess.run([sys.executable, str(Path(review.__file__).resolve()), 'verify',
            '--run', str(self.output), '--receipt-sha256', pin], capture_output=True, text=True, timeout=20)
        self.assertEqual(verified.returncode, 0, verified.stdout + verified.stderr)
        self.assertNotIn(str(self.root), verified.stdout)
        with redirect_stdout(StringIO()):
            self.assertEqual(review.main(['verify', '--run', str(self.output), '--receipt-sha256', '0' * 64]), 1)


if __name__ == '__main__': unittest.main()
