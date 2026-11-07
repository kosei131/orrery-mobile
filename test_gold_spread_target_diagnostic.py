import json
from pathlib import Path
import unittest

from orrery_gold_spread_target_diagnostic import summarize, PINNED_ZIP_SHA256


AUDIT=Path(__file__).parent/'research_evidence/local-history-20261101/gold_histdata_tick_audit_20261103.json'


class GoldSpreadTargetTests(unittest.TestCase):
    def load(self):
        return json.loads(AUDIT.read_text(encoding='utf-8'))

    def test_real_archived_quote_spread_comparison_is_not_trading_return(self):
        r=summarize(self.load())
        self.assertEqual(r['source_ticks'],6446239)
        self.assertEqual(len(r['hours']),24)
        self.assertEqual(len(r['targets']),4)
        self.assertAlmostEqual(r['targets'][0]['gross_target_price_distance'],0.3)
        self.assertAlmostEqual(r['targets'][0]['all_ticks_median_spread_to_target'],1.8)
        self.assertAlmostEqual(r['targets'][1]['all_ticks_p95_spread_to_target'],0.7/0.6)
        self.assertAlmostEqual(r['targets'][2]['all_ticks_median_spread_to_target'],0.54/1.5)
        self.assertIn(22,r['targets'][2]['utc_hours_where_p95_spread_exceeds_gross_target'])
        self.assertEqual(r['targets'][0]['hourly_median_at_or_above_target'],list(range(24)))
        self.assertEqual(r['targets'][1]['hourly_median_at_or_above_target'],[22,23])
        self.assertEqual(r['targets'][2]['hourly_p95_at_or_above_target'],[22])
        self.assertEqual(r['targets'][3]['hourly_p95_at_or_above_target'],[])
        self.assertEqual(r['targets'][1]['hourly_p95_below_target'],[8,9,10,11,12])
        self.assertTrue(r['targets'][1]['quote_weighted_hour_coverage_not_trade_coverage'])
        self.assertIsNone(r['actual_win_rate_pct'])
        self.assertIsNone(r['net_expectancy_r'])
        self.assertIsNone(r['actual_profit_usd'])
        self.assertFalse(r['execution_allowed'])
        self.assertFalse(r['execution_chronology_verified'])
        self.assertTrue(r['spread_not_additive_if_already_in_bid_ask_fills'])

    def test_bad_zip_pin_or_fake_bar_export_rejected(self):
        a=self.load()
        a['original_zip_sha256']='0'*64
        with self.assertRaises(ValueError):summarize(a)
        a['original_zip_sha256']=PINNED_ZIP_SHA256
        a['chronological_bar_exported']=True
        with self.assertRaises(ValueError):summarize(a)

    def test_missing_hour_and_mutated_count_rejected(self):
        a=self.load()
        del a['spread_by_declared_utc_hour']['22']
        with self.assertRaises(ValueError):summarize(a)
        a=self.load()
        a['spread_by_declared_utc_hour']['22']['ticks']+=1
        with self.assertRaises(ValueError):summarize(a)

    def test_invalid_targets_rejected(self):
        a=self.load()
        for target in (0,-1,float('nan')):
            with self.subTest(target=target),self.assertRaises(ValueError):
                summarize(a,target_rs=[target])


if __name__=='__main__':
    unittest.main()
