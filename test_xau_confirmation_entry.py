import unittest
from orrery_public_xau_sequence_study import observe_retest
from orrery_xau_confirmation_entry_comparison import entry_plans
from orrery_xau_h4_alignment import START
from orrery_xau_structural_stop_comparison import stop_specs

C=START+3600
def candidate(confirm=C,poi=True):
    return dict(sweep_close=confirm-600,confirmation_close=confirm,side='BUY',
                poi={'low':99,'high':101} if poi else None)
def bar(at,touch=False):
    return dict(close_time=at,low=100 if touch else 105,high=102 if touch else 106)
def ident(c):return (c['sweep_close'],c['confirmation_close'],c['side'])

class ConfirmationEntryTests(unittest.TestCase):
    def test_immediate_uses_all_confirmations_without_reading_future_observations(self):
        cs=[candidate(),candidate(C+600,poi=False)]
        class Poison:
            def __getitem__(self,key):raise AssertionError('Future observation read')
        plans,skips=entry_plans(cs,mode='CONFIRMATION',observations=Poison())
        self.assertEqual(len(plans),2)
        self.assertEqual(skips,[])
        self.assertEqual(plans[0]['first_poi_touch_close'],C)

    def test_waiting_does_not_create_trade_for_no_poi_or_expiry(self):
        cs=[candidate(),candidate(C+600,poi=False)]
        obs={ident(cs[0]):dict(status='EXPIRED',entry_at=None),
             ident(cs[1]):dict(status='NO_POI',entry_at=None)}
        plans,skips=entry_plans(cs,mode='RETEST',observations=obs)
        self.assertEqual(plans,[])
        self.assertEqual([s['reason'] for s in skips],['EXPIRED','NO_POI'])

    def test_first_touch_survives_later_gap_and_future_append(self):
        c=candidate();early=[bar(C+300,True)]
        a=observe_retest(c,early)
        self.assertEqual(a['entry_at'],C+300)
        self.assertEqual(a,observe_retest(c,early+[bar(C+900)]))

    def test_gap_before_touch_is_unknown_not_future_fill(self):
        r=observe_retest(candidate(),[bar(C+300),bar(C+900,True)])
        self.assertEqual(r['status'],'UNKNOWN_HISTORY')
        self.assertIsNone(r['entry_at'])

    def test_complete_no_touch_expires_truncated_history_is_unknown(self):
        rows=[bar(C+n*300) for n in range(1,13)]
        self.assertEqual(observe_retest(candidate(),rows)['status'],'EXPIRED')
        self.assertEqual(observe_retest(candidate(),rows[:-1])['status'],'UNKNOWN_HISTORY')
        self.assertEqual(observe_retest(candidate(poi=False),[])['status'],'NO_POI')

    def test_confirmation_entry_structural_stop_uses_only_prior_m1(self):
        c=candidate();plans,_=entry_plans([c],mode='CONFIRMATION')
        h=[dict(close_time=C-600,low=90,high=110)]
        prior=[dict(at=t,low=99,high=101) for t in range(C-600,C,60)]
        a=stop_specs(plans,h,prior,spread=.6)
        b=stop_specs(plans,h,prior+[dict(at=C,low=1,high=500)],spread=.6)
        self.assertEqual(a,b)
        self.assertIsNone(a[(C,'BUY')]['blocked_reason'])

    def test_invalid_retest_time_and_duplicate_confirmation_rejected(self):
        c=candidate()
        with self.assertRaises(ValueError):entry_plans([c,c],mode='CONFIRMATION')
        with self.assertRaises(ValueError):
            entry_plans([c],mode='RETEST',observations={ident(c):dict(status='RETEST',entry_at=C)})

if __name__=='__main__':unittest.main()
