# SPDX-License-Identifier: GPL-3.0-only
from copy import deepcopy
import unittest
from lsr04_signal_journal import SignalJournal
from lsr05_halftrend import calculate
from lsr05_observation import HalfTrendObserver
from test_lsr05_halftrend import bars


class ObservationTests(unittest.TestCase):
    def setUp(self):
        self.journal=SignalJournal(); self.monitor=HalfTrendObserver(self.journal)
        self.data=bars([100.]*100+[102.,104.,106.,100.,98.,96.,104.])

    def snapshot(self,data=None,**settings):
        data=self.data if data is None else data
        return calculate(data,as_of=data[-1]['close_time'],interval=300,enabled=True,**settings)

    def observe(self,snapshot=None,**settings):
        snap=self.snapshot() if snapshot is None else snapshot
        args=dict(symbol='XAUUSD',observed_at=self.data[-1]['close_time']+1,
                  data_source='SYNTHETIC_FEED',implementation_version='ORRERY05-v1')
        args.update(settings)
        return self.monitor.observe(snap,**args)

    def test_existing_journal_receives_only_ready_closed_observations(self):
        out=self.observe()
        self.assertEqual(len(out['events']),107)
        self.assertEqual(len(out['signal_events']),8)
        self.assertEqual([e['signal'] for e in out['signal_events'] if e['signal']!='NONE'],['SELL','BUY'])
        self.assertFalse(out['execution_allowed'])
        self.assertFalse(out['nonrepainting_verified'])

    def test_identical_snapshot_not_counted_as_new_signals(self):
        first=self.observe(); second=self.observe(observed_at=self.data[-1]['close_time']+2)
        self.assertEqual(second['events'],[]); self.assertEqual(second['signal_events'],[])
        self.assertEqual(len(self.journal.report()['events']),len(first['signal_events']))

    def test_future_append_preserves_old_observations(self):
        self.observe()
        extended=bars([b['close'] for b in self.data]+[105.,106.])
        out=self.observe(self.snapshot(extended),observed_at=extended[-1]['close_time']+1)
        self.assertEqual(len(out['events']),2)
        self.assertFalse(any(e['changed_after_observation'] for e in out['events']))

    def test_changed_historical_signal_is_recorded_not_overwritten(self):
        self.observe(); corrected=deepcopy(self.data)
        corrected[104].update(open=102.,high=102.5,low=101.5,close=102.)
        out=self.observe(self.snapshot(corrected),observed_at=self.data[-1]['close_time']+2)
        changes=[e for e in out['signal_events'] if e['changed_after_observation']]
        self.assertTrue(any(e['previous_signal']=='SELL' and e['signal']=='NONE' for e in changes))
        self.assertGreater(self.monitor.report()['signal_revision_count'],0)
        old=[e for e in self.journal.report()['events'] if e['signal']=='SELL' and not e['changed_after_observation']]
        self.assertTrue(old)

    def test_channel_change_detected_even_when_signal_is_unchanged(self):
        flat=bars([100.]*100)
        self.observe(self.snapshot(flat)); changed=deepcopy(flat); changed[70]['high']=100.7
        out=self.observe(self.snapshot(changed),observed_at=self.data[-1]['close_time']+2)
        self.assertTrue(any(e['changed_after_observation'] for e in out['events']))
        self.assertEqual(self.monitor.report()['signal_revision_count'],0)

    def test_amplitude_and_history_anchor_have_distinct_identities(self):
        a=self.observe(); b=self.observe(self.snapshot(amplitude=4))
        c=self.observe(self.snapshot(self.data[1:]))
        self.assertEqual(len({a['revision_id'],b['revision_id'],c['revision_id']}),3)
        self.assertEqual(self.monitor.report()['value_revision_count'],0)

    def test_late_observation_is_not_backdated_to_candle_close(self):
        now=self.data[-1]['close_time']+1000
        out=self.observe(observed_at=now)
        self.assertTrue(all(e['observed_at']==now for e in out['signal_events']))

    def test_invalid_future_snapshot_has_no_partial_journal_writes(self):
        with self.assertRaises(ValueError): self.observe(observed_at=self.data[-2]['close_time'])
        self.assertEqual(self.journal.report()['observations'],0)
        bad=self.snapshot(); bad['rows'][-1]['atr_low']=float('nan')
        with self.assertRaises(ValueError): self.observe(bad)
        self.assertEqual(self.monitor.report()['events'],[])

    def test_capacity_exhaustion_stops_before_mutation(self):
        monitor=HalfTrendObserver(self.journal,max_events=100)
        with self.assertRaises(ValueError): monitor.observe(self.snapshot(),symbol='XAUUSD',
            observed_at=self.data[-1]['close_time']+1,data_source='SYNTHETIC',implementation_version='v1')
        self.assertEqual(self.journal.report()['observations'],0)

    def test_regressed_clock_and_history_end_rejected(self):
        self.observe()
        with self.assertRaises(ValueError): self.observe(observed_at=self.data[-1]['close_time'])
        with self.assertRaises(ValueError): self.observe(self.snapshot(self.data[:-1]),
            observed_at=self.data[-1]['close_time']+2)

    def test_warmup_does_not_emit_none_as_a_confirmed_signal(self):
        out=self.observe(self.snapshot(self.data[:50]))
        self.assertEqual(out['signal_events'],[])
        self.assertEqual(self.journal.report()['observations'],0)

    def test_returned_records_do_not_mutate_retained_history(self):
        out=self.observe(); out['events'][0]['values']['line']=1
        out['events'][0]['configuration']['amplitude']=8
        history=self.monitor.report()
        self.assertNotEqual(history['events'][0]['values']['line'],1)
        self.assertEqual(history['events'][0]['configuration']['amplitude'],2)

    def test_disabled_snapshot_does_not_write(self):
        out=self.observe(calculate(None,as_of=0,interval=300))
        self.assertEqual(out['status'],'DISABLED')
        self.assertEqual(self.monitor.report()['events'],[])

    def test_m15_and_data_source_are_separate_scopes(self):
        a=self.observe()
        data=bars([b['close'] for b in self.data],interval=900)
        snap=calculate(data,as_of=data[-1]['close_time'],interval=900,enabled=True)
        b=self.observe(snap,observed_at=data[-1]['close_time']+1)
        c=self.observe(data_source='OTHER_FEED')
        self.assertEqual(b['events'][0]['timeframe'],'M15')
        self.assertEqual(len({a['revision_id'],b['revision_id'],c['revision_id']}),3)


if __name__=='__main__': unittest.main()
