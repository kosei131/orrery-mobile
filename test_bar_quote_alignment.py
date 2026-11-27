import unittest

from orrery_bar_quote_alignment import audit_session


class BarQuoteAlignmentTest(unittest.TestCase):
    def run_audit(self, *, omit_m5=False, wrong_h4=False, omit_quote=False):
        settings = dict(symbol='XAUUSD', data_source='fixture', chart_type='STANDARD',
                        price_basis='MID', as_of_s=14400, time_format='UNIX_SECONDS',
                        column_map={k: k for k in ('time', 'open', 'high', 'low', 'close')})
        csvs = {}
        for frame, step in [('M5', 300), ('M15', 900), ('H4', 14400)]:
            rows = ['time,open,high,low,close']
            for at in range(0, 14400, step):
                if frame == 'M5' and omit_m5 and at == 0:
                    continue
                close = 101 if frame == 'H4' and wrong_h4 else 100
                rows.append(f'{at},101,101,100,{close}')
            csvs[frame] = '\n'.join(rows).encode()
        quotes = (dict(time_msc=at * 1000, bid=100 if at % 300 == 0 else 99,
                       ask=102 if at % 300 == 0 else 101)
                  for at in range(0, 14400, 60) if not (omit_quote and at == 60))
        return audit_session(csvs, settings, quotes, start_s=0, end_s=14400,
                             max_gap_msc=60000, quote_symbol='XAUUSD',
                             quote_source='fixture', price_tolerance=0)

    def test_half_open_bar_edges_and_mid_ohlc(self):
        result = self.run_audit()
        self.assertTrue(result['aligned'])
        self.assertEqual(result['frames']['M5']['expected'], 48)
        self.assertFalse(result['feed_identity_verified'])

    def test_missing_first_bar_and_wrong_h4(self):
        result = self.run_audit(omit_m5=True, wrong_h4=True)
        self.assertFalse(result['aligned'])
        self.assertEqual(result['frames']['M5']['missing_bars'], 1)
        self.assertEqual(result['frames']['H4']['mismatched_bars'], 1)

    def test_gap_blocks_even_when_ohlc_matches(self):
        result = self.run_audit(omit_quote=True)
        self.assertFalse(result['aligned'])
        self.assertEqual(result['first_gap_msc'], (0, 120000))
        self.assertEqual(result['frames']['H4']['mismatched_bars'], 0)
