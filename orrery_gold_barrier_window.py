# SPDX-License-Identifier: GPL-3.0-only
"""Conservative fixed-entry XAU Bid/Ask barrier comparison, research only.

No fills, entry inference, interpolation or chronological repair. Quotes must
be raw-order, whole-second integer-scaled and validated before any result.
Every candidate must provide its entry time/barriers BEFORE evaluation.
"""
from orrery_second_barrier_diagnostic import first_touch

MAX_QUOTES = 2_000_000


def compare_barriers(quotes, *, entry_utc_ms, side, stop, targets,
                     max_gap_ms=60_000):
    """Compare fixed targets, censoring at first raw clock discontinuity."""
    if type(entry_utc_ms) is not int or entry_utc_ms < 0 or entry_utc_ms % 1000:
        raise ValueError('Whole-second fixed entry clock required')
    if type(max_gap_ms) is not int or not 0 < max_gap_ms <= 60_000:
        raise ValueError('Bounded maximum gap required')
    if side not in ('BUY', 'SELL') or type(stop) is not int or stop <= 0:
        raise ValueError('Fixed side and stop required')
    if not isinstance(targets, dict) or not 1 <= len(targets) <= 12:
        raise ValueError('One to twelve named targets required')
    if not isinstance(quotes, (list, tuple)) or len(quotes) > MAX_QUOTES:
        raise ValueError('Bounded raw-order quote sequence required')
    for name, target in targets.items():
        if (not isinstance(name, str) or not name or len(name) > 64
            or type(target) is not int or target <= 0
            or (side == 'BUY' and target <= stop)
            or (side == 'SELL' and target >= stop)):
            raise ValueError('Named directionally valid barriers required')
    for quote in quotes:
        if (not isinstance(quote, (list, tuple)) or len(quote) != 3
            or any(type(v) is not int for v in quote)):
            raise ValueError('Exact integer quote tuple required')
        ts, bid, ask = quote
        if ts < 0 or ts % 1000 or bid <= 0 or ask < bid:
            raise ValueError('Invalid whole-second Bid/Ask quote')
    observations = []
    previous = None
    boundary = None
    started = False
    for ts, bid, ask in quotes:
        if previous is not None:
            if ts < previous:
                boundary = 'CLOCK_REVERSAL'
                break
            if ts - previous > max_gap_ms:
                boundary = 'UNOBSERVED_GAP'
                break
        previous = ts
        if ts <= entry_utc_ms:
            continue
        started = True
        observations.append((ts, bid, ask))
    results = {}
    for name, target in targets.items():
        observed = first_touch(observations, side, stop, target)
        status = observed['status']
        if status == 'UNRESOLVED':
            status = 'CENSORED_' + (boundary or ('DATA_END' if started else 'NO_POST_ENTRY_QUOTES'))
        results[name] = dict(status=status, at_utc_ms=observed['at_utc_ms'],
                             intrasecond_order_verified=False,
                             broker_fill_verified=False, actual_profit_usd=None)
    return dict(status='RESEARCH_PRICE_TOUCH_ONLY', entry_utc_ms=entry_utc_ms,
                side=side, fixed_stop_scaled=stop, target_results=results,
                processed_post_entry_quotes=len(observations), boundary=boundary,
                quote_order_repaired=False, spread_already_in_bid_ask=True,
                actual_net_expectancy_r=None, account_return_pct=None,
                backtest_ready=False, execution_allowed=False)
