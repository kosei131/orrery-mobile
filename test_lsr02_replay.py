import unittest
from lsr02_replay import replay
from test_lsr02_structure import bars

class ReplayTests(unittest.TestCase):
    def test_empty_and_no_ready(self):
        self.assertEqual(replay('XAUUSD',[],[],[],as_of=0,buffer=1),[])
        data=bars([(10,8,9)]*8)
        self.assertEqual(replay('XAUUSD',[],[],data,as_of=2400,buffer=1),[])
    def test_reject_gaps_unfinished_and_bad_settings(self):
        data=bars([(10,8,9)]*3)
        with self.assertRaises(ValueError):replay('XAUUSD',[],[],data,as_of=300,buffer=1)
        with self.assertRaises(ValueError):replay('XAUUSD',[],[],data[::2],as_of=900,buffer=1)
        with self.assertRaises(ValueError):replay('XAUUSD',[],[],[],as_of=0,buffer=0)
    def test_real_detection_prefix_and_sweep_stop(self):
        h=bars([(10,8,9),(12,9,11),(11,7,8),(14,10,13),(13,9,10),(16,12,15),(15,11,14)])
        for i,b in enumerate(h):b['close_time']=(i+1)*14400
        start=100800
        f=bars([(14,12,13),(15,11,12),(14,12,13),(13,10,12),(14,11,13)])
        for i,b in enumerate(f):b['close_time']=start+i*900
        m=bars([(14,11,13)]*13)
        for i,b in enumerate(m):b['close_time']=start+i*300
        result=replay('XAUUSD',h,f,m,as_of=m[-1]['close_time'],buffer=.1,left=1,right=1)
        self.assertTrue(result)
        self.assertEqual(result[0]['side'],'BUY')
        self.assertAlmostEqual(result[0]['stop'],9.9)
        self.assertNotIn('READY',[e['state'] for e in result])
        for n in range(1,len(m)+1):
            t=m[n-1]['close_time']
            short=replay('XAUUSD',[b for b in h if b['close_time']<=t],[b for b in f if b['close_time']<=t],m[:n],as_of=t,buffer=.1,left=1,right=1)
            self.assertEqual(short,[e for e in result if e['at']<=t])

class ReplayDiagnosticTests(unittest.TestCase):
    def fixture(self,sell=False):
        from test_lsr02_paths import fixture
        return fixture(sell)

    def run_replay(self,h,m,f,**extra):
        return replay('XAUUSD',h,m,f,as_of=f[-1]['close_time'],buffer=.1,
                      left=1,right=1,**extra)

    def test_diagnostics_preserve_buy_and_sell_traces_and_count_transitions_once(self):
        for sell in (False,True):
            h,m,f=self.fixture(sell);d={}
            expected=self.run_replay(h,m,f,lifetime=6000)
            self.assertEqual(expected,self.run_replay(h,m,f,lifetime=6000,diagnostics=d))
            self.assertEqual(d['candidate_transitions'],{'SWEEP':1,'CONFIRM':1,'RETEST':1})
            self.assertEqual(d['m15_sweep_events'],1)
            self.assertEqual(sum(d['sweep_dispositions'].values()),1)
            self.assertEqual(sum(d['h4_states'].values()),len(f))

    def test_flat_h4_counts_direction_gate_without_promoting_candidate(self):
        h,m,f=self.fixture()
        for b in h:b.update(open=12,close=12,low=11,high=13)
        d={};self.assertEqual(self.run_replay(h,m,f,diagnostics=d),[])
        self.assertEqual(d['h4_states'],{'RANGE':len(f)})
        self.assertEqual(d['h4_context_reasons'],{'INSUFFICIENT_CONFIRMED_PIVOTS':len(f)})
        self.assertEqual(d['sweep_dispositions'],{'HTF_RANGE':1})

    def test_missing_h4_remains_missing(self):
        h,m,f=self.fixture();d={}
        self.assertEqual(self.run_replay([],m,f,diagnostics=d),[])
        self.assertEqual(d['h4_states'],{'MISSING':len(f)})
        self.assertEqual(d['sweep_dispositions'],{'HTF_STALE_OR_MISSING':1})

    def test_expiration_is_counted_once_not_as_repeated_invalid_rows(self):
        h,m,f=self.fixture();d={}
        self.run_replay(h,m,f,lifetime=2400,diagnostics=d)
        self.assertEqual(d['invalidation_reasons'],{'EXPIRED':1})
        self.assertEqual(d['invalidation_from_states'],{'CONFIRM':1})
        self.assertNotIn('RETEST',d['candidate_transitions'])

    def test_filled_diagnostic_sink_rejected_and_kept(self):
        h,m,f=self.fixture();d={'keep':True}
        with self.assertRaisesRegex(ValueError,'Empty diagnostic'):
            self.run_replay(h,m,f,diagnostics=d)
        self.assertEqual(d,{'keep':True})

class H4ContextDiagnosticTests(unittest.TestCase):
    fixture=ReplayDiagnosticTests.fixture
    run_replay=ReplayDiagnosticTests.run_replay
    # Reuse the same fixtures; these are diagnostics, not new trend rules.
    def test_short_context_is_pivot_shortage_not_established_range(self):
        h,m,f=self.fixture();d={}
        self.run_replay(h[-2:],m,f,diagnostics=d)
        self.assertEqual(d['h4_context_reasons'],{'INSUFFICIENT_CONFIRMED_PIVOTS':len(f)})
        self.assertEqual(d['h4_context_bars'],{'2':len(f)})
        self.assertEqual(d['h4_sweep_context_reasons'],{'INSUFFICIENT_CONFIRMED_PIVOTS':1})

    def test_confirmed_conflicting_structure_is_distinct(self):
        h,m,f=self.fixture();h[4]['low']=6;h[6]['low']=5;d={}
        self.assertEqual(self.run_replay(h,m,f,diagnostics=d),[])
        self.assertEqual(d['h4_context_reasons'],{'NON_DIRECTIONAL_CONFIRMED_STRUCTURE':len(f)})
        self.assertEqual(d['h4_reason_by_bars'],{'NON_DIRECTIONAL_CONFIRMED_STRUCTURE:7':len(f)})

    def test_directional_structure_counts_use_current_confirmed_context(self):
        h,m,f=self.fixture();d={}
        expected=self.run_replay(h,m,f)
        self.assertEqual(self.run_replay(h,m,f,diagnostics=d),expected)
        self.assertEqual(d['h4_context_reasons'],{'UP':len(f)})
        self.assertEqual(d['h4_sweep_context_reasons'],{'UP':1})

if __name__=='__main__':unittest.main()
