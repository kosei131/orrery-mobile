#!/usr/bin/env python3
"""Convert independently sourced UTC XAUUSD M1 sample to bid-like OHLC research input.
IMPORTANT: source is publisher OHLC (quote basis not broker verified), never claim
actual bid/ask, spread or fills. Refuse timezone-naive timestamps and gaps in bars.
"""
import argparse,csv,datetime as dt,json
from pathlib import Path
from orrery_m1_complete_bars import aggregate

def run(source:Path,dest:Path):
    dest.mkdir(parents=True,exist_ok=True)
    m1=dest/"XAUUSD_M1_UNVERIFIED_QUOTE.csv"
    rows=0
    with source.open(newline="",encoding="utf-8-sig") as fp, m1.open("w",newline="",encoding="utf-8") as out:
        reader=csv.DictReader(fp)
        needed={"datetime","open","high","low","close"}
        if not needed.issubset(reader.fieldnames or []):raise ValueError("Unexpected source schema")
        writer=csv.writer(out);writer.writerow(["timestamp_utc","bid_open","bid_high","bid_low","bid_close"])
        prior=None
        for row in reader:
            t=dt.datetime.fromisoformat(row["datetime"].replace("Z","+00:00"))
            if t.tzinfo is None or t.utcoffset()!=dt.timedelta(0):
                raise ValueError("Refusing source timestamps without explicit UTC offset")
            if prior is not None and t<=prior:raise ValueError("Nonincreasing timestamp")
            prior=t
            writer.writerow([t.isoformat()]+[row[k] for k in ("open","high","low","close")])
            rows+=1
    report={"source":"GetData Finance public XAUUSD sample","source_rows":rows,
            "utc_offsets_verified":True,"quote_basis_broker_verified":False,
            "bid_field_name_compatibility_only":True,
            "backtest_profit_validated":False,"periods":{}}
    for p in ("M5","M15","H4"):
        report["periods"][p]=aggregate(m1,dest/f"XAUUSD_{p}_UNVERIFIED_QUOTE.csv",p)
    (dest/"report.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    return report
if __name__=="__main__":
    a=argparse.ArgumentParser();a.add_argument("source",type=Path);a.add_argument("--out",type=Path,required=True)
    v=a.parse_args();print(json.dumps(run(v.source,v.out),indent=2))
