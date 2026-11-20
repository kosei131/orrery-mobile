import math
import unittest
from datetime import datetime, timezone
from orrery_dashboard_analysis import analyze


class AnalysisTests(unittest.TestCase):
    def fixture(self):
        bars = []
        for i in range(100):
            price = 100 + 4 * math.sin(i / 3)
            bars.append(dict(time=i*300, open=price, high=price+1, low=price-1, close=price))
        return dict(status='READ_ONLY_DEMO',
                    checked_at_utc=datetime.fromtimestamp(30000, timezone.utc).isoformat(),
                    charts=[dict(symbol='XAUUSD', timeframe='5m',
                                 status='CLOSED_BARS_AVAILABLE', bars=bars)])

    def test_levels_indicators_and_review_scenarios_share_snapshot(self):
        result = analyze(self.fixture(), 30000)
        chart = result['charts'][0]
        self.assertEqual(chart['status'], 'RESEARCH_LEVELS_ONLY')
        self.assertTrue(chart['levels'])
        self.assertIsNotNone(chart['indicators']['atr'])
        self.assertEqual(len(chart['reference_plans']), 2)
        for plan in chart['reference_plans']:
            self.assertGreater(plan['gross_reward_risk'], 0)
            self.assertFalse(plan['execution_allowed'])
        self.assertIsNone(result['expected_net_r'])
        self.assertIsNone(result['account_sl_risk'])

    def test_stale_gapped_and_unavailable_never_produce_plans(self):
        for mode in ('stale', 'gap', 'unavailable'):
            source = self.fixture()
            if mode == 'gap':
                source['charts'][0]['bars'].pop(50)
            if mode == 'unavailable':
                source['charts'][0]['status'] = 'STALE'
            result = analyze(source, 30006 if mode == 'stale' else 30000)
            self.assertEqual(result['charts'][0]['status'], 'UNAVAILABLE')
            self.assertEqual(result['charts'][0]['reference_plans'], [])

    def test_simulation_and_real_payload_cannot_be_promoted(self):
        for status in ('SIMULATED_TEST_DATA', 'REAL', None):
            source = self.fixture()
            source['status'] = status
            self.assertEqual(analyze(source, 30000)['charts'], [])


if __name__ == '__main__':
    unittest.main()
