"""Strict local CSV reader for the research attribution engine.

Accepts a NORMALIZED research CSV, NOT an MT5-native deal export.
Caller must first reconstruct full closed trades and compute MAE/MFE from
broker quotes. Source identity is unverified; no orders, account access, uploads.
"""
import csv
from pathlib import Path
from lsr02_trade_attribution import report

FIELDS=("id","symbol","strategy","opened_at","closed_at","gross_pnl_usd",
        "cost_usd","max_adverse_usd","max_favorable_usd","max_simultaneous_lots",
        "averaging_added","support_confirmed","two_six_near",
        "spread_widened","news_window","regime_changed")
NUMERIC=("opened_at","closed_at","gross_pnl_usd","cost_usd","max_adverse_usd",
         "max_favorable_usd","max_simultaneous_lots")
FLAGS=("averaging_added","support_confirmed","two_six_near","spread_widened",
       "news_window","regime_changed")

def load_report(path, *, top_n=20):
    p=Path(path)
    if not p.is_file() or p.stat().st_size>8*1024*1024:
        raise ValueError("CSV missing or over 8MiB")
    with p.open("r",encoding="utf-8-sig",newline="") as f:
        reader=csv.DictReader(f)
        if reader.fieldnames!=list(FIELDS):
            raise ValueError("Expected exact normalized attribution header")
        trades=[]
        for row in reader:
            if len(trades)>=100000 or None in row or any(v is None or not v.strip() for v in row.values()):
                raise ValueError("Malformed/oversized trade history")
            trade={k:row[k] for k in ("id","symbol","strategy")}
            try:
                for k in NUMERIC:trade[k]=float(row[k])
            except ValueError as exc:
                raise ValueError("Invalid numeric field") from exc
            for k in FLAGS:
                if row[k] not in ("true","false"):
                    raise ValueError("Use true/false flags explicitly")
                trade[k]=row[k]=="true"
            trades.append(trade)
    result=report(trades,top_n=top_n)
    result["data_provenance"]="LOCAL_NORMALIZED_CSV_UNVERIFIED"
    result["mt5_native_import_supported"]=False
    result["execution_allowed"]=False
    return result
