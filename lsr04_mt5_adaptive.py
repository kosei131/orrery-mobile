"""Bounded, recursively split DEMO-only MT5 tick windows.

A window at the safety cap is NOT accepted as complete. No live trading.
"""
from datetime import timedelta
from lsr04_mt5_ticks import read_ticks

def capture_adaptive(mt5, *, symbol, start_utc, end_utc,
                     cap=300000, min_window_seconds=60, max_windows=10000):
    if type(cap) is not int or not 1<=cap<=300000:
        raise ValueError("Invalid safety cap")
    if type(min_window_seconds) is not int or not 1<=min_window_seconds<=3600:
        raise ValueError("Invalid minimum window")
    if type(max_windows) is not int or not 1<=max_windows<=100000:
        raise ValueError("Invalid window budget")
    if start_utc>=end_utc or end_utc-start_utc>timedelta(days=190):
        raise ValueError("Invalid historical horizon")
    if start_utc.microsecond%1000 or end_utc.microsecond%1000:
        raise ValueError("Millisecond-aligned capture bounds required")
    leaves=[];queue=[(start_utc,end_utc)]
    while queue:
        if len(leaves)+len(queue)>max_windows:
            raise ValueError("Historical window budget exhausted")
        start,end=queue.pop()
        part=read_ticks(mt5,account_is_demo=True,symbol=symbol,
                        start_utc=start,end_utc=end)
        if part["count"]>=cap:
            if (end-start).total_seconds()<=min_window_seconds:
                raise ValueError("Unresolved saturated window; cannot claim coverage")
            # Partition on an exact tick-clock millisecond, never fractional ms.
            span_ms=(end-start)//timedelta(milliseconds=1)
            mid=start+timedelta(milliseconds=span_ms//2)
            queue.extend([(mid,end),(start,mid)])
            continue
        data=[row for row in part["ticks"] if row["time_msc"]<end.timestamp()*1000]
        leaves.append((start,end,data))
    leaves.sort(key=lambda x:x[0])
    result=[];previous=None;windows=[]
    for start,end,rows in leaves:
        for row in rows:
            if previous is not None and row["time_msc"]<previous:
                raise ValueError("Out-of-order cross-window history")
            result.append(row);previous=row["time_msc"]
        windows.append(dict(start=start.isoformat(),end=end.isoformat(),count=len(rows),
                            empty=not bool(rows)))
    return dict(status="HISTORY_UNVERIFIED",symbol=symbol,ticks=result,
        windows=windows,empty_windows=sum(x["empty"] for x in windows),
        execution_allowed=False,
        caveat="Non-saturated chunks do not prove broker completeness; verify sessions and gaps.")
