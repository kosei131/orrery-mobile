import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

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
