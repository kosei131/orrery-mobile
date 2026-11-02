"""Independent OHLC bracket audit, not an AMD port or executable fill model."""
from decimal import Decimal, InvalidOperation


def _price(value):
    if isinstance(value,bool):raise ValueError('Finite positive price required')
    try:p=Decimal(str(value))
    except (InvalidOperation,ValueError):raise ValueError('Finite positive price required') from None
    if not p.is_finite() or not 0<p<=Decimal('1e12'):raise ValueError('Finite positive price required')
    return p


def audit_bar(*, side, entry, stop, target, bar):
    """One subsequent bar for an already-open fixed bracket.

    Open-price fills are a declared reference assumption, never broker fills.
    Without an opening gap, both touches leave the order unresolved.
    Caller must establish clocks, feed, bid/ask and prior position survival.
    """
    if side not in ('BUY','SELL'):raise ValueError('BUY or SELL required')
    if not isinstance(bar,dict) or set(bar)!={'open','high','low','close'}:raise ValueError('Exact OHLC required')
    e,s,t=map(_price,(entry,stop,target));b={k:_price(v) for k,v in bar.items()}
    if not b['low']<=min(b['open'],b['close'])<=max(b['open'],b['close'])<=b['high']:
        raise ValueError('Invalid OHLC')
    if not (s<e<t if side=='BUY' else t<e<s):raise ValueError('Positive structural bracket required')
    sign=Decimal(1 if side=='BUY' else -1);risk=abs(e-s)
    stop_touch=b['low']<=s if side=='BUY' else b['high']>=s
    target_touch=b['high']>=t if side=='BUY' else b['low']<=t
    gap_stop=b['open']<=s if side=='BUY' else b['open']>=s
    gap_target=b['open']>=t if side=='BUY' else b['open']<=t
    price=None;ambiguous=False;stop_first=None
    if gap_stop:status='OPEN_AT_OR_BEYOND_STOP';price=b['open']
    elif gap_target:status='OPEN_AT_OR_BEYOND_TARGET';price=b['open']
    elif stop_touch and target_touch:
        status='AMBIGUOUS_INTRABAR';ambiguous=True;stop_first=-1.0
    elif stop_touch:status='STOP_ONLY';price=s
    elif target_touch:status='TARGET_ONLY';price=t
    else:status='NO_BARRIER_TOUCH'
    return dict(status=status,both_touched=bool(stop_touch and target_touch),
        intrabar_order_unknown=ambiguous,reference_exit_price=float(price) if price is not None else None,
        gross_reference_r=float(sign*(price-e)/risk) if price is not None else None,
        stop_first_sensitivity_r=stop_first,open_fill_assumption=bool(gap_stop or gap_target),
        fill_verified=False,net_expectancy_r=None,actual_profit_usd=None,execution_allowed=False)
