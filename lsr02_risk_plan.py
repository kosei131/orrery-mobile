"""Offline structural stop planning and realized performance; never places orders."""
from math import isfinite
from lsr02 import risk_gate


def number(value):
    return type(value) in (int, float) and isfinite(value)


def plan(*, side, entry, sweep_extreme, buffer, target, **guards):
    """Stop lies beyond sweep; target remains the caller's structural target.

    Same USD assumptions as risk_gate: equity*fraction is gross stop loss,
    cost is a conservative whole-trade USD estimate added to stop risk.
    Does not verify broker minimum stops, tick values, fills or lot sizes.
    """
    values = (entry, sweep_extreme, buffer, target)
    if (side not in ('BUY', 'SELL') or not all(number(v) for v in values)
            or min(entry, sweep_extreme, target) <= 0 or buffer <= 0):
        raise ValueError('Invalid structural stop input')
    sl = sweep_extreme - buffer if side == 'BUY' else sweep_extreme + buffer
    if not (isfinite(sl) and ((side == 'BUY' and 0 < sl < sweep_extreme < entry < target)
            or (side == 'SELL' and 0 < target < entry < sweep_extreme < sl))):
        raise ValueError('Stop or target is on the wrong side')
    # Let the existing conservative gate validate all account/data guards.
    accepted = risk_gate(side=side, entry=entry, sl=sl, tp=target, **guards)
    equity, fraction, cost = (guards.get(k) for k in ('equity', 'risk_fraction', 'cost'))
    valid = all(number(v) for v in (equity, fraction, cost)) and equity > 0 and fraction > 0 and cost >= 0
    gross_risk = equity * fraction if valid else None
    rr = abs(target-entry) / abs(entry-sl)
    net_rr = (gross_risk*rr-cost)/(gross_risk+cost) if valid else None
    return {'status': 'DEMO_REVIEW_ONLY' if accepted else 'SKIP',
            'stop': sl, 'target': target,
            'gross_stop_risk_usd': gross_risk,
            'estimated_stop_loss_usd': gross_risk+cost if valid else None,
            'net_rr': net_rr, 'lots': None,
            'sizing_status': 'AWAIT_VERIFIED_BROKER_SPEC',
            'execution_allowed': False}


def performance(trades, *, initial_equity):
    """Chronological CLOSED trades only, USD. No deposits/withdrawals assumed.

    Each record: id, closed_at (numeric UTC seconds), gross_pnl, cost,
    initial_risk (planned gross stop USD >0). R uses that gross risk basis.
    Realized drawdown excludes open P/L, so is NOT account max drawdown.
    """
    if not number(initial_equity) or initial_equity <= 0:
        raise ValueError('Positive initial equity required')
    seen, previous = set(), None
    nets, rs = [], []
    equity = peak = initial_equity
    max_dd = max_dd_pct = 0
    streak = max_streak = 0
    for t in trades:
        ident = t.get('id')
        at, gross, cost, risk = (t.get(k) for k in ('closed_at', 'gross_pnl', 'cost', 'initial_risk'))
        if (not isinstance(ident, str) or not ident or ident in seen
                or not all(number(v) for v in (at, gross, cost, risk))
                or at < 0 or cost < 0 or risk <= 0
                or (previous is not None and at < previous)):
            raise ValueError('Invalid or unordered closed trade')
        seen.add(ident)
        previous = at
        net = gross-cost
        if not isfinite(net) or not isfinite(net/risk):
            raise ValueError('Unrepresentable trade result')
        equity += net
        if not isfinite(equity) or equity < 0:
            raise ValueError('Invalid equity path')
        nets.append(net)
        rs.append(net/risk)
        peak = max(peak, equity)
        max_dd = max(max_dd, peak-equity)
        max_dd_pct = max(max_dd_pct, (peak-equity)/peak)
        # Breakeven does not erase a loss streak; a positive NET win resets it.
        streak = streak+1 if net < 0 else (0 if net > 0 else streak)
        max_streak = max(max_streak, streak)
    wins = sum(x > 0 for x in nets)
    losses = sum(x < 0 for x in nets)
    profit = sum(x for x in nets if x > 0)
    loss = -sum(x for x in nets if x < 0)
    n = len(nets)
    return {'trades': n, 'wins': wins, 'losses': losses,
            'breakeven': n-wins-losses,
            'net_pnl_usd': sum(nets), 'ending_equity': equity,
            'win_rate': wins/n if n else None,
            'expectancy_usd': sum(nets)/n if n else None,
            'expectancy_r': sum(rs)/n if n else None,
            'profit_factor': profit/loss if loss else None,
            'max_realized_drawdown_usd': max_dd,
            'max_realized_drawdown_fraction': max_dd_pct,
            'max_consecutive_losses': max_streak,
            'current_consecutive_losses': streak,
            'execution_allowed': False}
