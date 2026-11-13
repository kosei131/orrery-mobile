# SPDX-License-Identifier: GPL-3.0-only
"""Conservative raw-clock XAU barrier comparison, research-only.

All quote prices are scaled integers. Prices are observed touches, not fills.
Entry must have exactly one quote at its known timestamp; same-second entry
with multiple quotes is not treated as a uniquely determined entry price.
"""
from orrery_second_barrier_diagnostic import first_touch

MAX_QUOTES = 2_000_000


def compare_barriers(quotes, *, entry_utc_ms, side, stop, targets,
                     max_gap_ms=60_000):
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

    entry_quotes = [q for q in quotes if q[0] == entry_utc_ms]
    entry_status = ('ENTRY_UNOBSERVED' if not entry_quotes else
                    'ENTRY_SAME_SECOND_AMBIGUOUS' if len(entry_quotes) != 1 else
                    'ENTRY_QUOTE_OBSERVED')
    observations = []
    boundary = None
    if entry_status == 'ENTRY_QUOTE_OBSERVED':
        entry_index = next(i for i, q in enumerate(quotes) if q[0] == entry_utc_ms)
        previous = entry_utc_ms
        for ts, bid, ask in quotes[entry_index + 1:]:
            if ts < previous:
                boundary = 'CLOCK_REVERSAL'
                break
            if ts - previous > max_gap_ms:
                boundary = 'UNOBSERVED_GAP'
                break
            observations.append((ts, bid, ask))
            previous = ts
    results = {}
    for name, target in targets.items():
        observed = first_touch(observations, side, stop, target)
        status = observed['status']
        if entry_status != 'ENTRY_QUOTE_OBSERVED':
            status = 'CENSORED_' + entry_status
        elif status == 'UNRESOLVED':
            status = 'CENSORED_' + (boundary or ('DATA_END' if observations else 'NO_POST_ENTRY_QUOTES'))
        results[name] = dict(status=status, at_utc_ms=observed['at_utc_ms'],
                             intrasecond_order_verified=False,
                             broker_fill_verified=False, actual_profit_usd=None)
    return dict(status='RESEARCH_PRICE_TOUCH_ONLY', entry_utc_ms=entry_utc_ms,
                entry_status=entry_status, side=side, fixed_stop_scaled=stop,
                entry_quote_bid_scaled=entry_quotes[0][1] if len(entry_quotes)==1 else None,
                entry_quote_ask_scaled=entry_quotes[0][2] if len(entry_quotes)==1 else None,
                target_results=results, processed_post_entry_quotes=len(observations),
                boundary=boundary, quote_order_repaired=False,
                spread_already_in_bid_ask=True, actual_net_expectancy_r=None,
                account_return_pct=None, backtest_ready=False, execution_allowed=False)
