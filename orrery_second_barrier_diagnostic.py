# SPDX-License-Identifier: GPL-3.0-only
"""Read-only quote timestamp diagnostic for research; never treats ties as ordered fills."""

def first_touch(quotes, side, stop, target):
    if side not in ('BUY', 'SELL') or not (0 < stop < target if side == 'BUY' else 0 < target < stop):
        raise ValueError('Invalid side or barriers')
    prev = None
    group = []
    def classify(rows):
        prices = [bid if side == 'BUY' else ask for _, bid, ask in rows]
        sl = any(p <= stop if side == 'BUY' else p >= stop for p in prices)
        tp = any(p >= target if side == 'BUY' else p <= target for p in prices)
        if sl and tp: return 'AMBIGUOUS_SAME_SECOND'
        if sl: return 'STOP_OBSERVED'
        if tp: return 'TARGET_OBSERVED'
        return None
    for tick in quotes:
        if len(tick) != 3: raise ValueError('Quote shape')
        ts, bid, ask = tick
        if any(type(x) is not int for x in tick) or ts < 0 or ts % 1000 or bid <= 0 or ask < bid:
            raise ValueError('Invalid whole-second bid/ask')
        if prev is not None and ts < prev: raise ValueError('Clock reversal: no inferred chronology')
        if prev is not None and ts != prev:
            result = classify(group)
            if result: return {'status':result,'at_utc_ms':prev,'actual_profit_usd':None,'execution_allowed':False}
            group = []
        group.append(tick)
        prev = ts
    result = classify(group) if group else None
    return {'status':result or 'UNRESOLVED','at_utc_ms':prev if result else None,'actual_profit_usd':None,'execution_allowed':False}
