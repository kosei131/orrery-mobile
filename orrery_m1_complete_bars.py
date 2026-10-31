#!/usr/bin/env python3
"""Build *complete only* UTC OHLC bars from ordered M1 bid candles.
Reject missing minutes; no forward filling or synthetic history.
"""
import argparse
import csv
import datetime as dt
import json
import hashlib
import math
from bisect import bisect_right
from pathlib import Path

PERIODS = {"M5": 5, "M15": 15, "H4": 240}

def calendar_minutes(calendar, size):
    """Caller-supplied schedule, never inferred or certified as broker truth."""
    source = calendar.get("source")
    if not isinstance(source, str) or not source.strip():
        raise ValueError("Calendar source required")
    intervals = calendar.get("intervals")
    if not isinstance(intervals, list) or not intervals:
        raise ValueError("Explicit OPEN/CLOSED intervals required")
    starts, ends, states = [], [], []
    for item in intervals:
        pair = []
        for key in ("start_utc", "end_utc"):
            t = dt.datetime.fromisoformat(item[key])
            if t.tzinfo is None or t.utcoffset() != dt.timedelta(0) or t.second or t.microsecond:
                raise ValueError("Calendar requires UTC minute boundaries")
            pair.append(int(t.timestamp()))
        a, b = pair
        if b <= a or (ends and a != ends[-1]) or item["state"] not in ("OPEN", "CLOSED"):
            raise ValueError("Calendar must cover consecutive nonoverlapping intervals")
        starts.append(a); ends.append(b); states.append(item["state"])
    if starts[0] % (size*60) or ends[-1] % (size*60):
        raise ValueError("Calendar horizon must align to requested bar grid")
    if ends[-1]-starts[0] > 366*86400:
        raise ValueError("Calendar horizon exceeds one year")
    expected = {}
    for stamp in range(starts[0], ends[-1], 60):
        i = bisect_right(starts, stamp)-1
        if states[i] == "OPEN":
            key = stamp // (size*60) * size*60
            expected.setdefault(key, []).append(stamp)
    return expected


def aggregate(src: Path, dst: Path, period: str, *, calendar=None):
    size = PERIODS[period]
    expected_by_bucket = calendar_minutes(calendar, size) if calendar is not None else None
    buckets = {}
    total = 0
    previous = None
    with src.open(newline="", encoding="utf-8") as fp:
        for record in csv.DictReader(fp):
            t = dt.datetime.fromisoformat(record["timestamp_utc"])
            if t.tzinfo is None or t.utcoffset() != dt.timedelta(0) or t.second or t.microsecond:
                raise ValueError("UTC minute timestamps required")
            if previous is not None and t <= previous:
                raise ValueError("timestamps must strictly increase")
            previous = t
            p = [float(record[k]) for k in ("bid_open","bid_high","bid_low","bid_close")]
            if not all(math.isfinite(x) for x in p) or not (0 < p[2] <= min(p[0],p[3]) <= max(p[0],p[3]) <= p[1]):
                raise ValueError("invalid M1 OHLC")
            key = int(t.timestamp()) // (size * 60) * size * 60
            if expected_by_bucket is not None and int(t.timestamp()) not in expected_by_bucket.get(key, []):
                raise ValueError("Quote outside explicitly OPEN calendar minutes")
            buckets.setdefault(key, []).append((t,p))
            total += 1
    complete = []
    dropped = []
    keys = sorted(buckets if expected_by_bucket is None else expected_by_bucket)
    session_partial = 0
    for k in keys:
        group = buckets.get(k, [])
        start = dt.datetime.fromtimestamp(k, dt.timezone.utc)
        expected = ([start + dt.timedelta(minutes=n) for n in range(size)]
                    if expected_by_bucket is None else
                    [dt.datetime.fromtimestamp(t, dt.timezone.utc) for t in expected_by_bucket[k]])
        if [t for t,_ in group] != expected:
            dropped.append(start.isoformat())
            continue
        session_partial += len(expected) < size
        prices = [p for _,p in group]
        complete.append([start.isoformat(),prices[0][0],max(p[1] for p in prices),
                         min(p[2] for p in prices),prices[-1][3]])
    dst.parent.mkdir(parents=True,exist_ok=True)
    with dst.open("w",newline="",encoding="utf-8") as fp:
        w=csv.writer(fp)
        w.writerow(["timestamp_utc","bid_open","bid_high","bid_low","bid_close"])
        w.writerows(complete)
    return {"period":period,"source_m1_rows":total,"complete_bars":len(complete),
            "incomplete_bars_rejected":len(dropped),"rejected_utc_starts":dropped,
            "price_basis":"bid_only",
            "calendar_source":calendar["source"] if calendar is not None else None,
            "calendar_sha256":hashlib.sha256(json.dumps(calendar,sort_keys=True,separators=(",", ":")).encode()).hexdigest() if calendar is not None else None,
            "calendar_broker_verified":False,
            "complete_session_partial_bars":session_partial,
            "bar_grid":"UTC; close at grid end, including session-partial bars",
            "execution_allowed":False,"no_missing_data_filled":True,
            "sl_tp_execution_validated":False}

if __name__ == "__main__":
    p=argparse.ArgumentParser()
    p.add_argument("m1_csv",type=Path)
    p.add_argument("--period",choices=sorted(PERIODS),required=True)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--calendar-json",type=Path)
    a=p.parse_args()
    print(json.dumps(aggregate(a.m1_csv,a.out,a.period,calendar=json.loads(a.calendar_json.read_text(encoding="utf-8")) if a.calendar_json else None),indent=2))
