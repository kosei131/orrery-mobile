"""Audit supplied TradingView ZIP bytes; no extraction, price repair or orders.

Nominal-clock aggregation is a consistency check, not feed authentication or
a session calendar. Incomplete child windows remain unverified.
"""
import argparse
import csv
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from io import BytesIO, StringIO
import json
from pathlib import Path
import zipfile

FRAMES = {'5m': 300, '15m': 900, '4h': 14400}
MEMBERS = {'manifest.json', 'README.txt', *(f'{f}.csv' for f in FRAMES),
           *(f'{f}_time_gaps.csv' for f in FRAMES)}
FIELDS = ['timestamp_unix_utc', 'datetime_utc', 'open', 'high', 'low', 'close', 'volume']


def _utc(value):
    if not isinstance(value, str) or len(value) > 100:
        raise ValueError('Bounded explicit UTC timestamp required')
    t = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if t.tzinfo is None or t.utcoffset().total_seconds() != 0 or t.microsecond:
        raise ValueError('Whole UTC seconds required')
    at = int(t.timestamp())
    if at < 0:
        raise ValueError('Nonnegative UTC required')
    return at


def _iso(at):
    return datetime.fromtimestamp(at, timezone.utc).isoformat().replace('+00:00', 'Z')


def _decimal(cell):
    if not isinstance(cell, str) or not 0 < len(cell) <= 100 or cell != cell.strip():
        raise ValueError('Bounded decimal cell required')
    try:
        value = Decimal(cell)
    except InvalidOperation:
        raise ValueError('Invalid number') from None
    if not value.is_finite() or abs(value) > Decimal('1e12'):
        raise ValueError('Invalid numeric range')
    return value


def _bars(raw, interval, cutoff):
    reader = csv.reader(StringIO(raw.decode('utf-8-sig'), newline=''), strict=True)
    if next(reader, None) != FIELDS:
        raise ValueError('Exact export columns required')
    rows = []; gaps = []; shifts = []; previous = None; blank_lines = 0
    for cells in reader:
        if not cells:
            blank_lines += 1; continue
        if len(cells) != len(FIELDS) or len(rows) >= 200000:
            raise ValueError('Ragged CSV or row budget exceeded')
        record = dict(zip(FIELDS, cells)); n = _decimal(record['timestamp_unix_utc'])
        if n != n.to_integral_value() or int(n) != _utc(record['datetime_utc']):
            raise ValueError('UNIX and ISO clocks disagree')
        at = int(n)
        if at + interval > cutoff or (previous is not None and at <= previous):
            raise ValueError('Unconfirmed, duplicate or unordered bar')
        prices = {k: _decimal(record[k]) for k in ('open', 'high', 'low', 'close')}
        volume = _decimal(record['volume'])
        if (volume < 0 or not 0 < prices['low'] <= min(prices['open'], prices['close'])
                <= max(prices['open'], prices['close']) <= prices['high']):
            raise ValueError('Invalid OHLCV')
        if previous is not None and at - previous != interval:
            item = dict(after_open_utc=_iso(previous), before_open_utc=_iso(at),
                        delta_seconds=at - previous)
            gaps.append(item)
            if (at - previous) % interval:
                shifts.append(item)
        rows.append(dict(at=at, **prices)); previous = at
    if not rows:
        raise ValueError('History required')
    return rows, dict(rows=len(rows), blank_lines=blank_lines, first_open_utc=_iso(rows[0]['at']),
        last_open_utc=_iso(rows[-1]['at']), nominal_last_close_utc=_iso(rows[-1]['at'] + interval),
        non_nominal_intervals=len(gaps), non_grid_intervals=len(shifts),
        non_grid_examples=shifts[:20], session_calendar_verified=False,
        raw_sha256=sha256(raw).hexdigest())


def _aggregate_check(child, parent, child_step, parent_step, window):
    index = {r['at']: r for r in child}; checked = 0; outside = 0; incomplete = 0; mismatches = []
    for p in parent:
        at = p['at']
        if at < window[0] or at + parent_step > window[1]:
            outside += 1; continue
        small = [index.get(t) for t in range(at, at + parent_step, child_step)]
        if any(c is None for c in small):
            incomplete += 1; continue
        checked += 1
        expected = dict(open=small[0]['open'], high=max(c['high'] for c in small),
                        low=min(c['low'] for c in small), close=small[-1]['close'])
        fields = [k for k in expected if expected[k] != p[k]]
        if fields:
            mismatches.append(dict(parent_open_utc=_iso(at), fields=fields,
                aggregate_ohlc={k: str(v) for k, v in expected.items()},
                supplied_ohlc={k: str(p[k]) for k in expected}))
    return dict(checked_complete_parent_bars=checked, outside_window=outside,
        incomplete_child_windows=incomplete, mismatch_count=len(mismatches),
        mismatch_examples=mismatches[:20], nominal_interval_assumption=True,
        all_parent_bars_verified=bool(checked) and not (outside or incomplete or mismatches))


