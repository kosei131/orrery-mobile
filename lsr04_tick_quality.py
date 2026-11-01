"""Streaming normalized Bid/Ask quality audit; no completeness or fill approval.

No inferred weekend calendar. Repeated normalized quotes may represent distinct
raw events whose flags were discarded by intake. They are retained and flagged.
"""
from bisect import bisect_right
from decimal import Decimal
from datetime import datetime, timezone
from hashlib import sha256
from json import dumps
from math import isfinite


def _number(value, positive=False):
    if type(value) not in (int, float) or not isfinite(value) or (positive and value <= 0):
        raise ValueError('Finite audit parameter required')
    return float(value)


def _time(value):
    if isinstance(value, str):
        value = datetime.fromisoformat(value)
    if not isinstance(value, datetime) or value.utcoffset() is None or value.utcoffset().total_seconds() != 0 or value.microsecond % 1000:
        raise ValueError('UTC millisecond-aligned bounds required')
    delta = value-datetime(1970,1,1,tzinfo=timezone.utc)
    return delta.days*86400000 + delta.seconds*1000 + delta.microseconds//1000


def audit_ticks(ticks, *, symbol, start_utc, end_utc, source, broker_spec,
                max_spread_points, max_gap_seconds=60, windows=None,
                sessions=None, session_source=None,
                spread_bin_edges_points=(1, 5, 10, 25, 50, 100),
                max_ticks=10000000, max_examples=100):
    if symbol not in ('XAUUSD', 'USDJPY') or not isinstance(source, str) or not source.strip():
        raise ValueError('Canonical symbol and explicit source required')
    start, end = _time(start_utc), _time(end_utc)
    if start >= end:
        raise ValueError('Increasing audit bounds required')
    if not isinstance(broker_spec, dict) or broker_spec.get('symbol') != symbol:
        raise ValueError('Explicit matching broker specification required')
    point = _number(broker_spec.get('point'), True)
    contract = _number(broker_spec.get('trade_contract_size'), True)
    digits = broker_spec.get('digits')
    if type(digits) is not int or not 0 <= digits <= 12:
        raise ValueError('Broker digits required')
    gap_limit = _number(max_gap_seconds, True)*1000
    spread_limit = _number(max_spread_points, True)
    if type(max_ticks) is not int or not 1 <= max_ticks <= 100000000 or type(max_examples) is not int or not 0 <= max_examples <= 1000:
        raise ValueError('Invalid audit resource budget')
    edges = [_number(v, True) for v in spread_bin_edges_points]
    if not edges or len(edges) > 100 or edges != sorted(set(edges)):
        raise ValueError('Increasing spread-bin edges required')
    calendar = []
    if sessions is not None:
        if not isinstance(sessions, list) or len(sessions) > 100000 or not isinstance(session_source, str) or not session_source.strip():
            raise ValueError('Explicit bounded session calendar and provenance required')
        for row in sessions:
            a, b = _time(row['start_utc']), _time(row['end_utc'])
            state = row.get('state')
            if not start <= a < b <= end or state not in ('OPEN', 'CLOSED') or (calendar and a < calendar[-1][1]):
                raise ValueError('Ordered nonoverlapping session intervals required')
            calendar.append((a, b, state))
    calendar_starts = [r[0] for r in calendar]
    manifest = []; manifest_holes = []; cap_windows = 0
    if windows is not None:
        if not isinstance(windows, list) or len(windows) > 100000:
            raise ValueError('Bounded window manifest required')
        cursor = start
        for row in windows:
            a = _time(row.get('start_utc', row.get('start')))
            b = _time(row.get('end_utc', row.get('end')))
            count = row.get('accepted_ticks', row.get('count'))
            if not start <= a < b <= end or a < cursor or type(count) is not int or count < 0:
                raise ValueError('Ordered nonoverlapping window/count manifest required')
            if a > cursor:manifest_holes.append((cursor, a))
            cap = row.get('at_safety_limit', False)
            if type(cap) is not bool:raise ValueError('Invalid saturation evidence')
            cap_windows += cap
            manifest.append((a, b, count));cursor = b
        if cursor < end:manifest_holes.append((cursor, end))
    window_starts = [r[0] for r in manifest]; actual_counts = [0]*len(manifest)
    histogram = [0]*(len(edges)+1)
    counts = dict(input_rows=0, valid_rows=0, invalid_rows=0, out_of_range_rows=0,
                  time_reversals=0, normalized_duplicate_rows=0, same_millisecond_distinct_rows=0,
                  excessive_spread_rows=0, ticks_in_declared_closure=0, ticks_outside_manifest=0,
                  gap_candidates=0, closure_explained_gaps=0, unknown_session_gaps=0,
                  open_session_gap_candidates=0)
    examples = []; digest = sha256(); prior = None; seen_at_time = set()
    minimum = None; maximum = None; mean = 0.
    calendar_cursor = 0; longest_gap_ms = 0

    def example(kind, **fields):
        if len(examples) < max_examples:examples.append(dict(kind=kind, **fields))

    def gap(a, b):
        nonlocal calendar_cursor, longest_gap_ms
        longest_gap_ms = max(longest_gap_ms, b-a)
        if b-a <= gap_limit:return
        counts['gap_candidates'] += 1
        # Endpoints move monotonically; each calendar interval is visited once
        # apart from intervals crossing quote gaps.
        while calendar_cursor < len(calendar) and calendar[calendar_cursor][1] <= a:
            calendar_cursor += 1
        i = calendar_cursor; opened = 0; closed = 0
        while i < len(calendar) and calendar[i][0] < b:
            x, y, state = calendar[i]; duration = max(0, min(b,y)-max(a,x))
            if state == 'OPEN':opened += duration
            else:closed += duration
            i += 1
        unknown = b-a-opened-closed
        if opened > gap_limit:counts['open_session_gap_candidates'] += 1
        if unknown > 0:counts['unknown_session_gaps'] += 1
        if closed == b-a:counts['closure_explained_gaps'] += 1
        example('QUOTE_GAP', start_msc=a, end_msc=b, open_ms=opened, closed_ms=closed, unknown_ms=unknown)

    for row in ticks:
        counts['input_rows'] += 1
        if counts['input_rows'] > max_ticks:
            raise ValueError('Tick audit budget exceeded; split input, never certify a truncated prefix')
        try:
            if not isinstance(row, dict) or type(row.get('time_msc')) is not int:
                raise ValueError('Invalid timestamp')
            t = row['time_msc']; bid = _number(row.get('bid'), True); ask = _number(row.get('ask'), True)
            if bid > ask:raise ValueError('Crossed quote')
            spread = float((Decimal(str(ask))-Decimal(str(bid)))/Decimal(str(point)))
            if not isfinite(spread):raise ValueError('Spread overflow')
        except (ValueError, TypeError):
            counts['invalid_rows'] += 1;example('INVALID_QUOTE', row_index=counts['input_rows']-1)
            continue
        if not start <= t < end:
            counts['out_of_range_rows'] += 1;example('OUT_OF_RANGE', time_msc=t)
            continue
        digest.update((dumps([t,bid,ask], separators=(',', ':'))+'\n').encode())
        if prior is not None and t < prior:
            counts['time_reversals'] += 1;example('TIME_REVERSAL', time_msc=t)
        elif prior is None or t > prior:
            gap(start if prior is None else prior, t)
            prior = t;seen_at_time = set()
        key = (bid, ask)
        if prior == t:
            if key in seen_at_time:counts['normalized_duplicate_rows'] += 1
            elif seen_at_time:counts['same_millisecond_distinct_rows'] += 1
            if len(seen_at_time) >= 100000:raise ValueError('Same-millisecond audit budget exceeded')
            seen_at_time.add(key)
        counts['valid_rows'] += 1
        n = counts['valid_rows'];mean += (spread-mean)/n
        minimum = spread if minimum is None else min(minimum, spread)
        maximum = spread if maximum is None else max(maximum, spread)
        histogram[bisect_right(edges, spread)] += 1
        if spread > spread_limit:counts['excessive_spread_rows'] += 1
        ci = bisect_right(calendar_starts, t)-1
        if ci >= 0 and t < calendar[ci][1] and calendar[ci][2] == 'CLOSED':
            counts['ticks_in_declared_closure'] += 1
        wi = bisect_right(window_starts, t)-1
        if wi >= 0 and t < manifest[wi][1]:actual_counts[wi] += 1
        elif windows is not None:counts['ticks_outside_manifest'] += 1
    gap(start if prior is None else prior, end)
    mismatches = sum(actual != row[2] for actual,row in zip(actual_counts,manifest))
    issues = [name for name in ('invalid_rows','out_of_range_rows','time_reversals',
              'excessive_spread_rows','ticks_in_declared_closure','ticks_outside_manifest') if counts[name]]
    if manifest_holes:issues.append('MANIFEST_HOLES')
    if mismatches:issues.append('MANIFEST_COUNT_MISMATCH')
    if cap_windows:issues.append('SATURATED_WINDOWS')
    if counts['valid_rows'] == 0:issues.append('NO_VALID_QUOTES')
    review_reasons = []
    if windows is None:review_reasons.append('NO_WINDOW_MANIFEST')
    if sessions is None:review_reasons.append('NO_SESSION_CALENDAR')
    if counts['unknown_session_gaps']:review_reasons.append('UNEXPLAINED_SESSION_GAPS')
    if counts['open_session_gap_candidates']:review_reasons.append('OPEN_SESSION_GAP_CANDIDATES')
    if counts['normalized_duplicate_rows']:review_reasons.append('NORMALIZED_DUPLICATE_CANDIDATES')
    config = dict(audit_version=1, max_ticks=max_ticks, max_examples=max_examples,
                  manifest_provided=windows is not None, saturated_windows=cap_windows,
                  symbol=symbol, source=source, start=start, end=end,
                  broker_spec=[point,contract,digits], max_gap_ms=gap_limit,
                  max_spread_points=spread_limit, spread_edges=edges,
                  windows=manifest, calendar=calendar, session_source=session_source)
    return dict(status='BLOCKED_TICK_QUALITY'  if issues else 'REVIEW_TICK_QUALITY',
                symbol=symbol, source=source, requested_start_msc=start, requested_end_msc=end,
                broker_spec=dict(symbol=symbol,point=point,trade_contract_size=contract,digits=digits),
                counts=counts, issues=issues, review_reasons=review_reasons, examples=examples,
                audit_config_sha256=sha256(dumps(config,sort_keys=True,separators=(',', ':')).encode()).hexdigest(),
                manifest_provided=windows is not None, manifest_hole_count=len(manifest_holes),
                manifest_count_mismatches=mismatches, saturated_windows=cap_windows,
                session_source=session_source, normalized_quote_sha256=digest.hexdigest(),
                spread_points=dict(minimum=minimum, maximum=maximum, mean=mean if counts['valid_rows'] else None,
                    bin_edges=edges, bin_counts=histogram, threshold=spread_limit),
                max_gap_seconds=max_gap_seconds, observed_max_gap_seconds=longest_gap_ms/1000,
                completeness_verified=False,
                backtest_ready=False, execution_allowed=False,
                caveat='No calendar inferred. Long gaps can be quiet markets or missing data. Duplicate normalized quotes retain ambiguous raw events. Manifest coverage and this hash do not prove broker completeness.')


def audit_capture(capture, **kwargs):
    """Accept existing capture_days/capture_adaptive manifests without rewriting ticks."""
    if not isinstance(capture, dict) or 'ticks' not in capture or 'windows' not in capture:
        raise ValueError('Capture ticks and manifest required')
    return audit_ticks(capture['ticks'], symbol=capture['symbol'], windows=capture['windows'], **kwargs)
