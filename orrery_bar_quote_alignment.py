"""Offline comparison of confirmed standard bars with observed quote OHLC."""
from decimal import Decimal
from math import isfinite

from orrery_tradingview_study import INTERVALS, normalize

FIELDS = ('open', 'high', 'low', 'close')


def audit_session(raw_csvs, settings, quotes, *, start_s, end_s, max_gap_msc,
                  quote_symbol, quote_source, price_tolerance):
    """Audit whole bars in one declared session; retain missing bars as failures."""
    if (type(start_s) is not int or type(end_s) is not int
            or not 0 <= start_s < end_s <= settings['as_of_s']
            or type(max_gap_msc) is not int or not 1 <= max_gap_msc <= 60000):
        raise ValueError('Explicit confirmed session and quote gap bound required')
    basis = settings['price_basis']
    if (settings['chart_type'] != 'STANDARD' or basis not in ('BID', 'ASK', 'MID')
            or quote_symbol not in ('XAUUSD', 'USDJPY')
            or quote_symbol != settings['symbol'] or not quote_source
            or quote_source != settings['data_source']):
        raise ValueError('Matching symbol, source labels and a supported quote basis required')
    if (type(price_tolerance) not in (int, float) or not isfinite(price_tolerance)
            or price_tolerance < 0):
        raise ValueError('Explicit finite absolute price tolerance required')
    tolerance = Decimal(str(price_tolerance))
    if set(raw_csvs) != set(INTERVALS):
        raise ValueError('M5 M15 H4 exports required')

    frames = {}
    for frame, seconds in INTERVALS.items():
        bars, provenance = normalize(raw_csvs[frame], timeframe=frame, settings=settings)
        # Use the exported grid phase, including when the first in-session bar is missing.
        first = start_s + (provenance['first_open_s'] - start_s) % seconds
        expected = range(first + seconds, end_s + 1, seconds)
        reference = {bar['close_time']: bar for bar in bars if bar['close_time'] in expected}
        frames[frame] = (seconds, expected, reference, {}, provenance['raw_sha256'])

    previous = start_s * 1000
    seen = 0
    first_gap = None
    for quote in quotes:
        clock = quote['time_msc']
        bid, ask = quote['bid'], quote['ask']
        if (type(clock) is not int or not previous <= clock < end_s * 1000
                or any(type(v) not in (int, float) or not isfinite(v) for v in (bid, ask))
                or not 0 < bid <= ask):
            raise ValueError('Ordered in-session Bid/Ask observations required')
        if first_gap is None and clock - previous > max_gap_msc:
            first_gap = (previous, clock)
        previous = clock
        seen += 1
        bid, ask = Decimal(str(bid)), Decimal(str(ask))
        price = {'BID': bid, 'ASK': ask, 'MID': (bid + ask) / 2}[basis]
        for seconds, expected, _, observed, _ in frames.values():
            close = expected.start + ((clock // 1000 - expected.start) // seconds + 1) * seconds
            if close not in expected:
                continue
            opening, high, low, _ = observed.get(close, (price,) * 4)
            observed[close] = opening, max(high, price), min(low, price), price

    if first_gap is None and (not seen or end_s * 1000 - previous > max_gap_msc):
        first_gap = (previous, end_s * 1000)
    results = {}
    for frame, (_, expected, reference, observed, digest) in frames.items():
        mismatch = sum(
            any(abs(value - Decimal(str(reference[close][key]))) > tolerance
                for key, value in zip(FIELDS, observed[close]))
            for close in reference.keys() & observed.keys()
        )
        results[frame] = dict(expected=len(expected), missing_bars=len(expected)-len(reference),
                              missing_quote_bars=len(expected)-len(observed),
                              mismatched_bars=mismatch, raw_sha256=digest)
    aligned = first_gap is None and all(
        row['expected'] and not (row['missing_bars'] or row['missing_quote_bars']
                                 or row['mismatched_bars']) for row in results.values())
    return dict(aligned=aligned, frames=results, first_gap_msc=first_gap,
                quote_count=seen, start_s=start_s, end_s=end_s, price_basis=basis,
                max_gap_msc=max_gap_msc, price_tolerance=price_tolerance,
                feed_identity_verified=False, execution_allowed=False)
