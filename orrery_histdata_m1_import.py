#!/usr/bin/env python3
"""Offline converter: HistData Generic ASCII M1 ZIP -> UTC validated M1 CSV.
No network, broker access, orders or invented missing candles.
HistData Generic ASCII timestamps are fixed EST (UTC-05:00), no DST.
"""
import argparse
import csv
import datetime as dt
import io
import json
import re
import zipfile
from pathlib import Path

EST = dt.timezone(dt.timedelta(hours=-5))
UTC = dt.timezone.utc
ENTRY = re.compile(r"^(?:DAT_ASCII_)?(XAUUSD|USDJPY)_M1_(20\d{4})\.csv$", re.I)
MAX_UNCOMPRESSED = 60_000_000

def convert(source: Path, output: Path, symbol: str) -> dict:
    with zipfile.ZipFile(source) as z:
        files = [v for v in z.infolist() if ENTRY.match(Path(v.filename).name)
                 and ENTRY.match(Path(v.filename).name).group(1).upper() == symbol]
        if len(files) != 1:
            raise ValueError("ZIP must contain exactly one matching HistData Generic ASCII M1 CSV")
        info = files[0]
        if info.file_size > MAX_UNCOMPRESSED:
            raise ValueError("CSV exceeds configured uncompressed limit")
        rows = []
        previous = None
        with z.open(info) as raw, io.TextIOWrapper(raw, encoding="utf-8-sig") as data:
            for line_number, line in enumerate(data, 1):
                fields = line.strip().split(";")
                if len(fields) != 6:
                    raise ValueError(f"line {line_number}: expected six semicolon-separated columns")
                local = dt.datetime.strptime(fields[0], "%Y%m%d %H%M%S").replace(tzinfo=EST)
                if local.second != 0:
                    raise ValueError(f"line {line_number}: M1 second must equal 00")
                timestamp = local.astimezone(UTC)
                if previous is not None and timestamp <= previous:
                    raise ValueError(f"line {line_number}: non-increasing timestamp")
                previous = timestamp
                o, h, l, c = map(float, fields[1:5])
                if not (0 < l <= min(o,c) <= max(o,c) <= h):
                    raise ValueError(f"line {line_number}: invalid OHLC")
                rows.append((timestamp.isoformat(),o,h,l,c))
        if not rows:
            raise ValueError("M1 file is empty")
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as fp:
        writer = csv.writer(fp)
        writer.writerow(["timestamp_utc","bid_open","bid_high","bid_low","bid_close"])
        writer.writerows(rows)
    return {"source":"HistData Generic ASCII M1","symbol":symbol,"bars":len(rows),
            "first_utc":rows[0][0],"last_utc":rows[-1][0],
            "price_basis":"BID_ONLY","timestamp_source":"fixed EST UTC-05:00; no DST",
            "tick_execution_validated":False,"profit_calculated":False}

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("zip_path",type=Path)
    p.add_argument("--symbol",required=True,choices=["XAUUSD","USDJPY"])
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    print(json.dumps(convert(a.zip_path,a.out,a.symbol),indent=2))
