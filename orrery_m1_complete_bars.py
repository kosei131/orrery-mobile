#!/usr/bin/env python3
"""Build *complete only* UTC OHLC bars from ordered M1 bid candles.
Reject missing minutes; no forward filling or synthetic history.
"""
import argparse
import csv
import datetime as dt
import json
from pathlib import Path

PERIODS = {"M5": 5, "M15": 15, "H4": 240}

def aggregate(src: Path, dst: Path, period: str):
    size = PERIODS[period]
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
            if not (0 < p[2] <= min(p[0],p[3]) <= max(p[0],p[3]) <= p[1]):
                raise ValueError("invalid M1 OHLC")
            key = int(t.timestamp()) // (size * 60) * size * 60
            buckets.setdefault(key, []).append((t,p))
            total += 1
    complete = []
    dropped = []
    for k, group in sorted(buckets.items()):
        start = dt.datetime.fromtimestamp(k, dt.timezone.utc)
        expected = [start + dt.timedelta(minutes=n) for n in range(size)]
        if [t for t,_ in group] != expected:
            dropped.append(start.isoformat())
            continue
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
            "price_basis":"bid_only","no_missing_data_filled":True,
            "sl_tp_execution_validated":False}

if __name__ == "__main__":
    p=argparse.ArgumentParser()
    p.add_argument("m1_csv",type=Path)
    p.add_argument("--period",choices=sorted(PERIODS),required=True)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    print(json.dumps(aggregate(a.m1_csv,a.out,a.period),indent=2))
