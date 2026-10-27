"""Offline exit-policy comparison. Hypothetical fills, no market/order APIs."""
from math import isfinite
from lsr02 import hypothesis_targets
from lsr02_structure import detect


def finite(x):
    return type(x) in (int, float) and isfinite(x)


def simulate(bars, *, side, entry, sl, entry_at, as_of, interval,
             targets, risk_usd, round_trip_cost_usd, per_exit_cost_usd):
    """Entry is assumed filled at entry_at, before the first complete bar.

    targets is an ascending-distance list of (price, original-position fraction).
    OHLC ties use stop first; adverse opening gaps fill stops at open.
    Limits never gain opening-gap improvement. No breakeven/trailing stop.
    Costs: pro-rata whole-position round trip plus fixed fee per exit fill.
    """
    if (side not in ('BUY', 'SELL') or
            not all(finite(v) for v in (entry, sl, entry_at, as_of, interval,
                                       risk_usd, round_trip_cost_usd, per_exit_cost_usd))
            or min(entry, sl, risk_usd, interval) <= 0 or entry_at < 0
            or as_of < entry_at or min(round_trip_cost_usd, per_exit_cost_usd) < 0):
        raise ValueError('Invalid exit model input')
    sign = 1 if side == 'BUY' else -1
    distance = sign*(entry-sl)
    if distance <= 0 or not targets:
        raise ValueError('Invalid stop or empty targets')
    last = 0
    fraction_sum = 0
    for price, fraction in targets:
        if (not finite(price) or not finite(fraction) or price <= 0 or fraction <= 0
                or sign*(price-entry) <= last):
            raise ValueError('Targets must increase in favorable distance')
        last = sign*(price-entry)
        fraction_sum += fraction
    if not isfinite(fraction_sum) or abs(fraction_sum-1) > 1e-12:
        raise ValueError('Fractions must sum to one')
    detect(bars, as_of=as_of, interval=interval)
    if bars and bars[0]['close_time'] != entry_at+interval:
        raise ValueError('Need full bars strictly after entry')
    fills, pending = [], list(targets)

    def fill(price, fraction, at, reason):
        gross = sign*(price-entry)/distance*risk_usd*fraction
        cost = round_trip_cost_usd*fraction+per_exit_cost_usd
        if not all(isfinite(v) for v in (gross, cost, gross-cost)):
            raise ValueError('Unrepresentable result')
        fills.append(dict(price=price, fraction=fraction, at=at,
                          reason=reason, gross_pnl=gross, cost=cost))

    for b in bars:
        if not pending:
            break
        at = b['close_time']  # availability time, not an inferred intrabar timestamp
        opening = b['open']
        if sign*(opening-sl) <= 0:
            fill(opening, sum(f for _, f in pending), at, 'STOP_GAP')
            pending.clear()
            break
        # Open is known to precede the high/low; take already-marketable limits.
        while pending and sign*(opening-pending[0][0]) >= 0:
            price, fraction = pending.pop(0)
            fill(price, fraction, at, 'TARGET_AT_OPEN')
        adverse = b['low'] if side == 'BUY' else b['high']
        if pending and sign*(adverse-sl) <= 0:
            fill(sl, sum(f for _, f in pending), at, 'STOP_FIRST')
            pending.clear()
            break
        favorable = b['high'] if side == 'BUY' else b['low']
        while pending and sign*(favorable-pending[0][0]) >= 0:
            price, fraction = pending.pop(0)
            fill(price, fraction, at, 'TARGET')
    net = sum(f['gross_pnl']-f['cost'] for f in fills)
    return dict(status='OPEN' if pending else 'CLOSED', fills=fills,
                realized_net_usd=net, realized_r=net/risk_usd,
                remaining_fraction=sum(f for _, f in pending),
                completed_net_usd=None if pending else net,
                execution_allowed=False, data_source='CALLER_PROVIDED_UNVERIFIED')


def compare(bars, *, measured_range, partial_target, partial_fraction, **settings):
    """A/B hypotheses and partial/full exits on exactly the same path/costs."""
    if not finite(partial_fraction) or not 0 < partial_fraction < 1:
        raise ValueError('Explicit partial fraction required')
    targets = hypothesis_targets(settings['side'], settings['entry'],
                                 settings['sl'], measured_range)
    results = {}
    for name in ('A_range_2_6', 'B_gross_rr_2_6'):
        target = targets[name]
        results[name] = {
            'full': simulate(bars, targets=[(target, 1)], **settings),
            'partial': simulate(bars, targets=[(partial_target, partial_fraction),
                                  (target, 1-partial_fraction)], **settings)}
    return dict(hypotheses=results, C_undefined=None, execution_allowed=False)
