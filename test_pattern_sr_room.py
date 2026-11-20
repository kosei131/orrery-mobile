import unittest
from orrery_pattern_sr_room import room,geometry


def bars(high=110):
    return [dict(close_time=(i+1)*900,open=100,high=h,low=l,close=100)
            for i,(h,l) in enumerate(zip([102,104,high,104,102],[98,96,90,96,98]))]

class RoomTests(unittest.TestCase):
    def test_buy_known_pivot_and_threshold(self):
        r=room(bars(),at=4500,side='BUY',entry=100,risk=6)
        self.assertEqual(r['group'],'ROOM_GE_1_5R');self.assertEqual(r['level_known_at'],4500)
        self.assertEqual(room(bars(108),at=4500,side='BUY',entry=100,risk=6)['group'],'ROOM_LT_1_5R')
    def test_sell_support_is_directional(self):
        self.assertEqual(room(bars(),at=4500,side='SELL',entry=100,risk=6)['level'],90)
    def test_pivot_is_not_available_before_confirmation(self):
        r=room(bars(),at=3600,side='BUY',entry=100,risk=6)
        self.assertEqual(r['group'],'UNKNOWN');self.assertIsNone(r['room_r'])
    def test_future_append_does_not_change_past_annotation(self):
        b=bars();extra=dict(close_time=5400,open=100,high=999,low=1,close=100)
        self.assertEqual(room(b,at=4500,side='BUY',entry=100,risk=6),room(b+[extra],at=4500,side='BUY',entry=100,risk=6))
    def test_gap_resets_and_stale_is_unknown(self):
        b=bars()+[dict(close_time=6300,open=100,high=101,low=99,close=100)]
        self.assertEqual(room(b,at=6300,side='BUY',entry=100,risk=6)['group'],'UNKNOWN')
        self.assertEqual(room(bars(),at=5400,side='BUY',entry=100,risk=6)['reason'],'NO_CURRENT_M15')
    def test_missing_level_is_not_a_pass(self):
        self.assertEqual(room(bars(),at=4500,side='BUY',entry=120,risk=6)['group'],'UNKNOWN')
    def test_invalid_clock_and_risk_rejected(self):
        for r in (0,-1,float('nan')):
            with self.assertRaises(ValueError):room(bars(),at=4500,side='BUY',entry=100,risk=r)
        with self.assertRaises(ValueError):room(bars()[::-1],at=4500,side='BUY',entry=100,risk=6)
    def test_geometry_uses_correct_quote_and_anchor_side(self):
        c=dict(entry_at=120,side='SELL',anchor_open=0,anchor_known_at=120,anchor_bid_low=90)
        bid={t:dict(open=100,high=101,low=99,close=100) for t in (0,60,120)}
        ask={t:dict(open=101,high=104,low=100,close=101) for t in (0,60,120)}
        self.assertEqual(geometry(c,'ANCHOR_EXTREME',bid,ask),(100,4))
        del ask[60];self.assertIsNone(geometry(c,'ANCHOR_EXTREME',bid,ask))

class EvidenceTests(unittest.TestCase):
    def test_every_baseline_candidate_kept_and_levels_are_causal(self):
        import csv,json
        from pathlib import Path
        from hashlib import sha256
        from orrery_pattern_robustness import load_parent
        root=Path('research_evidence/local-history-20261101')
        path=root/'pattern_sr_room_20261103.csv';r=json.loads((root/'pattern_sr_room_20261103.json').read_text())
        self.assertEqual(sha256(path.read_bytes()).hexdigest(),r['annotations_sha256'])
        with path.open(newline='',encoding='utf-8') as f:rows=list(csv.DictReader(f))
        parent=load_parent()
        for window,ms in r['models'].items():
            for model,m in ms.items():
                group=[x for x in rows if x['window']==window and x['model']==model]
                self.assertEqual(len(group),m['baseline']['entry_plans'])
                self.assertEqual({x['candidate_id'] for x in group},{x['candidate_id'] for x in parent['results'][window]['models'][model]['outcomes']})
                for name,stats in m['groups'].items():self.assertEqual(sum(x['group']==name for x in group),stats['entry_plans'])
        for x in rows:
            if x['level_known_at']:self.assertLessEqual(int(x['level_known_at']),int(x['entry_at']))
            if x['group']=='UNKNOWN':self.assertEqual(x['room_r'],'')
        self.assertFalse(r['adopted']);self.assertFalse(r['out_of_sample'])
        self.assertIsNone(r['net_expectancy_r'])

if __name__=='__main__':unittest.main()
