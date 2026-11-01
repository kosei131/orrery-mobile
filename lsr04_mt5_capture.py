"""Read-only bounded historical MT5 DEMO capture with coverage diagnostics.

Half-open day windows [start,end) de-duplicate their shared boundaries.
No completeness claims from empty windows; no account identifiers or secrets.
"""
from datetime import timedelta
from lsr04_mt5_ticks import read_ticks

def capture_days(mt5, *, symbol, start_utc, end_utc, max_days=190):
    if not isinstance(max_days,int) or isinstance(max_days,bool) or not 1<=max_days<=366:
        raise ValueError("Invalid maximum days")
    if start_utc>=end_utc or end_utc-start_utc>timedelta(days=max_days):
        raise ValueError("Invalid capture horizon")
    cursor=start_utc;all_ticks=[];windows=[];last_t=None
    while cursor<end_utc:
        until=min(cursor+timedelta(days=1),end_utc)
        part=read_ticks(mt5,account_is_demo=True,symbol=symbol,
                        start_utc=cursor,end_utc=until)
        accepted=0
        for item in part["ticks"]:
            t=item["time_msc"]
            # MT5 range end is inclusive: exclude boundary in this half-open window.
            if t>=until.timestamp()*1000:continue
            if last_t is not None and t<last_t:
                raise ValueError("Unordered history across windows")
            # Multiple distinct ticks may legitimately share a millisecond.
            # Only the half-open end boundary is discarded, never same-time ticks.
            all_ticks.append(item);last_t=t;accepted+=1
        windows.append(dict(start_utc=cursor.isoformat(),end_utc=until.isoformat(),
                            accepted_ticks=accepted,empty=accepted==0,
                            at_safety_limit=part["count"]>=300000))
        cursor=until
    if any(w["at_safety_limit"] for w in windows):
        raise ValueError("Window reached tick cap; split into shorter windows")
    return dict(status="UNVERIFIED_HISTORY_COVERAGE",
                symbol=symbol,ticks=all_ticks,windows=windows,
                empty_windows=sum(w["empty"] for w in windows),
                execution_allowed=False,
                caution="Empty windows can reflect market closure OR missing broker history; investigate before backtesting.")
