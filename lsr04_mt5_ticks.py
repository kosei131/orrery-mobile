"""Read-only DEMO MT5 historical tick intake, no secrets or trade calls.

Call read_ticks with an injected MT5 module that implements copy_ticks_range.
Caller must explicitly supply account type, symbol and UTC range. Historical
coverage may be partial; downstream research must audit gaps and provenance.
"""
from datetime import datetime, timezone
from math import isfinite

MAX_TICKS=300000
def read_ticks(mt5, *, account_is_demo, symbol, start_utc, end_utc):
    if account_is_demo is not True:
        raise ValueError("DEMO-only data capture")
    account=mt5.account_info()
    if account is None or getattr(account,"trade_mode",None)!=getattr(mt5,"ACCOUNT_TRADE_MODE_DEMO",None) or getattr(mt5,"ACCOUNT_TRADE_MODE_DEMO",None) is None:
        raise ValueError("Broker-reported DEMO account is required")
    if symbol not in ("XAUUSD","USDJPY"):
        raise ValueError("Explicit canonical symbol required; do not guess broker suffix")
    if not isinstance(start_utc,datetime) or not isinstance(end_utc,datetime) or start_utc.utcoffset() is None or end_utc.utcoffset() is None:
        raise ValueError("Timezone-aware UTC bounds required")
    if start_utc.utcoffset().total_seconds()!=0 or end_utc.utcoffset().total_seconds()!=0 or not start_utc<end_utc:
        raise ValueError("Strict increasing UTC bounds required")
    info=mt5.symbol_info(symbol)
    if info is None or not getattr(info,"trade_contract_size",None):
        raise ValueError("Broker symbol metadata unavailable")
    raw=mt5.copy_ticks_range(symbol,start_utc,end_utc,mt5.COPY_TICKS_ALL)
    if raw is None or len(raw)>MAX_TICKS:
        raise ValueError("Tick feed missing or exceeds safe batch size")
    rows=[];previous=None
    for tick in raw:
        t=int(tick["time_msc"])
        bid=float(tick["bid"]);ask=float(tick["ask"])
        if t<start_utc.timestamp()*1000 or t>end_utc.timestamp()*1000 or (previous is not None and t<previous):
            raise ValueError("Unordered/out-of-range tick")
        if not all(isfinite(x) for x in (bid,ask)) or not 0<bid<=ask:
            raise ValueError("Missing or crossed bid/ask")
        rows.append(dict(time_msc=t,bid=bid,ask=ask))
        previous=t
    return dict(status="UNVERIFIED_DEMO_HISTORY_CAPTURE",symbol=symbol,
        requested_start=start_utc.isoformat(),requested_end=end_utc.isoformat(),
        count=len(rows),contract_size=float(info.trade_contract_size),
        ticks=rows,execution_allowed=False,
        caveat="Returned ticks are not proof of complete six-month history or executable fills.")
