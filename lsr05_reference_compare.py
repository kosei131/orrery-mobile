# SPDX-License-Identifier: GPL-3.0-only
"""Compare supplied HalfTrend exports; never certify their authenticity or edge."""
from hashlib import sha256
from json import dumps
from math import isfinite
import re

from lsr05_halftrend import calculate, SOURCE_SHA256

FIELDS = ('at', 'state', 'line', 'atr', 'atr_high', 'atr_low', 'signal', 'ready')
NUMERIC = ('line', 'atr', 'atr_high', 'atr_low')
BAR_FIELDS = ('close_time', 'open', 'high', 'low', 'close')


def reference_sha256(reference):
    """Canonical JSON pin, not the SHA of a raw CSV/JSON file."""
    return sha256(dumps(reference, sort_keys=True, separators=(',', ':'),
                        allow_nan=False).encode('utf-8')).hexdigest()


def _number(value):
    return type(value) in (int, float) and isfinite(value)


def compare_reference(bars, reference, *, expected_reference_sha256, symbol, data_source,
                      as_of, interval, amplitude, channel_deviation, absolute_tolerance,
                      calendar_evidence=None, expected_calendar_sha256=None):
    """Recompute locally and compare every supplied external row without a time shift.

    A reference must describe its full calculation history, not just an export
    window after hidden warmup. Declared provenance is retained, never authenticated.
    No I/O, trading, parameter selection or edits to the core strategy.
    """
    if symbol not in ('XAUUSD', 'USDJPY') or not isinstance(data_source, str) or not 0 < len(data_source) <= 400:
        raise ValueError('Explicit symbol and feed required')
    if not _number(absolute_tolerance) or not 0 <= absolute_tolerance <= .01:
        raise ValueError('Predeclared absolute price tolerance in [0, 0.01] required')
    if not isinstance(expected_reference_sha256, str) or not re.fullmatch('[0-9a-f]{64}', expected_reference_sha256):
        raise ValueError('Retained canonical reference pin required')
    if not isinstance(reference, dict) or reference_sha256(reference) != expected_reference_sha256:
        raise ValueError('Reference changed or is not pinned')
    keys = {'schema_version', 'platform', 'implementation_label', 'implementation_sha256',
            'source_sha256', 'symbol', 'data_source', 'captured_at', 'interval', 'amplitude',
            'channel_deviation', 'calendar_sha256', 'bars', 'rows'}
    if set(reference) != keys or type(reference['schema_version']) is not int or reference['schema_version'] != 1:
        raise ValueError('Explicit reference schema version 1 required')
    if reference['platform'] not in ('TRADINGVIEW', 'MT5'):
        raise ValueError('Declared external platform required')
    if not isinstance(reference['implementation_label'], str) or not 0 < len(reference['implementation_label']) <= 400:
        raise ValueError('Reference implementation label required')
    for field in ('implementation_sha256', 'source_sha256'):
        if not isinstance(reference[field], str) or not re.fullmatch('[0-9a-f]{64}', reference[field]):
            raise ValueError('Reference source/code fingerprints required')
    if not _number(as_of) or not _number(reference['captured_at']) or not 0 <= reference['captured_at'] <= as_of:
        raise ValueError('Reference capture clock outside comparison horizon')
    local = calculate(bars, as_of=as_of, interval=interval, amplitude=amplitude,
                      channel_deviation=channel_deviation, enabled=True,
                      calendar_evidence=calendar_evidence, expected_calendar_sha256=expected_calendar_sha256,
                      symbol=symbol, data_source=data_source)
    result = dict(status='BLOCKED_REFERENCE_CONTEXT', reference_sha256=expected_reference_sha256,
                  local_input_sha256=local.get('input_sha256'), platform=reference['platform'],
                  implementation_label=reference['implementation_label'],
                  implementation_sha256=reference['implementation_sha256'],
                  reference_source_sha256=reference['source_sha256'],
                  captured_at=reference['captured_at'], absolute_tolerance=absolute_tolerance,
                  comparison_scope='SUPPLIED_FULL_HISTORY_ONLY', independent_reference_verified=False,
                  tradingview_parity_verified=False, mt5_parity_verified=False,
                  nonrepainting_verified=False, market_edge_verified=False, execution_allowed=False)
    problems = []
    for name, value in dict(symbol=symbol, data_source=data_source, interval=interval,
                            amplitude=amplitude, channel_deviation=channel_deviation,
                            source_sha256=SOURCE_SHA256, calendar_sha256=expected_calendar_sha256).items():
        if reference[name] != value or (type(value) is int and type(reference[name]) is not int):
            problems.append(name)
    if local['status'] != 'HALFTREND_RESEARCH_ONLY':
        problems.append('local_history_not_ready')
    other_bars = reference['bars']
    if not isinstance(other_bars, list) or len(other_bars) > 10000:
        raise ValueError('Bounded reference input bars required')
    for bar in other_bars:
        if not isinstance(bar, dict) or bar.get('is_closed', True) is not True or any(not _number(bar.get(k)) for k in BAR_FIELDS):
            raise ValueError('Finite confirmed reference OHLC required')
    if [{k: b[k] for k in BAR_FIELDS} for b in other_bars] != [{k: b[k] for k in BAR_FIELDS} for b in bars]:
        problems.append('input_bars_or_history_seed')
    if any(b['close_time'] > reference['captured_at'] for b in other_bars):
        raise ValueError('Reference captured before its bars closed')
    if problems:
        return dict(result, context_mismatches=problems)
    rows = reference['rows']
    if not isinstance(rows, list) or len(rows) > 10000:
        raise ValueError('Bounded reference output required')
    previous = None
    for row in rows:
        if not isinstance(row, dict) or set(row) != set(FIELDS):
            raise ValueError('Explicit normalized reference output fields required')
        if not _number(row['at']) or row['at'] < 0 or row['at'] > reference['captured_at'] or (previous is not None and row['at'] <= previous):
            raise ValueError('Unique ordered reference close clocks required')
        if row['state'] not in ('UP', 'DOWN') or row['signal'] not in (None, 'BUY', 'SELL') or type(row['ready']) is not bool:
            raise ValueError('Reference state/signal/readiness types invalid')
        if not _number(row['line']) or any(row[k] is not None and not _number(row[k]) for k in NUMERIC):
            raise ValueError('Finite reference prices or explicit missing ATR required')
        previous = row['at']
    expected = {r['at']: r for r in local['rows']}
    supplied = {r['at']: r for r in rows}
    missing = sorted(expected.keys() - supplied.keys())
    extra = sorted(supplied.keys() - expected.keys())
    counts = {k: 0 for k in FIELDS if k != 'at'}
    maxima = {k: None for k in NUMERIC}
    examples = []
    for at in sorted(expected.keys() & supplied.keys()):
        a, b = expected[at], supplied[at]
        for name in counts:
            left, right = a[name], b[name]
            if name in NUMERIC and left is not None and right is not None:
                delta = abs(left - right)
                # Finite values can still overflow on subtraction.
                if not isfinite(delta):
                    raise ValueError('Reference difference overflow')
                maxima[name] = delta if maxima[name] is None else max(maxima[name], delta)
                mismatch = delta > absolute_tolerance
            else:
                mismatch = left != right
            if mismatch:
                counts[name] += 1
                if len(examples) < 100:
                    examples.append(dict(at=at, field=name, local=left, reference=right))
    mismatch = bool(missing or extra or any(counts.values()))
    return dict(result, status='REFERENCE_MISMATCH' if mismatch else 'REFERENCE_SAMPLE_MATCHED_NOT_VERIFIED',
                local_bars=len(expected), reference_bars=len(supplied),
                compared_bars=len(expected.keys() & supplied.keys()),
                missing_bars=len(missing), extra_bars=len(extra),
                missing_close_examples=missing[:100], extra_close_examples=extra[:100],
                mismatch_counts=counts, maximum_absolute_differences=maxima, mismatch_examples=examples,
                caveat='Caller-supplied export and fingerprints are not authenticated. A sample match is not external parity, non-repainting or profitability proof.')
