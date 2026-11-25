# SPDX-License-Identifier: GPL-3.0-only
from datetime import datetime, timezone
import unittest

from orrery_gold_hourly_trend import signals as strict_signals
from orrery_gold_session_hourly import chains, open_horizon, replay, signals


def stamp(value):
    return int(datetime.fromisoformat(value).replace(tzinfo=timezone.utc).timestamp())


def bar(at, price):
    return dict(close_time=at, close=price, high=price+1, low=price-1)


class SessionHourlyTests(unittest.TestCase):
    def test_closed_daily_gap_carries_but_open_gap_resets(self):
        at = stamp('2026-01-06T22:00:00')
        # Test a full lookback spanning the NY 17-18 daily break.
        earlier = [bar(at-(20-i)*3600,100) for i in range(20)]
        rows = earlier+[bar(at,90), bar(at+7200,101)]
        self.assertTrue(any(r['at_utc']==at+7200 for r in signals(rows, at+7201, session=True)))
        self.assertFalse(any(r['at_utc']==at+7200 for r in signals(rows, at+7201, session=False)))
        rows[-1]['close_time'] += 3600
        self.assertFalse(any(r['at_utc']==at+10800 for r in signals(rows, at+10801, session=True)))

    def test_strict_signals_match_original_on_open_hours(self):
        at = stamp('2026-01-06T21:00:00')
        rows = [bar(at-(20-i)*3600,p) for i,p in enumerate([100]*19+[90,101])]
        original = [{k:v for k,v in r.items() if k!='h4_direction'}
                    for r in strict_signals(rows, [], at+1)]
        self.assertEqual(list(signals(rows, at+1, session=False)), original)
        self.assertEqual(list(signals(rows, at+1, session=True)), original)

    def test_weekend_and_dst_closures_allow_context_only(self):
        friday = stamp('2025-03-07T22:00:00')
        monday = stamp('2025-03-09T23:00:00')
        rows = [bar(friday-(20-i)*3600,p) for i,p in enumerate([100]*19+[90,90])]
        rows.append(bar(monday,101))
        self.assertTrue(list(signals(rows,monday+1,session=True)))
        self.assertFalse(list(signals(rows,monday+1,session=False)))

    def test_close_and_end_horizons(self):
        at = stamp('2026-01-06T21:00:00')
        self.assertEqual(open_horizon(at,at+86400),60)
        self.assertEqual(open_horizon(at+3600,at+86400),0)
        self.assertEqual(open_horizon(at,at+1800),30)
        summer = stamp('2026-07-06T20:00:00')
        self.assertEqual(open_horizon(summer,summer+86400),60)

    def test_no_future_bar_changes_past_signal(self):
        at = stamp('2026-01-06T21:00:00')
        rows = [bar(at-(20-i)*3600,p) for i,p in enumerate([100]*19+[90,101])]
        before = list(signals(rows,at+1,session=True))
        self.assertEqual(list(signals(rows+[bar(at+3600,10000)],at+1,session=True)),before)

    def test_session_close_and_gap_remain_distinct(self):
        at = stamp('2026-01-06T21:00:00')
        bid = {at+i*60:dict(open=100,high=100.1,low=99.9,close=100) for i in range(60)}
        ask = {t:{k:v+.1 for k,v in b.items()} for t,b in bid.items()}
        found = [dict(at_utc=at,side='BUY',stop_distance=2)]
        rows,_ = replay(found,bid,ask,at+86400)
        self.assertEqual(rows[0]['exit_reason'],'SESSION_CLOSE')
        self.assertAlmostEqual(rows[0]['r'],-.1/2.1)
        del ask[at+30*60]
        rows,_ = replay(found,bid,ask,at+86400)
        self.assertEqual(rows[0]['status'],'CENSORED_AT_SIDE_GAP')
        self.assertNotIn('r',rows[0])

    def test_sell_tp_and_one_position(self):
        at = stamp('2026-01-06T19:00:00')
        bid = {at+i*60:dict(open=100,high=100.1,low=99.9,close=100) for i in range(180)}
        ask = {t:{k:v+.1 for k,v in b.items()} for t,b in bid.items()}
        ask[at+120]['low']=95
        found=[dict(at_utc=at,side='SELL',stop_distance=2),
               dict(at_utc=at+60,side='SELL',stop_distance=2)]
        rows, skips=replay(found,bid,ask,at+86400)
        self.assertEqual(len(rows),1)
        self.assertAlmostEqual(rows[0]['r'],2)
        self.assertEqual(skips['OCCUPIED_OR_UNKNOWN_OUTCOME'],1)

    def test_unordered_bars_are_rejected(self):
        at=stamp('2026-01-06T19:00:00')
        with self.assertRaises(ValueError):
            list(chains([bar(at,100),bar(at,101)],session=True))


if __name__ == '__main__':
    unittest.main()
