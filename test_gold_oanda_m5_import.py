from datetime import datetime, timezone
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import orrery_gold_nested_wave_holdout as holdout

from orrery_gold_nested_wave_holdout import START, audit_source
from orrery_gold_oanda_m5_import import normalize
from orrery_real_bars_lsr_bridge import load


class OandaImportTests(unittest.TestCase):
    def test_normalized_csv_feeds_audit_and_bad_pages_fail_before_output(self):
        candle = dict(time='2026-12-01T00:00:00.000000000Z', complete=True,
                      mid=dict(o='4000', h='4002', l='3999', c='4001'))
        with TemporaryDirectory() as directory:
            root = Path(directory)
            page = root / 'page.json'

            def write(candles):
                page.write_text(json.dumps(dict(instrument='XAU_USD', granularity='M5',
                                                candles=candles)), encoding='utf-8')

            write([candle])
            output = root / 'valid'
            receipt = normalize([page], output)
            bars = load(output / 'xauusd_m5_mid.csv', 'M5')['bars']
            self.assertEqual(bars[0]['open_time'], START)
            self.assertEqual(audit_source(bars, receipt, receipt['csv_sha256'])['observed_slots'], 1)
            for candles in ([dict(candle, complete=False)], [candle, candle],
                            [dict(candle, time='2026-12-01T00:00:00.000000001Z')]):
                write(candles)
                with self.assertRaises(ValueError):
                    normalize([page], root / 'bad')
                self.assertFalse((root / 'bad').exists())

    def test_archived_pages_reach_all_three_arms_with_real_candidate_detection(self):
        for resume_close, should_pass in ((113, True), (118, False)):
            with self.subTest(resume_close=resume_close), TemporaryDirectory() as directory:
                root = Path(directory)
                # Three closed H1 blocks, then an M15 pullback and a later breakout.
                patterns = ([(104, 105, 103, 104)] * 4
                            + [(104, 124, 102, 115)] * 4
                            + [(115, 116, 109, 113), (113, 114, 107, 109),
                               (109, 110, 105, 107), (107, 112, 106, 111)]
                            + [(111, 112, 105.5, 110), (110, resume_close, 108, resume_close),
                               (resume_close, 125, resume_close-1, 124)])
                candles = []
                for i, prices in enumerate(patterns):
                    for offset in (0, 300, 600):
                        stamp = START - 10800 + i * 900 + offset
                        candles.append(dict(
                            time=datetime.fromtimestamp(stamp, timezone.utc).isoformat(),
                            complete=True, mid=dict(zip('ohlc', map(str, prices)))))
                pages = []
                for i, chunk in enumerate((candles[:36], candles[36:])):
                    page = root / f'page{i}.json'
                    page.write_text(json.dumps(dict(instrument='XAU_USD', granularity='M5',
                                                    candles=chunk)), encoding='utf-8')
                    pages.append(page)
                output = root / 'normalized'
                receipt = normalize(pages, output)
                # Advance only the test clock. The strategy, period and exits stay real.
                with patch.object(holdout, 'datetime') as clock:
                    clock.now.return_value = datetime.fromtimestamp(holdout.END, timezone.utc)
                    report = holdout.run(output / 'xauusd_m5_mid.csv', receipt['csv_sha256'],
                                         output / 'source_receipt.json')
                self.assertEqual(report['wait_states'], {'RESUMED': 1})
                self.assertEqual(report['source_audit']['observed_slots'], 9)
                immediate = report['immediate']['records']
                delayed = report['delayed']['records']
                filtered = report['delayed_with_room_gate']['records']
                self.assertEqual(len(immediate), 1)
                self.assertEqual(len(delayed), 1)
                self.assertEqual(immediate[0]['candidate_id'], delayed[0]['candidate_id'])
                self.assertEqual(immediate[0]['state'], 'TARGET_REFERENCE')
                self.assertEqual(delayed[0]['state'], 'TARGET_REFERENCE')
                self.assertEqual(filtered, delayed if should_pass else [])
                self.assertIsNone(report['account_return_pct'])
