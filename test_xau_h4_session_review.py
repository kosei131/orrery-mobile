import unittest
from orrery_xau_h4_session_review import review
from test_lsr05_session_clock import evidence,iso,BASE

class PublicH4ReviewTests(unittest.TestCase):
    def run_case(self,parts=None,candidate_minutes=3360,omit=False,published=None):
        cal=evidence(parts or [(0,3360,'OPEN')])['calendar']
        bars=[dict(close_time=int(BASE.timestamp())+m*60,open=100.,high=101.,low=99.,close=100.)
              for m in range(240,3361,240)]
        if omit:bars.pop(3)
        return review(bars,[dict(first_poi_touch_close=int(BASE.timestamp())+candidate_minutes*60)],cal,
            published_at=iso(-60) if published is None else published,document_sha256='a'*64)['rows'][0]
    def test_calendar_must_be_preknown(self):
        self.assertEqual(self.run_case(published=iso(3361))['status'],'BLOCKED_CALENDAR_NOT_PREKNOWN')
    def test_real_clocks_selected_without_orders(self):
        r=self.run_case();self.assertEqual(r['status'],'H4_SESSION_PRICE_DIAGNOSTIC_ONLY')
        self.assertEqual(len(r['diagnostic']['rows']),12)
        self.assertFalse(r['diagnostic']['execution_allowed'])
    def test_open_missing_is_retained_as_block(self):
        self.assertEqual(self.run_case(omit=True)['status'],'BLOCKED_SESSION_HISTORY')
    def test_coverage_shortfall_not_filled(self):
        self.assertEqual(self.run_case(parts=[(0,3120,'OPEN')])['status'],'BLOCKED_CALENDAR_COVERAGE')
    def test_future_calendar_intervals_do_not_change_past(self):
        self.assertEqual(self.run_case(),self.run_case(parts=[(0,3360,'OPEN'),(3360,3600,'CLOSED')]))