def audit_bundle(raw):
    if not isinstance(raw, bytes) or not 0 < len(raw) <= 16 * 1024 * 1024:
        raise ValueError('Bounded ZIP bytes required')
    # No paths from the upload are ever extracted or executed.
    with zipfile.ZipFile(BytesIO(raw)) as z:
        infos = z.infolist(); names = [i.filename for i in infos]
        if len(names) != len(set(names)) or set(names) != MEMBERS:
            raise ValueError('Exact unique bundle members required')
        if (any(i.file_size > 32 * 1024 * 1024 or i.flag_bits & 1 for i in infos)
                or sum(i.file_size for i in infos) > 100 * 1024 * 1024):
            raise ValueError('Archive size or encryption unsupported')
        files = {name: z.read(name) for name in names}
    if len(files['manifest.json']) > 65536:
        raise ValueError('Manifest budget exceeded')
    manifest = json.loads(files['manifest.json']); cutoff = _utc(manifest['cutoff_utc'])
    reports = manifest.get('reports')
    if not isinstance(reports, list) or len(reports) != 3 or any(not isinstance(r, dict) for r in reports):
        raise ValueError('Three manifest frame reports required')
    if {r.get('interval') for r in reports} != set(FRAMES):
        raise ValueError('Unique manifest intervals required')
    if any(r.get('symbol') != 'OANDA:XAUUSD' or r.get('provider') != 'OANDA via TradingView MCP' for r in reports):
        raise ValueError('Explicit single OANDA:XAUUSD source required')
    bars = {}; audits = {}; manifest_mismatches = []
    for frame, seconds in FRAMES.items():
        bars[frame], audits[frame] = _bars(files[frame + '.csv'], seconds, cutoff)
        declared = next(r for r in reports if r['interval'] == frame); a = audits[frame]
        for key in ('first_open_utc', 'last_open_utc', 'nominal_last_close_utc'):
            if _utc(declared[key]) != _utc(a[key]):
                manifest_mismatches.append(dict(frame=frame, field=key))
        if type(declared.get('saved')) is not int or declared['saved'] != a['rows']:
            manifest_mismatches.append(dict(frame=frame, field='saved'))
    start = max(bars[f][0]['at'] for f in FRAMES)
    end = min(bars[f][-1]['at'] + FRAMES[f] for f in FRAMES)
    common = dict(start_open_utc=_iso(start) if start < end else None,
                  end_nominal_close_utc=_iso(end) if start < end else None,
                  elapsed_seconds=max(0, end - start))
    comparisons = {}; common_comparisons = {}
    for child, parent in (('5m', '15m'), ('15m', '4h'), ('5m', '4h')):
        key = child + '_to_' + parent
        window = (bars[child][0]['at'], bars[child][-1]['at'] + FRAMES[child])
        comparisons[key] = _aggregate_check(bars[child], bars[parent], FRAMES[child], FRAMES[parent], window)
        common_comparisons[key] = _aggregate_check(bars[child], bars[parent], FRAMES[child], FRAMES[parent], (start, end))
    mismatch = bool(manifest_mismatches or any(c['mismatch_count'] for c in comparisons.values()))
    return dict(status='REVIEW_REQUIRED_NOMINAL_OHLC_MISMATCH' if mismatch else 'AUDITED_SESSION_AND_EXECUTION_DATA_REQUIRED',
        zip_sha256=sha256(raw).hexdigest(), source_declared='OANDA:XAUUSD via TradingView MCP',
        cutoff_utc=_iso(cutoff), frames=audits, manifest_mismatches=manifest_mismatches,
        common_range=common, nominal_aggregation=comparisons, common_range_nominal_aggregation=common_comparisons,
        source_authenticated=False, chart_standardness_verified=False, session_calendar_verified=False,
        broker_bid_ask_available=False, historical_usd_valuation_available=False,
        actual_profit_usd=None, candidate_replay_allowed=False, six_month_backtest_complete=False,
        execution_allowed=False,
        limitation='Complete nominal child windows only. Session/DST/partial bars and source revisions need separate evidence. No interpolation, repairs, strategy changes or fills.')


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('zip', type=Path); p.add_argument('--output', type=Path, required=True)
    a = p.parse_args(argv)
    with a.zip.open('rb') as f:
        raw = f.read(16 * 1024 * 1024 + 1)
    result = audit_bundle(raw)
    with a.output.open('x', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2); f.write('\n')
    print(result['status'])
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
