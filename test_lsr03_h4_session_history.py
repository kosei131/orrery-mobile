from copy import deepcopy
import unittest
from test_lsr05_session_clock import evidence, BASE
from lsr05_session_clock import evidence_sha256
from lsr03_h4_session_history import select_history

class H4SessionHistoryTests(unittest.TestCase):
    def setUp(self):
        self.ev=evidence([(0,480,'OPEN'),(480,3360,'CLOSED'),(3360,3840,'OPEN')])
        self.times=[int(BASE.timestamp())+m*60 for m in (240,480,3600,3840)]
    def run_case(self,times=None,ev=None,as_of=None):
        ev=self.ev if ev is None else ev
        return select_history(self.times if times is None else times,
            as_of=self.times[-1] if as_of is None else as_of,minimum_bars=3,
            symbol='XAUUSD',data_source='SYNTHETIC',evidence=ev,
            expected_evidence_sha256=evidence_sha256(ev))
    def test_explicit_closure_keeps_actual_times(self):
        r=self.run_case()
        self.assertEqual(r['selected_close_times'],self.times[-3:])
        self.assertEqual(r['status'],'H4_SESSION_CLOCK_SELECTION_ONLY')
        self.assertFalse(r['regime_evaluated']);self.assertFalse(r['execution_allowed'])
    def test_missing_open_bar_blocks_all_selection(self):
        r=self.run_case(self.times[1:])
        self.assertEqual(r['status'],'BLOCKED_SESSION_HISTORY')
        self.assertEqual(r['selected_close_times'],[])
    def test_quotes_during_closure_block(self):
        r=self.run_case(self.times[:2]+[self.times[1]+14400]+self.times[2:])
        self.assertEqual(r['status'],'BLOCKED_SESSION_HISTORY')
    def test_unknown_calendar_is_rejected(self):
        e=deepcopy(self.ev);e['calendar']['intervals'][1]['state']='UNKNOWN'
        with self.assertRaises(ValueError):self.run_case(ev=e)
    def test_old_calendar_cannot_authorize_future(self):
        r=self.run_case(as_of=self.times[-1]+14400)
        self.assertEqual(r['status'],'BLOCKED_CALENDAR_HORIZON')
    def test_future_bar_is_rejected(self):
        with self.assertRaises(ValueError):self.run_case(as_of=self.times[-1]-1)
    def test_wrong_feed_or_late_calendar_rejected(self):
        for key,value in [('data_source','OTHER'),('known_at_utc','2026-10-27T00:00:00+00:00')]:
            with self.assertRaises(ValueError):self.run_case(ev=dict(self.ev,**{key:value}))

class H4PriceTests(unittest.TestCase):
    setUp=H4SessionHistoryTests.setUp
    def prices(self):
        return [dict(close_time=t,open=p,high=p+1,low=p-1,close=p)
                for t,p in zip(self.times,[100.,100.,110.,110.])]
    def inspect(self,bars):
        from lsr03_h4_session_history import inspect_prices
        return inspect_prices(bars,as_of=self.times[-1],minimum_bars=4,
            symbol='XAUUSD',data_source='SYNTHETIC',evidence=self.ev,
            expected_evidence_sha256=evidence_sha256(self.ev))
    def test_reopening_gap_retained_and_structure_resets(self):
        r=self.inspect(self.prices())
        self.assertEqual(r['rows'][2]['true_range'],11.)
        self.assertEqual(r['rows'][2]['opening_price_gap'],10.)
        self.assertTrue(r['rows'][2]['follows_session_gap'])
        self.assertEqual([s['bars'] for s in r['segmented_structure']],[2,2])
        self.assertFalse(r['execution_allowed'])
    def test_missing_open_bar_blocks_price_results(self):
        r=self.inspect(self.prices()[1:])
        self.assertEqual(r['rows'],[]);self.assertEqual(r['segmented_structure'],[])
    def test_bad_price_rejected_even_before_selected_window(self):
        for value in (float('nan'),True,-1.):
            b=self.prices();b[0]['low']=value
            with self.assertRaises(ValueError):self.inspect(b)
    def test_input_not_rewritten(self):
        b=self.prices();before=deepcopy(b);self.inspect(b);self.assertEqual(b,before)
