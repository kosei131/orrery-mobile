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



def classify_gap_intervals(gaps):
    """Partition missing minutes by the existing UNVERIFIED weekly hypothesis.

    Publication timing is descriptive: this is neither a historical calendar
    certificate nor permission to bridge bars or change candidate selection.
    """
    if not isinstance(gaps,list) or len(gaps)>10000:
        raise ValueError('Bounded explicit gap list required')
    published=dt.datetime.fromisoformat('2026-08-22T20:59:35+00:00')
    rows=[]; previous_end=None; total_minutes=0
    for gap in gaps:
        pair=[]
        for key in ('after_utc','before_utc'):
            at=dt.datetime.fromisoformat(gap[key].replace('Z','+00:00'))
            if at.utcoffset()!=dt.timedelta(0) or at.second or at.microsecond:
                raise ValueError('Explicit UTC minute gap boundaries required')
            pair.append(at)
        before,after=pair
        count=int((after-before).total_seconds())//60-1
        if (count<=0 or type(gap.get('missing_minutes')) is not int
                or gap['missing_minutes']!=count
                or previous_end is not None and before<previous_end):
            raise ValueError('Ordered nonoverlapping gaps with exact counts required')
        total_minutes+=count
        if total_minutes>366*1440:
            raise ValueError('Gap minute budget exceeds one year')
        previous_end=after
        open_minutes=closed_minutes=before_publication=0
        at=before+dt.timedelta(minutes=1)
        while at<after:
            if weekly_open(at):open_minutes+=1
            else:closed_minutes+=1
            before_publication+=at<published
            at+=dt.timedelta(minutes=1)
        rows.append(dict(after_utc=before.isoformat(),before_utc=after.isoformat(),
            missing_minutes=count,weekly_open_unexplained_minutes=open_minutes,
            weekly_closed_candidate_minutes=closed_minutes,
            minutes_before_schedule_publication=before_publication,
            classification=('MIXED_WEEKLY_OPEN_AND_CLOSED' if open_minutes and closed_minutes
                else 'UNEXPLAINED_WEEKLY_OPEN' if open_minutes else 'WEEKLY_CLOSURE_CANDIDATE'),
            session_reason='UNVERIFIED'))
    return dict(status='UNVERIFIED_WEEKLY_GAP_PARTITION_ONLY',
        source_url=SOURCE,published_report_utc=published.isoformat(),
        rule_basis='EXISTING_UNVERIFIED_UTC_WEEKLY_HYPOTHESIS_NOT_RETRIEVED_LIVE',
        weekly_rule=dict(mon_thu_closed='21:00-22:00',friday_close='20:45',
                         saturday='CLOSED',sunday_open='22:00',timezone='UTC'),
        missing_minutes=total_minutes,
        weekly_open_unexplained_minutes=sum(r['weekly_open_unexplained_minutes'] for r in rows),
        weekly_closed_candidate_minutes=sum(r['weekly_closed_candidate_minutes'] for r in rows),
        minutes_before_schedule_publication=sum(r['minutes_before_schedule_publication'] for r in rows),
        gaps=rows,calendar_authenticated=False,publication_preknown_for_all_minutes=all(
            r['minutes_before_schedule_publication']==0 for r in rows),
        continuity_restored=False,strategy_adopted=False,actual_profit_usd=None,
        execution_allowed=False)

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
              'h4_file_sha256': hashlib.sha256((out/'H4_WEEKLY_SCHEDULE_UNVERIFIED.csv').read_bytes()).hexdigest() if bars is not None else None,
              'historical_holidays_and_session_changes_verified': False,
              'broker_calendar_verified': False, 'h4_strategy_ready': False,
              'execution_allowed': False, 'profit_usd': None,
              'warning': 'Missing timestamps are candidates for missing data or unlisted session exceptions. Public weekly rules cannot distinguish them. Any closure conflict blocks H4 export. A matching schedule is not feed authentication.'}
    (out/'report.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    return result

if __name__ == '__main__':
    print(json.dumps(crosscheck('public_xau_bars/XAUUSD_M1_UNVERIFIED_QUOTE.csv',
                               'public_xau_session_coverage')))
