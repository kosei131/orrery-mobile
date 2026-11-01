import csv
from datetime import datetime, timezone
from io import BytesIO, StringIO
import json
import tempfile
import unittest
from pathlib import Path
import zipfile

from orrery_tradingview_bundle_audit import audit_bundle, main, FIELDS, FRAMES


def iso(at):
    return datetime.fromtimestamp(at, timezone.utc).isoformat().replace('+00:00', 'Z')


def fixture():
    files = {}; reports = []
    for frame, seconds in FRAMES.items():
        rows = [[str(at), iso(at), '100', '102', '99', '101', '10']
                for at in range(0, 14400, seconds)]
        s = StringIO(); w = csv.writer(s); w.writerow(FIELDS); w.writerows(rows)
        files[frame + '.csv'] = s.getvalue().encode()
        files[frame + '_time_gaps.csv'] = b'not used as evidence\n'
        reports.append(dict(interval=frame, symbol='OANDA:XAUUSD', provider='OANDA via TradingView MCP',
            saved=len(rows), first_open_utc=iso(0), last_open_utc=iso(14400-seconds),
            nominal_last_close_utc=iso(14400)))
    files['manifest.json'] = json.dumps(dict(cutoff_utc=iso(14400), reports=reports)).encode()
    files['README.txt'] = b'SYNTHETIC AUDIT FIXTURE'
    return files


def pack(files):
    stream = BytesIO()
    with zipfile.ZipFile(stream, 'w') as z:
        for name, raw in files.items():
            z.writestr(name, raw)
    return stream.getvalue()


class BundleTests(unittest.TestCase):
    def test_matching_three_frames_are_not_execution_or_profit_proof(self):
        r = audit_bundle(pack(fixture()))
        counts = {k: c['checked_complete_parent_bars'] for k, c in r['nominal_aggregation'].items()}
        self.assertEqual(counts, {'5m_to_15m': 16, '15m_to_4h': 1, '5m_to_4h': 1})
        self.assertTrue(all(c['all_parent_bars_verified'] for c in r['nominal_aggregation'].values()))
        self.assertIsNone(r['actual_profit_usd'])
        for flag in ('source_authenticated', 'candidate_replay_allowed', 'execution_allowed', 'six_month_backtest_complete'):
            self.assertFalse(r[flag])

    def test_valid_but_inconsistent_h4_reports_exact_price_and_clock(self):
        files = fixture(); files['4h.csv'] = files['4h.csv'].replace(b',99,', b',98,')
        r = audit_bundle(pack(files))
        self.assertEqual(r['status'], 'REVIEW_REQUIRED_NOMINAL_OHLC_MISMATCH')
        for key in ('15m_to_4h', '5m_to_4h'):
            check = r['nominal_aggregation'][key]
            self.assertEqual(check['mismatch_count'], 1)
            self.assertEqual(check['mismatch_examples'][0]['fields'], ['low'])
            self.assertEqual(check['mismatch_examples'][0]['aggregate_ohlc']['low'], '99')

    def test_missing_child_is_unknown_not_zero_or_false_mismatch(self):
        files = fixture(); lines = files['5m.csv'].splitlines(); del lines[3]
        files['5m.csv'] = b'\n'.join(lines)
        manifest = json.loads(files['manifest.json']); manifest['reports'][0]['saved'] -= 1
        files['manifest.json'] = json.dumps(manifest).encode()
        r = audit_bundle(pack(files)); c = r['nominal_aggregation']['5m_to_15m']
        self.assertEqual(c['checked_complete_parent_bars'], 15)
        self.assertEqual(c['incomplete_child_windows'], 1)
        self.assertEqual(c['mismatch_count'], 0)
        self.assertFalse(c['all_parent_bars_verified'])
        self.assertEqual(r['frames']['5m']['non_nominal_intervals'], 1)

    def test_dual_clock_disagreement_and_nonfinite_rejected(self):
        for before, after in ((b'0,1970-', b'1,1970-'), (b',99,', b',NaN,')):
            files = fixture(); files['5m.csv'] = files['5m.csv'].replace(before, after, 1)
            with self.assertRaises(ValueError):
                audit_bundle(pack(files))

    def test_manifest_count_and_identity_cannot_certify_data(self):
        files = fixture(); m = json.loads(files['manifest.json']); m['reports'][0]['saved'] = 99
        files['manifest.json'] = json.dumps(m).encode()
        r = audit_bundle(pack(files))
        self.assertEqual(r['manifest_mismatches'], [dict(frame='5m', field='saved')])
        m['reports'][1]['symbol'] = 'OANDA:USDJPY'
        files['manifest.json'] = json.dumps(m).encode()
        with self.assertRaises(ValueError):
            audit_bundle(pack(files))

    def test_traversal_and_duplicate_archive_members_rejected_without_extraction(self):
        files = fixture(); files['../surprise'] = b'x'
        with self.assertRaises(ValueError):
            audit_bundle(pack(files))
        stream = BytesIO(pack(fixture()))
        with zipfile.ZipFile(stream, 'a') as z:
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter('ignore'); z.writestr('5m.csv', b'duplicate')
        with self.assertRaises(ValueError):
            audit_bundle(stream.getvalue())

    def test_unfinished_bar_is_not_silently_used(self):
        files = fixture(); m = json.loads(files['manifest.json']); m['cutoff_utc'] = iso(14399)
        files['manifest.json'] = json.dumps(m).encode()
        with self.assertRaisesRegex(ValueError, 'Unconfirmed'):
            audit_bundle(pack(files))

    def test_blank_csv_lines_are_counted_without_changing_bar_rows(self):
        files = fixture(); files['5m.csv'] += b'\n\n'
        r = audit_bundle(pack(files))
        self.assertEqual(r['frames']['5m']['rows'], 48)
        self.assertEqual(r['frames']['5m']['blank_lines'], 2)
        self.assertEqual(r['manifest_mismatches'], [])

    def test_non_grid_h4_shift_is_reported_without_repairing_or_certifying_session(self):
        files = fixture()
        files['4h.csv'] += f'18000,{iso(18000)},100,102,99,101,10\r\n'.encode()
        m = json.loads(files['manifest.json']); m['cutoff_utc'] = iso(32400)
        m['reports'][2].update(saved=2, last_open_utc=iso(18000), nominal_last_close_utc=iso(32400))
        files['manifest.json'] = json.dumps(m).encode()
        r = audit_bundle(pack(files))
        self.assertEqual(r['frames']['4h']['rows'], 2)
        self.assertEqual(r['frames']['4h']['non_grid_intervals'], 1)
        self.assertEqual(r['frames']['4h']['non_grid_examples'][0]['delta_seconds'], 18000)
        self.assertFalse(r['session_calendar_verified'])

    def test_cli_writes_report_once_without_modifying_archive(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); source = root/'input.zip'; output = root/'audit.json'
            raw = pack(fixture()); source.write_bytes(raw)
            self.assertEqual(main([str(source), '--output', str(output)]), 0)
            self.assertEqual(source.read_bytes(), raw)
            self.assertFalse(json.loads(output.read_text())['execution_allowed'])
            with self.assertRaises(FileExistsError):
                main([str(source), '--output', str(output)])


if __name__ == '__main__':
    unittest.main()
