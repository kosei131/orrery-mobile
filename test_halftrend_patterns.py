from copy import deepcopy
import unittest
from orrery_halftrend_patterns import walk,scan,sequence


def bar(i,o=100,h=101,l=99,c=100):
    return dict(open_time=i*300,close_time=(i+1)*300,open=o,high=h,low=l,close=c)
def state(b,line,side='DOWN',signal=None):
    return dict(at=b['close_time'],ready=True,state=side,line=line,atr=2,
                signal=signal,signal_known_at=b['close_time'] if signal else None)
def pullback():
    b=[bar(i) for i in range(3)]+[bar(3,102,103.2,101.8,102.8),bar(4,102.7,102.8,101.4,101.6)]
    h=[state(x,line) for x,line in zip(b,[105,104.5,104,103.5,103])]
    return b,h


class PatternTests(unittest.TestCase):
    def test_pullback_needs_later_close_and_preserves_anchor(self):
        b,h=pullback();early,_=walk(b[:4],h[:4]);full,_=walk(b,h)
        self.assertEqual(early,[]);self.assertEqual(len(full),1)
        c=full[0];self.assertEqual(c['family'],'PULLBACK_RESUME');self.assertEqual(c['side'],'SELL')
        self.assertEqual(c['anchor_known_at'],1200);self.assertEqual(c['entry_at'],1500)
        self.assertAlmostEqual(c['distance_atr'],.7)
    def test_anchor_breach_prevents_optimistic_same_bar_breakout(self):
        b,h=pullback();b[-1]['high']=104
        cs,f=walk(b,h);self.assertEqual(cs,[])
        self.assertEqual(f['PULLBACK_RESUME_ANCHOR_BREACHED'],1)
    def test_chase_distance_rejects_entry_without_inventing_loss(self):
        b,h=pullback();b[-1].update(low=100,close=100.5)
        cs,f=walk(b,h);self.assertEqual(cs,[])
        self.assertEqual(f['PULLBACK_RESUME_CHASE_REJECTED'],1)
    def test_unconfirmed_setup_expires_after_six_observed_bars(self):
        b,h=pullback();b=b[:4];h=h[:4]
        for i in range(4,10):
            x=bar(i,102,103,102,102.7);b.append(x);h.append(state(x,103))
        cs,f=walk(b,h);self.assertEqual(cs,[])
        self.assertEqual(f['PULLBACK_RESUME_EXPIRED'],1)
    def test_reversal_waits_after_flip_even_if_flip_already_broke_reference(self):
        b=[bar(i) for i in range(3)]+[bar(3,100,103,99.5,101.5),bar(4,101.5,102.5,100.5,101.8)]
        h=[state(x,104) for x in b[:3]]+[state(b[3],100,'UP','BUY'),state(b[4],101,'UP')]
        early,_=walk(b[:4],h[:4]);full,_=walk(b,h)
        self.assertEqual([c['family'] for c in early],['FLIP_REFERENCE'])
        rev=[c for c in full if c['family']=='REVERSAL_CONFIRM']
        self.assertEqual(len(rev),1);self.assertEqual(rev[0]['entry_at'],1500)
    def test_price_mirror_preserves_logic_and_reverses_side(self):
        b,h=pullback();a,_=walk(b,h)
        mirrored=[dict(x,open=200-x['open'],high=200-x['low'],low=200-x['high'],close=200-x['close']) for x in b]
        mh=[dict(x,line=200-x['line'],state='UP') for x in h]
        other,_=walk(mirrored,mh)
        self.assertEqual(len(a),len(other));self.assertEqual(other[0]['side'],'BUY')
        self.assertAlmostEqual(a[0]['distance_atr'],other[0]['distance_atr'])
    def test_actual_halftrend_future_append_preserves_prior_candidates(self):
        prices=[100.]*100+[102,104,106,100,98,96,104]*20
        b=[bar(i,p,p+.5,p-.5,p) for i,p in enumerate(prices)]
        early,_,_=scan(b[:160]);full,_,_=scan(b)
        self.assertTrue(early)
        self.assertEqual(early,[c for c in full if c['entry_at']<=160*300])
    def test_gap_resets_indicator_and_setup_warmup(self):
        prices=[100.]*100+[102,104,106,100,98,96,104]
        b=[bar(i,p,p+.5,p-.5,p) for i,p in enumerate(prices)]
        tail=[dict(bar(i,100,101,99,100),open_time=(i+3)*300,close_time=(i+4)*300) for i in range(107,111)]
        cs,_,receipts=scan(b+tail)
        self.assertEqual(len(receipts),2)
        self.assertTrue(all(c['entry_at']<=b[-1]['close_time'] for c in cs))
    def test_clock_mismatch_is_rejected(self):
        b,h=pullback();h[-1]['at']+=300
        with self.assertRaises(ValueError):walk(b,h)
    def test_unknown_outcome_suppresses_full_sequence_metrics(self):
        rows=[dict(status='RESOLVED_REFERENCE',r=-1,exit_at=600),dict(status='CENSORED_AT_SIDE_GAP')]
        self.assertIsNone(sequence(rows)['max_drawdown_at_exit_batches_r'])
        self.assertEqual(sequence(rows,True)['max_drawdown_at_exit_batches_r'],1)
        self.assertFalse(sequence(rows,True)['account_drawdown_available'])


