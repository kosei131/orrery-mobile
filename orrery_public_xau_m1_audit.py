#!/usr/bin/env python3
"""Audit an independently published XAUUSD M1 sample.
Sample is a third-party mid-quote feed: NOT Dukascopy, MetaQuotes, or actual fills.
"""
import csv
import datetime as dt
import hashlib
import json
import math
import sys
from pathlib import Path

def inspect(path):
    sha=hashlib.sha256(path.read_bytes()).hexdigest()
    with path.open(newline="",encoding="utf-8-sig") as f:
        reader=csv.DictReader(f)
        fields={x.strip().lower():x for x in (reader.fieldnames or [])}
        tkey=next((fields[k] for k in ("datetime","timestamp","date","time") if k in fields),None)
        if not tkey or any(k not in fields for k in ("open","high","low","close")):
            raise ValueError("Unrecognized OHLC CSV schema")
        first=last=previous=None
        rows=0
        duplicates=0
        nonminute=0
        gaps=[]
        for row in reader:
            value=row[tkey].strip().replace("Z","+00:00")
            try:
                t=dt.datetime.fromisoformat(value)
            except ValueError:
                t=dt.datetime.strptime(value,"%Y-%m-%d %H:%M:%S")
            if t.tzinfo is not None:
                t=t.astimezone(dt.timezone.utc).replace(tzinfo=None)
            if t.second or t.microsecond:
                nonminute+=1
            o,h,l,c=(float(row[fields[k]]) for k in ("open","high","low","close"))
            if not all(math.isfinite(p) for p in (o,h,l,c)) or not (0<l<=min(o,c)<=max(o,c)<=h):
                raise ValueError(f"Invalid OHLC at row {rows+2}")
            if previous is not None:
                delta=(t-previous).total_seconds()
                if delta==0:duplicates+=1
                if delta<0:raise ValueError("Nonmonotonic timestamps")
                if delta>60:gaps.append((previous.isoformat(),t.isoformat(),int(delta/60)-1))
            first=first or t
            last=t
            previous=t
            rows+=1
    if not rows:raise ValueError("Empty CSV")
    return {"source":"GetData Finance GitHub public XAUUSD 1m sample",
            "source_price_type":"mid quotes according to publisher; broker fills unverified",
            "sha256":sha,"rows":rows,"first":first.isoformat(),"last":last.isoformat(),
            "duplicate_timestamps":duplicates,"nonminute_timestamps":nonminute,
            "number_of_gaps_gt_1min":len(gaps),"largest_missing_minutes":max((g[2] for g in gaps),default=0),
            "first_10_gaps":gaps[:10],"ready_for_6mo_backtest":False,
            "pnl_usd":None}
if __name__=="__main__":
    result=inspect(Path(sys.argv[1]))
    print(json.dumps(result,indent=2))
    Path(sys.argv[2]).write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
