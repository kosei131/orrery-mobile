"""Read-only DEMO position stop valuation, account currency, no orders.

Current-close-to-SL loss is incremental equity exposure, not entry-to-SL
loss. No offsetting of winning positions against losses. Costs/gaps require
explicit per-position allowances; this is not a worst-case loss guarantee.
"""
from math import isfinite, fsum
from lsr04_mt5_account_sync import _identity, _utc


def _number(value, positive=False):
    if type(value) not in (int, float) or not isfinite(value) or (positive and value <= 0):
        raise ValueError("Invalid position valuation number")
    return float(value)


def position_signature(positions):
    rows = []
    for p in positions:
        if type(p.identifier) is not int or p.identifier <= 0 or type(p.ticket) is not int or p.ticket <= 0:
            raise ValueError("Position identity required")
        if not isinstance(p.symbol, str) or not p.symbol or type(p.type) is not int:
            raise ValueError("Position symbol/side required")
        for value in (p.volume, p.price_open, p.sl):
            _number(value, positive=True)
        rows.append((p.identifier, p.ticket, p.symbol, p.type, p.volume, p.price_open, p.sl))
    if len({r[0] for r in rows}) != len(rows):
        raise ValueError("Duplicate position identifier")
    return sorted(rows)


def demo_position_risk(mt5, *, now_utc, cost_allowances, max_quote_age_seconds=5,
                       expected_positions=None, expected_account=None):
    if not _utc(now_utc):
        raise ValueError("Explicit UTC valuation time required")
    if not 0 < _number(max_quote_age_seconds) <= 30:
        raise ValueError("Quote age must be within 30 seconds")
    if not isinstance(cost_allowances, dict) or any(type(k) is not int or k <= 0 for k in cost_allowances):
        raise ValueError("Explicit per-position cost/gap allowances required")
    if any(_number(v) < 0 for v in cost_allowances.values()):
        raise ValueError("Negative cost allowance")
    def blocked(reason):
        return dict(status="BLOCKED_POSITION_RISK", reason=reason,
                    total_incremental_stop_risk=None, positions=[], execution_allowed=False)
    try:
        account = mt5.account_info()
        if account is None or getattr(mt5, "ACCOUNT_TRADE_MODE_DEMO", None) is None or account.trade_mode != mt5.ACCOUNT_TRADE_MODE_DEMO:
            return blocked("DEMO_ACCOUNT_REQUIRED")
        identity = _identity(account)
        captured_equity = _number(account.equity, positive=True)
        if expected_account is not None and (_identity(expected_account) != identity or expected_account.equity != captured_equity):
            return blocked("ACCOUNT_SNAPSHOT_CHANGED")
        positions = mt5.positions_get()
        if positions is None:
            return blocked("POSITIONS_UNAVAILABLE")
        if len(positions) > 10000:
            return blocked("POSITION_LIMIT")
        signature = position_signature(positions)
        if expected_positions is not None and position_signature(expected_positions) != signature:
            return blocked("POSITIONS_CHANGED")
        if set(cost_allowances) != {p.identifier for p in positions}:
            return blocked("COST_ALLOWANCES_INCOMPLETE")
        buy, sell = mt5.POSITION_TYPE_BUY, mt5.POSITION_TYPE_SELL
        actions = (mt5.ORDER_TYPE_BUY, mt5.ORDER_TYPE_SELL)
        if any(type(v) is not int for v in (buy, sell, *actions)) or buy == sell or actions[0] == actions[1]:
            return blocked("INVALID_SIDE_CONSTANTS")
        rows = []; ticks = {}
        for p in positions:
            if p.type not in (buy, sell):
                return blocked("UNKNOWN_POSITION_SIDE")
            if p.symbol not in ticks:
                info = mt5.symbol_info(p.symbol)
                if info is None or info.name != p.symbol:
                    return blocked("SYMBOL_UNAVAILABLE")
                tick = mt5.symbol_info_tick(p.symbol)
                if tick is None:
                    return blocked("QUOTE_UNAVAILABLE")
                bid, ask = _number(tick.bid, True), _number(tick.ask, True)
                if bid > ask or type(tick.time_msc) is not int:
                    return blocked("INVALID_QUOTE")
                age = now_utc.timestamp() - tick.time_msc / 1000
                if not 0 <= age <= max_quote_age_seconds:
                    return blocked("STALE_OR_FUTURE_QUOTE")
                ticks[p.symbol] = (bid, ask, tick.time_msc)
            bid, ask, tick_time = ticks[p.symbol]
            current = bid if p.type == buy else ask
            if not (p.sl < current if p.type == buy else p.sl > current):
                return blocked("STOP_ALREADY_REACHED_OR_CROSSED")
            action = actions[0] if p.type == buy else actions[1]
            entry_pnl = _number(mt5.order_calc_profit(action, p.symbol, p.volume, p.price_open, p.sl))
            incremental_pnl = _number(mt5.order_calc_profit(action, p.symbol, p.volume, current, p.sl))
            if incremental_pnl >= 0:
                return blocked("INCONSISTENT_BROKER_STOP_QUOTE")
            allowance = cost_allowances[p.identifier]
            incremental = -incremental_pnl + allowance
            _number(incremental)
            rows.append(dict(position_id=p.identifier, symbol=p.symbol,
                side="BUY" if p.type == buy else "SELL", volume=p.volume,
                entry_price=p.price_open, stop_price=p.sl, bid=bid, ask=ask,
                tick_time_msc=tick_time, entry_to_stop_pnl=entry_pnl,
                incremental_price_loss=-incremental_pnl, cost_allowance=allowance,
                incremental_stop_risk=incremental))
        # Recheck relevant position fields; prices/profit naturally move and are not fingerprints.
        final_positions = mt5.positions_get()
        final_account = mt5.account_info()
        if final_positions is None or position_signature(final_positions) != signature:
            return blocked("POSITIONS_CHANGED")
        if final_account is None or _identity(final_account) != identity or final_account.equity != captured_equity:
            return blocked("ACCOUNT_SNAPSHOT_CHANGED")
        total = fsum(r["incremental_stop_risk"] for r in rows)
        _number(total)
    except Exception:
        return blocked("INVALID_OR_FAILED_BROKER_VALUATION")
    return dict(status="RESEARCH_POSITION_RISK", total_incremental_stop_risk=total,
                positions=rows, currency=identity[2], execution_allowed=False,
                caveat="Non-atomic sampled estimate; caller cost/gap allowances unverified, no margin/liquidation or guaranteed stop fill.")