class PatternEvidenceTests(unittest.TestCase):
    def test_hashes_candidate_chronology_and_every_window_population(self):
        import csv,gzip,json
        from hashlib import sha256
        from pathlib import Path
        root=Path('research_evidence/local-history-20261101');name='halftrend_patterns_20261102'
        m=json.loads((root/(name+'_manifest.json')).read_text())
        zipped=(root/(name+'.json.gz')).read_bytes();raw=gzip.decompress(zipped)
        self.assertEqual(sha256(zipped).hexdigest(),m['gzip_sha256'])
        self.assertEqual(sha256(raw).hexdigest(),m['uncompressed_sha256'])
        self.assertEqual(sha256((root/(name+'.csv')).read_bytes()).hexdigest(),m['csv_sha256'])
        with (root/(name+'.csv')).open(newline='') as f:self.assertEqual(len(list(csv.DictReader(f))),12)
        r=json.loads(raw);ids={c['id']:c for c in r['candidates']}
        self.assertEqual(len(ids),len(r['candidates']))
        self.assertEqual(r['funnel']['READY_ROWS']+r['funnel']['NOT_READY_ROWS'],r['aggregation']['complete_bars'])
        for c in ids.values():
            if c['family']=='FLIP_REFERENCE':self.assertEqual(c['entry_at'],c['anchor_known_at'])
            else:
                self.assertGreater(c['entry_at'],c['anchor_known_at'])
                self.assertLessEqual(c['entry_at']-c['anchor_known_at'],1800)
                self.assertLessEqual(c['distance_atr'],1)
        for w in r['results'].values():
            self.assertEqual(len(w['models']),6)
            for model in w['models'].values():
                self.assertEqual(model['entry_plans'],len(model['outcomes']))
                self.assertEqual(sum(model['status_counts'].values()),model['entry_plans'])
                resolved=[x for x in model['outcomes'] if x['status']=='RESOLVED_REFERENCE']
                self.assertEqual(len(resolved),model['resolved'])
                for x in model['outcomes']:self.assertIn(x['candidate_id'],ids)
                self.assertEqual(sum(v['entry_plans'] for v in model['by_side'].values()),model['entry_plans'])
                if model['resolved']!=model['entry_plans']:
                    self.assertIsNone(model['all_candidate_reference_sequence']['max_drawdown_at_exit_batches_r'])
                self.assertIsNone(model['account_return_pct']);self.assertIsNone(model['net_expectancy_r'])
        self.assertFalse(r['formal_lsr02']);self.assertFalse(r['wt_x_reproduced']);self.assertFalse(r['execution_allowed'])
        self.assertFalse(r['adopted']);self.assertFalse(r['independent_holdout_verified'])

if __name__=='__main__':unittest.main()
