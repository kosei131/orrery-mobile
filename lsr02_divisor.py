"""Published range/2.6 price-level variant; no profit target or order API.
Formula reference: marketscore.io/blog/2-6-the-secret-unveiled
This does not authenticate the user's original author/indicator definition.
"""
from math import isfinite


def levels(*, low, high, known_at, as_of):
    if (any(type(v) not in (int, float) or not isfinite(v)
            for v in (low, high, known_at, as_of))
            or not 0 < low < high or not 0 <= known_at <= as_of):
        raise ValueError('Completed, already-known positive range required')
    offset = (high-low)/2.6
    return dict(status='PUBLIC_VARIANT_RESEARCH', divisor=2.6,
                low=low, high=high, known_at=known_at, offset=offset,
                buy_pullback_level=high-offset, sell_pullback_level=low+offset,
                range_fraction=1/2.6,
                author_match='UNVERIFIED', execution_allowed=False)
