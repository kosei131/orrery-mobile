"""Fail-closed converter from UTC OHLC CSV to LSR-02 closed-bar records.

No missing-bar interpolation. Gaps are reported; caller must not pass discontinuous
segments to LSR-02 as if they were consecutive market bars.
"""
import csv
import datetime as dt

SECONDS={"M5":300,"M15":900,"H4":14400}
def load(path,timeframe):
    sec=SECONDS[timeframe]
    bars=[];gaps=[];last=None
    with open(path,newline="",encoding="utf-8") as f:
        reader=csv.DictReader(f)
        required={"timestamp_utc","bid_open","bid_high","bid_low","bid_close"}
        if not required.issubset(reader.fieldnames or []):
            raise ValueError("Missing UTC OHLC columns")
        for row in reader:
            t=dt.datetime.fromisoformat(row["timestamp_utc"])
            if t.tzinfo is None or t.utcoffset()!=dt.timedelta(0):
                raise ValueError("Explicit UTC timestamps required")
            stamp=int(t.timestamp())
            if stamp%sec!=0:raise ValueError("Bar not aligned to UTC grid")
            if last is not None:
                if stamp<=last:raise ValueError("Non-increasing source bars")
                if stamp-last!=sec:
                    gaps.append({"after_open":last,"before_open":stamp,
                                 "missing_grid_bars":(stamp-last)//sec-1})
            o,h,l,c=[float(row[f"bid_{x}"]) for x in ("open","high","low","close")]
            if not (0<l<=min(o,c)<=max(o,c)<=h):
                raise ValueError("Invalid OHLC")
            bars.append({"open_time":stamp,"close_time":stamp+sec,
                         "open":o,"high":h,"low":l,"close":c})
            last=stamp
    return {"timeframe":timeframe,"bars":bars,"gaps":gaps,
            "contiguous":not gaps,"safe_for_direct_replay":bool(bars) and not gaps,
            "price_basis_verified_bid":False}
