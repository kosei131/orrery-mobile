"""Independent Ichimoku/confirmed horizontal-level research annotations.
Not a reconstruction of any trader's proprietary '2.6' rule. No orders.
"""
from lsr02_structure import detect


def analyze(bars, *, as_of, interval, tenkan, kijun, span_b, shift,
            left=2, right=2):
    """Visible cloud at index i uses raw spans from i-shift, never i+shift.

    shift is an explicit integer index offset, not a platform-inclusive count.
    Horizontal breaks use pivots known BEFORE the current candle closed.
    """
    if (any(type(v) is not int or v < 1 for v in (tenkan, kijun, span_b, shift))
            or not tenkan <= kijun <= span_b):
        raise ValueError('Explicit ordered positive Ichimoku periods required')
    detect(bars, as_of=as_of, interval=interval, left=left, right=right)
    result = dict(status='UNKNOWN', reason='INSUFFICIENT_OR_STALE_HISTORY',
                  at=bars[-1]['close_time'] if bars else None,
                  parameters=dict(tenkan=tenkan, kijun=kijun, span_b=span_b, shift=shift),
                  tenkan=None, kijun=None, kijun_slope=None,
                  cloud=None, cloud_location='UNKNOWN', cloud_break=None,
                  nearest_support=None, nearest_resistance=None,
                  horizontal_breaks=[], execution_allowed=False,
                  rule_2_6_status='UNRESOLVED_AUTHOR_DEFINITION',
                  attribution='INDEPENDENT_PUBLIC_INDICATOR_RESEARCH')
    if not bars or as_of-bars[-1]['close_time'] >= interval:
        return result
    i = len(bars)-1

    def midpoint(end, period):
        if end < period-1:
            return None
        window = bars[end-period+1:end+1]
        # Half-sum avoids overflow from summing two very large positive prices.
        return max(b['high'] for b in window)/2+min(b['low'] for b in window)/2

    def cloud(index):
        source = index-shift
        t, k, b = (midpoint(source, p) for p in (tenkan, kijun, span_b))
        if None in (t, k, b):
            return None
        a = t/2+k/2
        return dict(span_a=a, span_b=b, low=min(a, b), high=max(a, b),
                    source_at=bars[source]['close_time'],
                    visible_at=bars[index]['close_time'])

    result['tenkan'] = midpoint(i, tenkan)
    result['kijun'] = midpoint(i, kijun)
    previous_kijun = midpoint(i-1, kijun)
    if previous_kijun is not None:
        delta = result['kijun']-previous_kijun
        result['kijun_slope'] = 'UP' if delta > 0 else 'DOWN' if delta < 0 else 'FLAT'
    current, previous = cloud(i), cloud(i-1)
    result['cloud'] = current
    close = bars[-1]['close']
    if current is not None:
        result.update(status='OBSERVED', reason='ANNOTATION_ONLY')
        result['cloud_location'] = ('ABOVE' if close > current['high'] else
                                    'BELOW' if close < current['low'] else 'INSIDE')
        if previous is not None:
            old_close = bars[-2]['close']
            if old_close <= previous['high'] and close > current['high']:
                result['cloud_break'] = 'UP'
            elif old_close >= previous['low'] and close < current['low']:
                result['cloud_break'] = 'DOWN'
    # Current-close pivot confirmation may be used as a level next candle only.
    pivots = detect(bars[:-1], as_of=as_of, interval=interval,
                    left=left, right=right)['pivots']
    supports = [p for p in pivots if p['kind'] == 'LOW' and p['price'] < close]
    resistances = [p for p in pivots if p['kind'] == 'HIGH' and p['price'] > close]
    result['nearest_support'] = max(supports, key=lambda p: p['price']) if supports else None
    result['nearest_resistance'] = min(resistances, key=lambda p: p['price']) if resistances else None
    if len(bars) >= 2:
        old_close = bars[-2]['close']
        for kind, direction in (('HIGH', 'UP'), ('LOW', 'DOWN')):
            refs = [p for p in pivots if p['kind'] == kind]
            if not refs:
                continue
            ref = refs[-1]
            broken = (old_close <= ref['price'] < close if direction == 'UP' else
                      old_close >= ref['price'] > close)
            if broken:
                result['horizontal_breaks'].append(dict(direction=direction,
                    price=ref['price'], reference_known_at=ref['known_at'],
                    observed_at=bars[-1]['close_time']))
    return result
