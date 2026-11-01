# SPDX-License-Identifier: GPL-3.0-only
from copy import deepcopy
from datetime import datetime,timezone,timedelta
import tempfile
from pathlib import Path
import unittest
from lsr05_session_clock import evidence_sha256, audit_close_times
from lsr05_halftrend import calculate, compare_amplitudes
from lsr05_observation import HalfTrendObserver
from lsr04_signal_journal import SignalJournal
from lsr05_observation_store import create_store,append_snapshot,restore_store

BASE=datetime(2026,10,26,tzinfo=timezone.utc)


def iso(minutes): return (BASE+timedelta(minutes=minutes)).isoformat()


def evidence(parts):
    return dict(symbol='XAUUSD',data_source='SYNTHETIC',known_at_utc=iso(-60),
        source_document_sha256='a'*64,calendar=dict(source='SYNTHETIC dated schedule',intervals=[
            dict(start_utc=iso(a),end_utc=iso(b),state=state) for a,b,state in parts]))


def data():
    # 50 observed M15 bars, one-hour closure, then 50 observed bars.
    closes=list(range(15,751,15))+list(range(825,1561,15))
    return [dict(close_time=int(BASE.timestamp())+m*60,open=100.,high=100.5,low=99.5,close=100.) for m in closes]


class SessionClockTests(unittest.TestCase):
    def setUp(self):
        self.bars=data()
        self.evidence=evidence([(0,750,'OPEN'),(750,810,'CLOSED'),(810,1560,'OPEN')])

    def calc(self,bars=None,ev=None):
        b=self.bars if bars is None else bars; e=self.evidence if ev is None else ev
        return calculate(b,as_of=int((BASE+timedelta(minutes=1560)).timestamp()),interval=900,
            enabled=True,symbol='XAUUSD',data_source='SYNTHETIC',calendar_evidence=e,
            expected_calendar_sha256=evidence_sha256(e))

    def test_confirmed_schedule_clock_carries_state_without_inventing_bars(self):
        out=self.calc()
        self.assertEqual(out['status'],'HALFTREND_RESEARCH_ONLY')
        self.assertEqual(len(out['rows']),100)
        self.assertEqual(out['calendar_audit']['closed_bar_slots'],4)
        self.assertEqual(out['calendar_audit']['permitted_gaps'][0]['skipped_bar_slots'],4)
        self.assertEqual(out['rows'][-1]['atr'],1.)
        self.assertFalse(out['calendar_audit']['calendar_broker_verified'])

    def test_strict_default_still_refuses_the_same_gap(self):
        with self.assertRaises(ValueError): calculate(self.bars,as_of=self.bars[-1]['close_time'],
                                                       interval=900,enabled=True)

    def test_missing_open_bar_is_not_excused_by_known_closure(self):
        out=self.calc(self.bars[:20]+self.bars[21:])
        self.assertEqual(out['status'],'BLOCKED_SESSION_HISTORY')
        self.assertEqual(out['rows'],[])
        self.assertEqual(out['calendar_audit']['missing_open_bars'],1)

    def test_bar_during_closure_is_contradiction(self):
        b=deepcopy(self.bars)
        extra=dict(b[49],close_time=int(BASE.timestamp())+765*60)
        out=self.calc(b[:50]+[extra]+b[50:])
        self.assertEqual(out['status'],'BLOCKED_SESSION_HISTORY')
        self.assertEqual(out['calendar_audit']['unexpected_bar_closes'],1)

    def test_late_calendar_and_wrong_feed_and_changed_pin_rejected(self):
        for changes in (dict(known_at_utc=iso(1)),dict(data_source='OTHER'),dict(symbol='USDJPY')):
            with self.assertRaises(ValueError): self.calc(ev=dict(self.evidence,**changes))
        with self.assertRaises(ValueError): calculate(self.bars,as_of=self.bars[-1]['close_time'],
            interval=900,enabled=True,symbol='XAUUSD',data_source='SYNTHETIC',
            calendar_evidence=self.evidence,expected_calendar_sha256='0'*64)

    def test_unknown_state_hole_or_naive_timezone_rejected(self):
        variants=[evidence([(0,750,'OPEN'),(750,810,'UNKNOWN'),(810,1560,'OPEN')]),
                  evidence([(0,750,'OPEN'),(765,810,'CLOSED'),(810,1560,'OPEN')])]
        naive=deepcopy(self.evidence); naive['known_at_utc']='2026-10-25T23:00:00'; variants.append(naive)
        for e in variants:
            with self.assertRaises(ValueError): self.calc(ev=e)

    def test_reopening_price_gap_is_included_in_atr(self):
        b=deepcopy(self.bars)
        for row in b[50:]: row.update(open=110.,high=110.5,low=109.5,close=110.)
        out=self.calc(b)
        self.assertAlmostEqual(out['rows'][-1]['atr'],(99+10.5)/100)

    def test_observer_rechecks_calendar_and_preserves_real_closing_times(self):
        snap=self.calc(); monitor=HalfTrendObserver(SignalJournal())
        args=dict(symbol='XAUUSD',observed_at=self.bars[-1]['close_time']+1,
                  data_source='SYNTHETIC',implementation_version='v2')
        observed=monitor.observe(snap,**args)
        self.assertEqual(observed['events'][50]['closed_at'],self.bars[50]['close_time'])
        self.assertIn('session_calendar_identity',observed['events'][0]['configuration'])
        bad=deepcopy(snap); bad['calendar_audit']['missing_open_bars']=1
        with self.assertRaises(ValueError): monitor.observe(bad,**args)

    def test_calendar_identity_survives_horizon_extension_with_same_evidence(self):
        old=self.calc(); ext=evidence([(0,750,'OPEN'),(750,810,'CLOSED'),(810,1575,'OPEN')])
        b=self.bars+[dict(self.bars[-1],close_time=self.bars[-1]['close_time']+900)]
        new=calculate(b,as_of=b[-1]['close_time'],interval=900,enabled=True,symbol='XAUUSD',
            data_source='SYNTHETIC',calendar_evidence=ext,expected_calendar_sha256=evidence_sha256(ext))
        self.assertEqual(old['calendar_audit']['calendar_identity_sha256'],new['calendar_audit']['calendar_identity_sha256'])
        monitor=HalfTrendObserver(SignalJournal())
        for snap,at in ((old,self.bars[-1]['close_time']+1),(new,b[-1]['close_time']+1)):
            result=monitor.observe(snap,symbol='XAUUSD',observed_at=at,data_source='SYNTHETIC',implementation_version='v2')
        self.assertEqual(len(result['events']),1)
        self.assertFalse(result['events'][0]['changed_after_observation'])

    def test_store_replays_calendar_aware_snapshots(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'store'; pin=create_store(root)['head_sha256']
            saved=append_snapshot(root,expected_head_sha256=pin,snapshot=self.calc(),symbol='XAUUSD',
                observed_at=self.bars[-1]['close_time']+1,data_source='SYNTHETIC',implementation_version='v2')
            restored=restore_store(root,expected_head_sha256=saved['head_sha256'])
            self.assertEqual(restored['batches'],1)
            self.assertEqual(len(restored['report']['events']),100)

    def test_amplitude_grid_uses_same_pinned_calendar(self):
        result=compare_amplitudes(self.bars,as_of=self.bars[-1]['close_time'],interval=900,
            symbol='XAUUSD',data_source='SYNTHETIC',calendar_evidence=self.evidence,
            expected_calendar_sha256=evidence_sha256(self.evidence))
        self.assertEqual(set(result['results']),{'2','4','6','8'})
        self.assertTrue(all(len(r['rows'])==100 for r in result['results'].values()))
        self.assertIsNone(result['best_amplitude'])


if __name__=='__main__': unittest.main()
