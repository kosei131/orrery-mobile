"""Experimental closed-bar structure definitions, not validated trading signals.
Input: positive OHLC and numeric UTC close_time; expected interval in seconds.
Reject missing/unfinished/misaligned bars. Call separately per symbol/timeframe.
"""
from math import isfinite


def detect(bars, *, as_of, interval, left=2, right=2):
    if any(type(x) not in (int, float) or not isfinite(x) for x in (as_of, interval)) or interval <= 0:
        raise ValueError('Invalid clock/interval')
    if any(type(x) is not int or x < 1 for x in (left, right)):
        raise ValueError('Positive pivot windows required')
    for i, b in enumerate(bars):
        if any(type(b.get(k)) not in (int, float) or not isfinite(b[k]) for k in ('open','high','low','close','close_time')):
            raise ValueError('Invalid OHLC/time')
        if not 0 < b['low'] <= min(b['open'], b['close']) <= max(b['open'], b['close']) <= b['high']:
            raise ValueError('Invalid OHLC range')
        if b['close_time'] > as_of:
            raise ValueError('Unfinished bar')
        if i and b['close_time'] - bars[i-1]['close_time'] != interval:
            raise ValueError('Missing or unordered bars; segment sessions first')
    pivots, events = [], []
    highs, lows, consumed = [], [], set()
    trend = 'RANGE'
    for i, b in enumerate(bars):
        # Only pivots confirmed BEFORE this close are eligible references.
        for kind, history in (('HIGH', highs), ('LOW', lows)):
            if not history:
                continue
            ref = history[-1]
            key = (kind, ref['index'])
            if key in consumed:
                continue
            level = ref['price']
            sweep = b['high'] > level and b['close'] < level if kind == 'HIGH' else b['low'] < level and b['close'] > level
            broken = b['close'] > level if kind == 'HIGH' else b['close'] < level
            if not (sweep or broken):
                continue
            direction = 'UP' if kind == 'HIGH' else 'DOWN'
            label = 'SWEEP' if sweep else ('CHoCH' if trend in ('UP','DOWN') and direction != trend else 'BOS' if direction == trend else 'BREAK')
            event = dict(index=i, known_at=b['close_time'], kind=label, direction=direction,
                         reference=ref.copy(), price=level, poi=None)
            if broken:
                # POI hypothesis: full wick range of last opposite candle since pivot.
                for j in range(i-1, ref['index']-1, -1):
                    c = bars[j]
                    opposite = c['close'] < c['open'] if direction == 'UP' else c['close'] > c['open']
                    if opposite:
                        event['poi'] = dict(index=j, low=c['low'], high=c['high'], known_at=b['close_time'])
                        break
            events.append(event)
            consumed.add(key)  # One event per reference; no repeated sweeps counted.
        p = i-right
        if p >= left:
            window = bars[p-left:i+1]
            for kind, field, history in (('HIGH','high',highs),('LOW','low',lows)):
                value = bars[p][field]
                others = [c[field] for j,c in enumerate(window) if j != left]
                if (value > max(others) if kind == 'HIGH' else value < min(others)):
                    pivot = dict(kind=kind,index=p,price=value,known_at=b['close_time'])
                    pivots.append(pivot); history.append(pivot)
        if len(highs)>=2 and len(lows)>=2:
            dh=highs[-1]['price']-highs[-2]['price']; dl=lows[-1]['price']-lows[-2]['price']
            trend='UP' if dh>0 and dl>0 else 'DOWN' if dh<0 and dl<0 else 'RANGE'
    return dict(pivots=pivots,events=events,trend=trend)
