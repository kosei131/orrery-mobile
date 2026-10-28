"""Public XAU weekly schedule crosscheck, NOT historical calendar certification.

Published GetData UTC hours, report dated 2026-08-22. No inferred holidays,
no permission to bridge gaps or use resulting bars as a verified strategy.
"""
import csv
import datetime as dt
import json
import hashlib
from pathlib import Path
from orrery_m1_complete_bars import aggregate
from orrery_real_bars_lsr_bridge import load
from orrery_public_xau_sequence_study import segments

SOURCE = 'https://getdata.finance/coverage/xauusd'

def weekly_open(t):
    day, minute = t.weekday(), t.hour*60+t.minute
    if day < 4:
        return minute < 21*60 or minute >= 22*60
    if day == 4:
        return minute < 20*60+45
    return day == 6 and minute >= 22*60


def crosscheck(src, output_dir):
    observed = set()
    with Path(src).open(newline='', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            t = dt.datetime.fromisoformat(row['timestamp_utc'])
            if t.tzinfo is None or t.utcoffset() != dt.timedelta(0) or t.second or t.microsecond:
                raise ValueError('Explicit UTC minute timestamps required')
            stamp = int(t.timestamp())
            if observed and stamp <= last:
                raise ValueError('M1 timestamps must strictly increase')
            if not observed:
                first = stamp
            last = stamp
            observed.add(stamp)
    if not observed:
        raise ValueError('Empty source')
    if last-first > 366*86400:
        raise ValueError('Source horizon exceeds one year')
    # Grid boundary edges are not complete source coverage; never certify them.
    start = first//14400*14400
    end = (last//14400+1)*14400
    expected = set()
    intervals = []
    for stamp in range(start, end, 60):
        t = dt.datetime.fromtimestamp(stamp, dt.timezone.utc)
        state = 'OPEN' if weekly_open(t) else 'CLOSED'
        if state == 'OPEN':
            expected.add(stamp)
        if not intervals or intervals[-1]['state'] != state:
            intervals.append({'start_utc': t.isoformat(), 'end_utc': None, 'state': state})
        intervals[-1]['end_utc'] = dt.datetime.fromtimestamp(stamp+60, dt.timezone.utc).isoformat()
    # Edge truncation is separate from absent open records inside observed horizon.
    inside = {t for t in expected if first <= t <= last}
    missing = sorted(inside-observed)
    outside = sorted(observed-expected)
    def iso(t):
        return dt.datetime.fromtimestamp(t, dt.timezone.utc).isoformat()
    calendar = {'source': SOURCE+'; published weekly schedule only, dated 2026-08-22; historical exceptions UNKNOWN',
                'intervals': intervals}
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=False)
    (out/'weekly_calendar_hypothesis.json').write_text(json.dumps(calendar, indent=2)+'\n', encoding='utf-8')
    bars = None
    continuity = None
    if not outside:
        bar_path = out/'H4_WEEKLY_SCHEDULE_UNVERIFIED.csv'
        bars = aggregate(Path(src), bar_path, 'H4', calendar=calendar)
        bars['price_basis'] = 'publisher quote, NOT verified broker Bid/Ask'
        groups = segments(load(bar_path, 'H4')['bars'], 14400)
        continuity = {'longest_consecutive_h4_bars': max((len(g) for g in groups), default=0),
                      'segments_with_at_least_12_bars': sum(len(g)>=12 for g in groups),
                      'bar_endpoints_with_12_consecutive_bars': sum(max(0,len(g)-11) for g in groups),
                      'bridged_missing_bars': False,
                      'note': '12 is a coverage diagnostic, not a validated regime rule.'}
    result = {'status': 'PUBLISHED_WEEKLY_SCHEDULE_CROSSCHECK_ONLY',
              'source_url': SOURCE, 'normalized_m1_sha256': hashlib.sha256(Path(src).read_bytes()).hexdigest(), 'published_report_utc': '2026-08-22T20:59:35+00:00',
              'first_observed_utc': iso(first), 'last_observed_utc': iso(last),
              'observed_m1': len(observed), 'expected_open_inside_observed_horizon': len(inside),
              'missing_open_minutes': len(missing), 'quotes_during_published_closure': len(outside),
              'missing_examples': [iso(t) for t in missing[:10]],
              'closure_conflict_examples': [iso(t) for t in outside[:10]],
              'edge_open_minutes_outside_observed_horizon': len(expected-inside),
              'h4_aggregation': bars, 'h4_continuity': continuity,
              'historical_holidays_and_session_changes_verified': False,
              'broker_calendar_verified': False, 'h4_strategy_ready': False,
              'execution_allowed': False, 'profit_usd': None,
              'warning': 'Missing timestamps are candidates for missing data or unlisted session exceptions. Public weekly rules cannot distinguish them. Any closure conflict blocks H4 export. A matching schedule is not feed authentication.'}
    (out/'report.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    return result

if __name__ == '__main__':
    print(json.dumps(crosscheck('public_xau_bars/XAUUSD_M1_UNVERIFIED_QUOTE.csv',
                               'public_xau_session_coverage')))
