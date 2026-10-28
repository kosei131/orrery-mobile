"""Read-only DEMO history/grouping bridge. No order authorization.

Completeness is externally asserted, never inferred from a successful fetch.
Optional broker stop valuation replaces caller risk estimates for research.
Costs/equity components remain unverified and block an overall safe status.
"""
from datetime import datetime, timedelta
from math import isfinite, fsum
from lsr04_account_gate import review
from lsr04_deal_groups import reconcile
from lsr04_daily_reconciliation import reconcile_day, amount


def _utc(t):
    return isinstance(t, datetime) and t.utcoffset() is not None and t.utcoffset().total_seconds() == 0


def _identity(account):
    key = tuple(getattr(account, f, None) for f in ("login", "server", "currency", "trade_mode"))
    if type(key[0]) is not int or key[0] <= 0 or any(not isinstance(s, str) or not s for s in key[1:3]):
        raise ValueError("Account identity and currency required")
    return key


def demo_day_check(mt5, *, day_start_utc, now_utc, day_start_equity,
                   existing_stop_risk, proposed_stop_risk,
                   history_start_utc=None, history_complete=False,
                   day_start_snapshot=None, verified_cash_flows=None,
                   stop_cost_allowances=None):
    if not all(_utc(t) for t in (day_start_utc, now_utc)):
        raise ValueError("UTC-aware times required")
    if not day_start_utc < now_utc < day_start_utc + timedelta(days=1):
        raise ValueError("Invalid daily history bounds")
    start = day_start_utc if history_start_utc is None else history_start_utc
    if not _utc(start) or start > day_start_utc or type(history_complete) is not bool:
        raise ValueError("Invalid full-history bounds/completeness assertion")
    if type(day_start_equity) not in (int, float) or not isfinite(day_start_equity) or day_start_equity <= 0:
        raise ValueError("Externally verified daily starting equity required")
    account = mt5.account_info()
    demo = getattr(mt5, "ACCOUNT_TRADE_MODE_DEMO", None)
    if account is None or demo is None or getattr(account, "trade_mode", None) != demo:
        raise ValueError("Broker-reported demo required")
    identity = _identity(account)

    def blocked(status, **details):
        return dict(status=status, execution_allowed=False, **details)

    try:
        deals = mt5.history_deals_get(start, now_utc)
        positions = mt5.positions_get()
        after = mt5.account_info()
    except Exception:
        return blocked("BLOCKED_BROKER_READ_FAILED")
    if deals is None or positions is None or after is None:
        return blocked("BLOCKED_INCOMPLETE_BROKER_HISTORY")
    try:
        if _identity(after) != identity:
            return blocked("BLOCKED_ACCOUNT_CHANGED")
    except ValueError:
        return blocked("BLOCKED_ACCOUNT_CHANGED")
    if type(getattr(after, "equity", None)) not in (int, float) or not isfinite(after.equity) or after.equity <= 0:
        return blocked("BLOCKED_INVALID_ACCOUNT_RISK")
    # MT5 reads are not atomic: this identity check does not prove snapshot consistency.
    try:
        if len(deals) > 100000:
            raise ValueError("History exceeds bounded grouping capacity")
        constants = [getattr(mt5, f) for f in ("DEAL_ENTRY_IN", "DEAL_ENTRY_OUT", "DEAL_ENTRY_INOUT")]
        if any(type(c) is not int for c in constants):
            raise ValueError("Integer entry constants required")
        buy, sell = mt5.DEAL_TYPE_BUY, mt5.DEAL_TYPE_SELL
        if type(buy) is not int or type(sell) is not int or buy == sell:
            raise ValueError("Trade type constants required")
        ids = [p.identifier for p in positions]  # identifier, not potentially changing ticket
        if len(set(ids)) != len(ids):
            raise ValueError("Duplicate open position identity")
        lower, upper = start.timestamp() * 1000, now_utc.timestamp() * 1000
        cash_flows = {} if verified_cash_flows is None else verified_cash_flows
        if not isinstance(cash_flows, dict) or any(type(k) is not int or k <= 0 for k in cash_flows):
            raise ValueError("Ticket-indexed externally verified cash amounts required")
        for value in cash_flows.values():
            amount(value)
        trades = []; cash_rows = []; seen = set()
        for d in deals:
            if type(d.ticket) is not int or d.ticket <= 0 or d.ticket in seen:
                raise ValueError("Duplicate/invalid history ticket")
            seen.add(d.ticket)
            if type(d.time_msc) is not int or not lower <= d.time_msc <= upper:
                raise ValueError("Deal outside requested history")
            if type(d.type) is not int:
                raise ValueError("Unknown deal type")
            if d.type not in (buy, sell):
                # BALANCE also covers adjustments; never infer deposit/withdrawal from type/sign.
                if d.type != getattr(mt5, "DEAL_TYPE_BALANCE", None) or d.ticket not in cash_flows:
                    raise ValueError("Unclassified cash operation or correction")
                if d.position_id != 0 or amount(d.volume) != 0 or amount(d.profit) != amount(cash_flows[d.ticket]):
                    raise ValueError("Cash evidence mismatch")
                if any(amount(getattr(d, f)) != 0 for f in ("commission", "swap", "fee")):
                    raise ValueError("Cash row with unattributed costs")
                cash_rows.append(d)
                continue
            if d.ticket in cash_flows:
                raise ValueError("Trade mislabeled as cash")
            trades.append(d)
            if not isinstance(d.symbol, str) or not d.symbol:
                raise ValueError("Missing broker symbol")
        if set(cash_flows) != {d.ticket for d in cash_rows}:
            raise ValueError("Cash evidence not found in history")
        # Validate symbol and direction throughout each position lifetime.
        lifetimes = {}
        for d in sorted(trades, key=lambda d: (d.time_msc, d.ticket)):
            symbol, direction = lifetimes.setdefault(d.position_id, (d.symbol, d.type))
            if d.symbol != symbol or (d.entry == constants[0] and d.type != direction) or (d.entry == constants[1] and d.type == direction):
                raise ValueError("Inconsistent position symbol/direction")
        grouped = reconcile(trades, entry_in=constants[0], entry_out=constants[1],
                            entry_inout=constants[2], open_position_ids=ids,
                            history_complete=history_complete)
        daily = [d for d in trades if d.time_msc >= day_start_utc.timestamp() * 1000]
        daily_net = fsum(getattr(d, f) for d in daily for f in ("profit", "commission", "swap", "fee"))
        daily_cash = fsum(d.profit for d in cash_rows if d.time_msc >= day_start_utc.timestamp() * 1000)
        if not isfinite(daily_net) or not isfinite(daily_cash):
            raise ValueError("Nonfinite daily total")
    except (AttributeError, TypeError, ValueError, OverflowError):
        return blocked("BLOCKED_UNCLASSIFIED_OR_INVALID_HISTORY")
    details = dict(grouping=grouped, deal_count=len(deals), open_positions=len(positions),
                   account_currency=identity[2], daily_deal_net=daily_net,
                   daily_equity_change=after.equity - day_start_equity,
                   daily_external_cash_net=daily_cash, daily_reconciled=False)
    if stop_cost_allowances is not None:
        from lsr04_mt5_position_risk import demo_position_risk
        try:
            exposure = demo_position_risk(mt5, now_utc=now_utc,
                cost_allowances=stop_cost_allowances,
                expected_positions=positions, expected_account=after)
        except (ValueError, TypeError):
            return blocked("BLOCKED_INVALID_STOP_ALLOWANCES", **details)
        details["stop_exposure"] = exposure
        if exposure["total_incremental_stop_risk"] is None:
            return blocked("BLOCKED_POSITION_RISK", **details)
        # Never use a manually supplied lower estimate in place of broker valuation.
        existing_stop_risk = exposure["total_incremental_stop_risk"]
    if day_start_snapshot is not None:
        try:
            snap = day_start_snapshot
            if not isinstance(snap, dict) or snap["at_utc"] != day_start_utc or not _utc(snap["at_utc"]):
                raise ValueError("Baseline must be at the exact session boundary")
            if tuple(snap[f] for f in ("login", "server", "currency", "trade_mode")) != identity:
                raise ValueError("Baseline account mismatch")
            if amount(snap["equity"]) != amount(day_start_equity):
                raise ValueError("Starting equity mismatch")
            daily_review = reconcile_day(opening_balance=snap["balance"], opening_equity=snap["equity"],
                closing_balance=after.balance, closing_equity=after.equity,
                trade_net=daily_net, external_cash_net=daily_cash,
                history_complete=history_complete, baseline_verified=snap["verified"])
        except (KeyError, AttributeError, ValueError, TypeError):
            return blocked("BLOCKED_INVALID_DAILY_BASELINE", **details)
        details["daily_review"] = daily_review
    if grouped["consecutive_losses"] is None:
        return blocked("BLOCKED_NO_AUTHORITATIVE_STREAK", **details)
    try:
        gate = review(day_start_utc=day_start_utc, now_utc=now_utc,
                      day_start_equity=day_start_equity, current_equity=after.equity,
                      existing_stop_risk=existing_stop_risk, proposed_stop_risk=proposed_stop_risk,
                      consecutive_losses=grouped["consecutive_losses"])
    except (TypeError, ValueError):
        return blocked("BLOCKED_INVALID_ACCOUNT_RISK", **details)
    # Nonzero external cash can mask or exaggerate the raw-equity daily gate.
    # Until that gate supports cash-adjusted equity, retain an explicit block.
    if daily_cash != 0:
        return blocked("BLOCKED_CASH_ADJUSTED_RISK_REQUIRED", risk_review=gate, **details)
    if day_start_snapshot is None or not details["daily_review"]["balance_reconciled"]:
        return blocked("BLOCKED_DAILY_RECONCILIATION", risk_review=gate, **details)
    # Balance reconciliation alone cannot verify floating/credit/blocked components.
    return blocked("BLOCKED" if gate["reasons"] else "BLOCKED_UNVERIFIED_EQUITY_AND_STOP_EXPOSURE",
                   risk_review=gate, **details)
