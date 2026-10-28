import unittest
from orrery_xau_h4_alignment import annotate, summarize
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

if __name__=='__main__':unittest.main()
