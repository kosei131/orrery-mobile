"""Read-only MT5 DEMO account history snapshot and conservative stop gate.

Requires broker-reported DEMO status, complete provided history window, and
explicit authoritative daily start equity. MT5 position synchronization is
NOT yet a broker-certified risk exposure calculation. Never sends orders.
"""
from datetime import datetime, timezone
from math import isfinite
from lsr04_account_gate import review

def demo_day_check(mt5,*,day_start_utc,now_utc,day_start_equity,
                   existing_stop_risk,proposed_stop_risk):
    if not all(isinstance(t,datetime) and t.utcoffset() is not None and
               t.utcoffset().total_seconds()==0 for t in (day_start_utc,now_utc)):
        raise ValueError("UTC-aware times required")
    if not day_start_utc<now_utc:
        raise ValueError("Invalid history bounds")
    account=mt5.account_info()
    if account is None or getattr(mt5,"ACCOUNT_TRADE_MODE_DEMO",None) is None or getattr(account,"trade_mode",None)!=mt5.ACCOUNT_TRADE_MODE_DEMO:
        raise ValueError("Broker-reported demo required")
    deals=mt5.history_deals_get(day_start_utc,now_utc)
    positions=mt5.positions_get()
    if deals is None or positions is None:
        return dict(status="BLOCKED_INCOMPLETE_BROKER_HISTORY",execution_allowed=False)
    if type(day_start_equity) not in (int,float) or not isfinite(day_start_equity) or day_start_equity<=0:
        raise ValueError("Externally verified daily starting equity required")
    # Aggregate close transactions rather than assuming an individual deal
    # always corresponds to a complete round-trip trade.
    # In absence of authoritative position-grouped trade PnL, do not estimate
    # the consecutive loss count from raw DEAL_ENTRY_OUT rows.
    if any(getattr(d,"entry",None)==getattr(mt5,"DEAL_ENTRY_OUT",object())
           for d in deals):
        return dict(status="BLOCKED_TRADE_GROUPING_REQUIRED",
                    deal_count=len(deals),open_positions=len(positions),
                    execution_allowed=False,
                    caveat="Partial exits, commissions and multi-deal trades need authoritative grouping.")
    if deals:
        return dict(status="BLOCKED_UNCLASSIFIED_DEALS",
                    deal_count=len(deals),execution_allowed=False)
    result=review(day_start_utc=day_start_utc,now_utc=now_utc,
        day_start_equity=day_start_equity,current_equity=float(account.equity),
        existing_stop_risk=existing_stop_risk,proposed_stop_risk=proposed_stop_risk,
        consecutive_losses=0)
    # Zero closed deals in the verified period is not proof of past streak.
    return dict(result,status="BLOCKED_NO_AUTHORITATIVE_STREAK",
                open_positions=len(positions),deal_count=0,execution_allowed=False,
                caveat="Requires earlier deal history and fully grouped positions before trade approval.")
