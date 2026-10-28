import unittest
from datetime import datetime, timedelta, timezone
from lsr04_tick_quality import audit_ticks, audit_capture
from lsr04_mt5_capture import capture_days
from lsr04_mt5_adaptive import capture_adaptive

START = datetime(2026,10,26,tzinfo=timezone.utc)
END = START+timedelta(seconds=180)
T = int(START.timestamp()*1000)
SPEC = dict(symbol='XAUUSD', point=.01, trade_contract_size=100, digits=2)


def tick(seconds, bid=100, ask=100.1):
    return dict(time_msc=T+seconds*1000,bid=bid,ask=ask)


class Quality(unittest.TestCase):
    def run_audit(self, ticks=None, **kw):
        args = dict(symbol='XAUUSD', start_utc=START, end_utc=END,source='FAKE_TEST',
                    broker_spec=SPEC,max_spread_points=50)
        args.update(kw)
        return audit_ticks([tick(0),tick(60),tick(120)] if ticks is None else ticks,**args)

    def calendar(self,state):
        return [dict(start_utc=START,end_utc=END,state=state)]

    def manifest(self,count):
        return [dict(start_utc=START.isoformat(),end_utc=END.isoformat(),accepted_ticks=count)]

    def test_clean_quotes_still_do_not_certify_completeness(self):
        r=self.run_audit(windows=self.manifest(3),sessions=self.calendar('OPEN'),session_source='TEST_CALENDAR')
        self.assertEqual(r['status'],'REVIEW_TICK_QUALITY')
        self.assertEqual(r['counts']['gap_candidates'],0)
        self.assertFalse(r['completeness_verified'])
        self.assertFalse(r['backtest_ready'])
        self.assertFalse(r['execution_allowed'])
        self.assertEqual(r['spread_points']['mean'],10)

    def test_no_inferred_weekend(self):
        r=self.run_audit([tick(0)])
        self.assertEqual(r['counts']['unknown_session_gaps'],1)
        self.assertEqual(r['counts']['closure_explained_gaps'],0)
        self.assertIn('NO_SESSION_CALENDAR',r['review_reasons'])

    def test_declared_closure_explains_only_covered_interval(self):
        r=self.run_audit([],sessions=self.calendar('CLOSED'),session_source='TEST')
        self.assertEqual(r['counts']['closure_explained_gaps'],1)
        self.assertEqual(r['counts']['unknown_session_gaps'],0)
        self.assertIn('NO_VALID_QUOTES',r['issues'])

    def test_open_silence_is_candidate_not_proven_missing_ticks(self):
        r=self.run_audit([tick(0)],sessions=self.calendar('OPEN'),session_source='TEST')
        self.assertEqual(r['counts']['open_session_gap_candidates'],1)
        self.assertIn('OPEN_SESSION_GAP_CANDIDATES',r['review_reasons'])
        self.assertFalse(r['completeness_verified'])

    def test_partial_calendar_leaves_unknown_duration(self):
        session=[dict(start_utc=START,end_utc=START+timedelta(seconds=90),state='CLOSED')]
        r=self.run_audit([],sessions=session,session_source='TEST')
        self.assertEqual(r['counts']['unknown_session_gaps'],1)
        self.assertEqual(r['counts']['closure_explained_gaps'],0)

    def test_quote_inside_declared_closure_flags_conflict(self):
        r=self.run_audit(sessions=self.calendar('CLOSED'),session_source='TEST')
        self.assertEqual(r['counts']['ticks_in_declared_closure'],3)
        self.assertEqual(r['status'],'BLOCKED_TICK_QUALITY')

    def test_same_millisecond_distinct_and_duplicate_preserved(self):
        rows=[tick(0),tick(0,100.01,100.11),tick(0)]
        r=self.run_audit(rows)
        self.assertEqual(r['counts']['valid_rows'],3)
        self.assertEqual(r['counts']['same_millisecond_distinct_rows'],1)
        self.assertEqual(r['counts']['normalized_duplicate_rows'],1)
        self.assertEqual(len(rows),3)

    def test_unsorted_and_out_of_range_not_sorted_or_clipped_silently(self):
        r=self.run_audit([tick(60),tick(0),tick(-1),tick(180)])
        self.assertEqual(r['counts']['time_reversals'],1)
        self.assertEqual(r['counts']['out_of_range_rows'],2)
        self.assertEqual(r['status'],'BLOCKED_TICK_QUALITY')

    def test_invalid_quote_rows_flagged(self):
        rows=[tick(0,0,1),tick(1,101,100),tick(2,float('nan'),100),dict(time_msc=T+.5,bid=100,ask=101)]
        r=self.run_audit(rows)
        self.assertEqual(r['counts']['invalid_rows'],4)
        self.assertIsNone(r['spread_points']['mean'])

    def test_spread_distribution_and_exact_threshold(self):
        r=self.run_audit([tick(0,100,100.1),tick(1,100,100.5),tick(2,100,100.51)],spread_bin_edges_points=[10,50],max_spread_points=50)
        self.assertEqual(r['spread_points']['bin_counts'],[0,1,2])
        self.assertEqual(r['counts']['excessive_spread_rows'],1)
        self.assertEqual(r['spread_points']['maximum'],51)

    def test_manifest_hole_and_wrong_count_block(self):
        windows=[dict(start=START.isoformat(),end=(START+timedelta(seconds=60)).isoformat(),count=99)]
        r=self.run_audit(windows=windows)
        self.assertEqual(r['manifest_hole_count'],1)
        self.assertEqual(r['manifest_count_mismatches'],1)
        self.assertEqual(r['counts']['ticks_outside_manifest'],2)

    def test_adjacent_window_boundary_owned_once(self):
        mid=START+timedelta(seconds=60)
        windows=[dict(start=START,end=mid,count=1),dict(start=mid,end=END,count=2)]
        r=self.run_audit(windows=windows)
        self.assertEqual(r['manifest_count_mismatches'],0)
        self.assertEqual(r['manifest_hole_count'],0)

    def test_saturated_window_remains_blocked(self):
        manifest=self.manifest(3);manifest[0]['at_safety_limit']=True
        self.assertIn('SATURATED_WINDOWS',self.run_audit(windows=manifest)['issues'])

    def test_calendar_overlap_or_missing_provenance_rejected(self):
        with self.assertRaises(ValueError):self.run_audit(sessions=self.calendar('OPEN'))
        with self.assertRaises(ValueError):self.run_audit(sessions=self.calendar('OPEN')*2,session_source='TEST')

    def test_resource_limit_never_certifies_prefix(self):
        with self.assertRaises(ValueError):self.run_audit(max_ticks=1)
        r=self.run_audit([tick(0),tick(100)],max_examples=0)
        self.assertEqual(r['examples'],[])
        self.assertGreater(r['counts']['gap_candidates'],0)

    def test_hash_and_configuration_are_reproducible(self):
        a=self.run_audit();b=self.run_audit()
        self.assertEqual(a['normalized_quote_sha256'],b['normalized_quote_sha256'])
        self.assertEqual(a['audit_config_sha256'],b['audit_config_sha256'])
        c=self.run_audit(max_gap_seconds=10)
        self.assertEqual(a['normalized_quote_sha256'],c['normalized_quote_sha256'])
        self.assertNotEqual(a['audit_config_sha256'],c['audit_config_sha256'])

    def test_stream_input_and_symbol_separation(self):
        spec=dict(SPEC,symbol='USDJPY',point=.001,digits=3)
        r=self.run_audit((row for row in [tick(0,150,150.01)]),symbol='USDJPY',broker_spec=spec)
        self.assertEqual(r['symbol'],'USDJPY')
        self.assertEqual(r['spread_points']['mean'],10)

    def test_bad_time_or_spec_rejected(self):
        for kw in (dict(start_utc=START.replace(tzinfo=None)),dict(broker_spec={}),dict(start_utc=START+timedelta(microseconds=1))):
            with self.assertRaises(ValueError):self.run_audit(**kw)

    def test_existing_capture_manifest_formats(self):
        class MT5:
            ACCOUNT_TRADE_MODE_DEMO=0
            COPY_TICKS_ALL=0
            def account_info(self):
                from types import SimpleNamespace
                return SimpleNamespace(trade_mode=0)
            def symbol_info(self,symbol):
                from types import SimpleNamespace
                return SimpleNamespace(trade_contract_size=100)
            def copy_ticks_range(self,symbol,start,end,flags):
                return [row for row in [tick(0),tick(60),tick(120),tick(180)] if start.timestamp()*1000 <= row['time_msc'] <= end.timestamp()*1000]
        for capture in (capture_days(MT5(),symbol='XAUUSD',start_utc=START,end_utc=END),
                        capture_adaptive(MT5(),symbol='XAUUSD',start_utc=START,end_utc=END)):
            r=audit_capture(capture,start_utc=START,end_utc=END,source='FAKE_TEST',broker_spec=SPEC,max_spread_points=50)
            self.assertEqual(r['counts']['valid_rows'],3)
            self.assertEqual(r['manifest_count_mismatches'],0)
            self.assertFalse(r['backtest_ready'])


if __name__=='__main__':unittest.main()
