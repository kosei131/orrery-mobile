from datetime import datetime, timezone, timedelta
import unittest
from unittest.mock import patch
from orrery_prospective_status import PLAN, PLAN_SHA256, acquisition_status

class StatusTests(unittest.TestCase):
    def status(self, text):
        return acquisition_status(PLAN.read_bytes(), plan_sha256=PLAN_SHA256,
                                  now=datetime.fromisoformat(text))
    def test_before_start_has_no_cutoff_or_counts(self):
        r=self.status('2026-11-02T23:59:59+00:00')
        self.assertEqual(r['phase'],'NOT_STARTED')
        self.assertIsNone(r['closed_bar_cutoff_upper_bound_utc'])
        self.assertTrue(all(v['latest_possible_nominal_open_utc'] is None for v in r['frames'].values()))
        self.assertIsNone(r['prospective_candidates']); self.assertFalse(r['data_acquired'])
    def test_first_h4_cannot_be_requested_before_nominal_close(self):
        r=self.status('2026-11-03T03:59:59+00:00')
        self.assertIsNone(r['frames']['4H']['latest_possible_nominal_open_utc'])
        r=self.status('2026-11-03T04:00:00+00:00')
        self.assertEqual(r['frames']['4H']['latest_possible_nominal_open_utc'],'2026-11-03T00:00:00Z')
    def test_mid_period_not_rounded_to_unverified_grid(self):
        r=self.status('2026-11-03T05:07:00+00:00')
        self.assertEqual(r['frames']['4H']['latest_possible_nominal_open_utc'],'2026-11-03T01:07:00Z')
        self.assertEqual(r['phase'],'IN_PROGRESS');self.assertFalse(r['frames']['4H']['feed_grid_verified'])
        self.assertEqual(r['start_hst'],'2026-11-02T14:00:00-10:00')
    def test_after_end_is_capped_without_claiming_data(self):
        r=self.status('2027-01-01T00:00:00+00:00')
        self.assertEqual(r['phase'],'ENDED');self.assertEqual(r['elapsed_calendar_seconds'],28*86400)
        self.assertEqual(r['closed_bar_cutoff_upper_bound_utc'],'2026-12-01T00:00:00Z')
        self.assertFalse(r['complete_session_coverage_verified']);self.assertFalse(r['execution_allowed'])
        self.assertIsNone(r['net_expectancy_r'])
    def test_timezone_equivalence_and_naive_rejection(self):
        a=self.status('2026-11-03T04:00:00+00:00');b=self.status('2026-11-02T18:00:00-10:00')
        self.assertEqual(a,b)
        with self.assertRaises(ValueError):self.status('2026-11-03T04:00:00')
    def test_dashboard_refreshes_clock_without_mutating_archive(self):
        import mt5_local_dashboard as d
        from orrery_prospective_status import current_status
        r=self.status('2026-11-03T04:00:00+00:00')
        original={'status':'PUBLIC_HISTORY_RESEARCH'}
        with patch.object(d,'HISTORY_SNAPSHOT',original), patch('orrery_prospective_status.current_status',return_value=r):
            self.assertEqual(d.snapshot()['prospective_readiness'],r)
        self.assertNotIn('prospective_readiness',original)

if __name__=='__main__':unittest.main()
