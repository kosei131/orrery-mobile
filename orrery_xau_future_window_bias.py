"""Quantify selection bias from skipping any entry without full 120 contiguous future M1 bars.
No assumed fills, no orders, and no interpolation across missing candles.
"""
import csv,datetime as dt,json
from pathlib import Path

def audit(m1_path,report_path,horizon=120):
    with open(m1_path,newline="",encoding="utf-8") as f:
        ts=[int(dt.datetime.fromisoformat(r["timestamp_utc"]).timestamp()) for r in csv.DictReader(f)]
    index={t:i for i,t in enumerate(ts)}
    events=json.loads(Path(report_path).read_text())["retouch_evidence"]
    records=[];reason_counts={}
    for e in sorted(events,key=lambda x:x["first_poi_touch_close"]):
        when=e["first_poi_touch_close"];i=index.get(when)
        if i is None:
            reason="missing_entry_minute";n=0
        else:
            n=1
            while n<horizon and i+n<len(ts) and ts[i+n]-ts[i+n-1]==60:n+=1
            reason="full_horizon" if n==horizon else ("end_of_source" if i+n==len(ts) else "gap_before_horizon")
        reason_counts[reason]=reason_counts.get(reason,0)+1
        records.append({"touch_close_utc":when,"side":e["side"],"contiguous_m1_available":n,"reason":reason})
    out={"status":"M1_FUTURE_WINDOW_SELECTION_AUDIT","requested_horizon_mins":horizon,
         "events":len(events),"reason_counts":reason_counts,
         "event_details":records,"trading_enabled":False,
         "warning":"Requiring 120 future contiguous M1 bars conditions inclusion on FUTURE data. Incomplete events are censored, not zero-profit or executable trades."}
    return out
if __name__=="__main__":
    out=audit(Path("public_xau_bars/XAUUSD_M1_UNVERIFIED_QUOTE.csv"),Path("public_xau_sequence_report.json"))
    Path("public_xau_m1_future_window_bias.json").write_text(json.dumps(out,indent=2)+"\n")
    print(json.dumps({k:v for k,v in out.items() if k!="event_details"}))
