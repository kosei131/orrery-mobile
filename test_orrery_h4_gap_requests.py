import csv
from datetime import datetime,timedelta,timezone
from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest
from orrery_m1_complete_bars import aggregate
from orrery_h4_gap_requests import requests


class GapRequestsTests(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup)
        self.root=Path(t.name);self.m1=self.root/'m1.csv';self.h4=self.root/'h4.csv'
        self.cal=self.root/'calendar.json';self.base=datetime(2026,10,26,tzinfo=timezone.utc)

    def iso(self,m):return (self.base+timedelta(minutes=m)).isoformat()

    def build(self,missing=(),closed=()):
        intervals=[]
        for i in range(5):
            intervals.append(dict(start_utc=self.iso(i*240),end_utc=self.iso((i+1)*240),
                                  state='CLOSED' if i in closed else 'OPEN'))
        cal=dict(source='SYNTHETIC hypothesis',intervals=intervals)
        self.cal.write_text(json.dumps(cal))
        with self.m1.open('w',newline='') as stream:
            w=csv.writer(stream);w.writerow(['timestamp_utc','bid_open','bid_high','bid_low','bid_close'])
            for i in range(1200):
                if i not in missing and i//240 not in closed:w.writerow([self.iso(i),100,101,99,100])
        aggregate(self.m1,self.h4,'H4',calendar=cal)
        return dict(normalized_sha256=sha256(self.m1.read_bytes()).hexdigest(),
            h4_sha256=sha256(self.h4.read_bytes()).hexdigest(),calendar_sha256=sha256(self.cal.read_bytes()).hexdigest(),
            start=int(self.base.timestamp()),end=int(self.base.timestamp())+5*14400,
            published_at=int(self.base.timestamp())-1)

    def run_request(self,kw):return requests(self.m1,self.h4,self.cal,**kw)

    def test_one_missing_minute_maps_to_exact_break_and_context(self):
        kw=self.build(missing=(480,));r=self.run_request(kw);g=r['rows'][0]
        self.assertEqual(r['quote_evidence_targets'],1)
        self.assertEqual(g['prior_contiguous_h4_bars'],2)
        self.assertEqual(g['following_contiguous_h4_bars'],2)
        self.assertEqual(g['unexplained_open_minutes'],1)
        self.assertEqual(g['missing_open_intervals'],[dict(start_utc=self.iso(480),end_utc_exclusive=self.iso(481))])
        self.assertFalse(r['continuity_restored'])
        self.assertIsNone(r['actual_profit_usd'])

    def test_closed_slot_is_calendar_review_not_quote_request(self):
        r=self.run_request(self.build(closed=(2,)))
        self.assertEqual(r['quote_evidence_targets'],0)
        self.assertEqual(r['rows'][0]['weekly_closed_h4_slots'],1)
        self.assertEqual(r['rows'][0]['unexplained_open_minutes'],0)

    def test_leading_partial_input_remains_boundary_evidence(self):
        r=self.run_request(self.build(missing=(0,)))
        self.assertEqual(r['interruption_count'],0)
        self.assertEqual(r['all_absent_expected_open_h4_slots'],1)
        self.assertEqual(r['study_boundary_open_slots'],[dict(open_utc=self.iso(0),unexplained_open_minutes=1)])
        self.assertEqual(r['source_edge_slots'],[self.iso(0)])

    def test_pins_and_post_publication_horizon_are_required(self):
        kw=self.build(missing=(480,))
        for change in (dict(normalized_sha256='0'*64),dict(h4_sha256='0'*64),
                       dict(calendar_sha256='0'*64),dict(published_at=kw['start']+1)):
            with self.subTest(change=change),self.assertRaises(ValueError):self.run_request(dict(kw,**change))

    def test_absent_h4_cannot_be_excused_when_all_minutes_present(self):
        kw=self.build();lines=self.h4.read_text().splitlines();self.h4.write_text('\n'.join(lines[:3]+lines[4:])+'\n')
        kw['h4_sha256']=sha256(self.h4.read_bytes()).hexdigest()
        with self.assertRaisesRegex(ValueError,'reconcile'):self.run_request(kw)

    def test_priority_uses_missing_minute_budget_after_context_tie(self):
        r=self.run_request(self.build(missing=(240,241,720)))
        self.assertEqual(r['quote_evidence_targets'],2)
        self.assertEqual(r['rows'][0]['gap_start_utc'],self.iso(720))
        self.assertEqual([x['evidence_review_rank'] for x in r['rows']],[1,2])

    def test_mixed_closure_and_unknown_never_promises_continuity(self):
        r=self.run_request(self.build(missing=(480,),closed=(1,)))
        self.assertEqual(r['rows'][0]['unexplained_open_minutes'],1)
        self.assertEqual(r['quote_evidence_targets'],0)
        self.assertFalse(r['rows'][0]['continuity_restoration_claimed'])
