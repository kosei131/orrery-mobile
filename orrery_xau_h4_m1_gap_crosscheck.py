"""Audit H4 gaps against observed underlying M1 activity, without assuming sessions.

If there are no M1 quotes in a missing H4 grid slot, classify it as
NO_OBSERVED_QUOTES, not as an officially confirmed market closure.
Observed M1 quotes in a missing H4 interval indicate aggregation/data loss.
"""
import csv,datetime as dt,json
from pathlib import Path
from bisect import bisect_left
from orrery_real_bars_lsr_bridge import load

H4=14400
def audit(root=Path("public_xau_bars")):
    h4=load(root/"XAUUSD_H4_UNVERIFIED_QUOTE.csv","H4")
    m1_path=root/"XAUUSD_M1_UNVERIFIED_QUOTE.csv"
    timestamps=[]
    with m1_path.open(newline="",encoding="utf-8") as f:
        for r in csv.DictReader(f):
            timestamps.append(int(dt.datetime.fromisoformat(r["timestamp_utc"]).timestamp()))
    timestamps.sort()
    details=[];with_quotes=0;without_quotes=0;missing_slots=0
    for gap in h4["gaps"]:
        prev=gap["after_open"];nxt=gap["before_open"]
        for slot in range(prev+H4,nxt,H4):
            missing_slots+=1
            # M1 bars are indexed by their open time; compare UTC grid slot.
            n=bisect_left(timestamps,slot+H4)-bisect_left(timestamps,slot)
            if n:with_quotes+=1
            else:without_quotes+=1
            details.append({"missing_h4_open_utc":dt.datetime.fromtimestamp(slot,dt.timezone.utc).isoformat(),
                            "observed_m1_bars_in_slot":n,
                            "class":"UNEXPLAINED_AGGREGATION_GAP" if n else "NO_OBSERVED_M1_QUOTES"})
    out={"status":"H4_M1_CROSSCHECK_ONLY","h4_gap_count":len(h4["gaps"]),
         "missing_h4_slots":missing_slots,"slots_with_m1_quotes":with_quotes,
         "slots_without_m1_quotes":without_quotes,
         "feed_session_calendar_verified":False,"h4_bridge_allowed":False,
         "details":details,
         "warning":"No M1 quote does not prove market closure; quote source is not verified MT5 broker feed."}
    Path("public_xau_h4_m1_gap_crosscheck.json").write_text(json.dumps(out,indent=2)+"\n")
    print(json.dumps({k:v for k,v in out.items() if k!="details"}))
if __name__=="__main__":audit()
