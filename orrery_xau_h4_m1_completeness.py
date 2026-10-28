"""Classify XAU missing H4 slots by observed source M1 candle count.
Research-only. Missing quotes must never be synthesized or treated as closed market.
"""
import json,collections
from pathlib import Path

def run():
    src=json.loads(Path("public_xau_h4_m1_gap_crosscheck.json").read_text())
    details=src["details"]
    counts=collections.Counter()
    examples=[]
    for row in details:
        n=row["observed_m1_bars_in_slot"]
        kind=("empty" if n==0 else "complete_240" if n==240 else "partial_1_to_239" if 0<n<240 else "overfull")
        counts[kind]+=1
        if kind!="empty" and len(examples)<12:
            examples.append({"open_utc":row["missing_h4_open_utc"],"m1_bars":n,"category":kind})
    out={"status":"H4_SOURCE_COMPLETENESS_RESEARCH","missing_h4_slots":len(details),
         "m1_slot_classification":dict(counts),"examples":examples,
         "full_h4_rebuild_allowed":False,"h4_trend_verified":False,
         "warning":"240 M1 bars is only a completeness criterion, not a verified broker-session or H4 trend signal."}
    Path("public_xau_h4_m1_completeness.json").write_text(json.dumps(out,indent=2)+"\n")
    print(json.dumps(out))
if __name__=="__main__":run()
