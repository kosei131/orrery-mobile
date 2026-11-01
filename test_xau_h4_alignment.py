import unittest
from orrery_xau_h4_alignment import annotate, summarize
from lsr02_regime import classify
from test_lsr02_structure import bars

CONFIG=dict(lookback=7,trend_efficiency=.3,range_efficiency=.2,left=1,right=1)

def history():
    b=bars([(10,8,9),(12,9,11),(11,7,8),(14,10,13),(13,9,10),(16,12,15),(15,11,15)])
    return [dict(x,close_time=(i+1)*14400) for i,x in enumerate(b)]

def candidate(t,side='BUY'):
    return {'first_poi_touch_close':t,'side':side}

class H4AlignmentTests(unittest.TestCase):
    def test_alignment_and_opposition_at_exact_confirmed_close(self):
        h=history(); t=h[-1]['close_time']
        r=annotate(h,[candidate(t),candidate(t,'SELL')],config=CONFIG)
        self.assertEqual([x['group'] for x in r],['ALIGNED','OPPOSED'])
        self.assertEqual(r[0]['h4_last_close'],t)
        self.assertFalse(r[0]['execution_allowed'])

    def test_future_bar_append_does_not_change_past_annotation(self):
        h=history();t=h[-1]['close_time']
        a=annotate(h,[candidate(t)],config=CONFIG)
        h.append(dict(h[-1],close_time=t+14400,open=1,close=1,low=1,high=1))
        self.assertEqual(a,annotate(h,[candidate(t)],config=CONFIG))
        r=annotate(h,[candidate(t-1)],config=CONFIG)[0]
        self.assertLessEqual(r['h4_last_close'],t-1)
        self.assertEqual(r['group'],'UNKNOWN')

    def test_stale_missing_and_empty_remain_unknown(self):
        h=history();t=h[-1]['close_time']
        for records,at in [(h,t+14400),(h[:3]+h[4:],t),([],t)]:
            with self.subTest(records=records):
                self.assertEqual(annotate(records,[candidate(at)],config=CONFIG)[0]['group'],'UNKNOWN')

    def test_history_diagnostic_empty_and_short(self):
        for h in ([],history()[:3]):
            d=annotate(h,[candidate(100800)],config=CONFIG)[0]['history_diagnostic']
            self.assertEqual(d['minimum_additional_bars'],7-len(h))
            self.assertEqual(d['available_total_asof'],len(h))
            self.assertFalse(d['bar_count_sufficient'])
            self.assertFalse(d['market_session_verified'])
        self.assertIsNone(annotate([],[candidate(100800)],config=CONFIG)[0]
                          ['history_diagnostic']['latest_age_seconds'])

    def test_gap_diagnostic_does_not_bridge_or_use_future(self):
        h=history(); t=h[-1]['close_time']; h=h[:3]+h[4:]
        d=annotate(h,[candidate(t)],config=CONFIG)[0]['history_diagnostic']
        self.assertEqual(d['preceding_gap_seconds'],28800)
        self.assertEqual(d['minimum_additional_bars'],4)
        self.assertEqual(d['used_first_close'],72000)
        self.assertEqual(d['latest_age_seconds'],0)

    def test_count_sufficient_is_not_strategy_approval(self):
        h=history();t=h[-1]['close_time']+14400
        row=annotate(h,[candidate(t)],config=CONFIG)[0]
        self.assertTrue(row['history_diagnostic']['bar_count_sufficient'])
        self.assertEqual(row['group'],'UNKNOWN')
        self.assertFalse(row['execution_allowed'])

    def test_duplicate_bad_side_or_clock_rejected(self):
        t=history()[-1]['close_time']
        for c in ([candidate(t),candidate(t)], [candidate(t,'INVALID')], [candidate(True)]):
            with self.subTest(c=c),self.assertRaises(ValueError):
                annotate(history(),c,config=CONFIG)

    def test_unresolved_not_silently_zero_or_win(self):
        t=history()[-1]['close_time']
        a=annotate(history(),[candidate(t),candidate(t,'SELL')],config=CONFIG)
        s=summarize(a,[{'touch_close_utc':t,'side':'BUY','r':-1}])
        self.assertEqual(s['ALL']['candidates'],2)
        self.assertEqual(s['ALL']['unresolved_or_unmodeled'],1)
        self.assertEqual(s['ALL']['mean_r'],-1)
        self.assertIsNone(s['OPPOSED']['win_rate_pct'])
        self.assertIsNone(s['OPPOSED']['total_r'])

    def test_outcomes_cannot_change_annotation(self):
        h=history();t=h[-1]['close_time']
        c=candidate(t)
        self.assertEqual(annotate(h,[c],config=CONFIG),annotate(h,[dict(c,r=500)],config=CONFIG))

class StructureScopeTests(unittest.TestCase):
    def expanded_history(self):
        h=history()
        for n in range(7):
            p=15.2+.2*n
            h.append(dict(close_time=h[-1]['close_time']+14400,
                          open=p,close=p,high=p+.1,low=p-.1))
        return h

    def test_scope_preserves_efficiency_atr_and_band_but_keeps_older_pivots(self):
        h=self.expanded_history();t=h[-1]['close_time']
        kwargs=dict(as_of=t,interval=14400,**CONFIG)
        old=classify(h,**kwargs)
        self.assertEqual(old,classify(h,structure_scope='WINDOW',**kwargs))
        full=classify(h,structure_scope='CONTIGUOUS_HISTORY',**kwargs)
        self.assertEqual(old['reason'],'INSUFFICIENT_CONFIRMED_SWINGS')
        self.assertEqual(full['regime'],'UP')
        for key in ('efficiency','atr_sma','band'):
            self.assertEqual(old[key],full[key])
        self.assertFalse(full['execution_allowed'])

    def test_full_history_mode_does_not_read_future_or_bridge_gap(self):
        h=self.expanded_history();t=h[-1]['close_time']
        a=annotate(h,[candidate(t)],config=CONFIG,full_structure_history=True)
        self.assertEqual(a[0]['group'],'ALIGNED')
        self.assertEqual(a[0]['h4_bars_used'],14)
        future=dict(h[-1],close_time=t+14400)
        self.assertEqual(a,annotate(h+[future],[candidate(t)],config=CONFIG,full_structure_history=True))
        gapped=h[:6]+h[7:]
        r=annotate(gapped,[candidate(t)],config=CONFIG,full_structure_history=True)[0]
        self.assertEqual(r['h4_bars_used'],7)
        self.assertEqual(r['group'],'UNKNOWN')

    def test_invalid_structure_scope_rejected_even_without_history(self):
        with self.assertRaises(ValueError):
            classify([],as_of=0,interval=14400,structure_scope='AUTO',**CONFIG)
        with self.assertRaises(ValueError):
            annotate([],[],config=CONFIG,full_structure_history='yes')

if __name__=='__main__':unittest.main()
