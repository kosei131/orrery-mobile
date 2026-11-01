"""Research-only: evaluate LSR-02 structure on uninterrupted market-bar segments.

This measures historical structural evidence, never executed trades or PnL.
Each segment resets pivots; no future bars are used for individual snapshots.
"""
import json
from collections import Counter
from pathlib import Path
from orrery_real_bars_lsr_bridge import load
from lsr02_structure import detect

def inspect(bars_path, timeframe, min_bars=30):
    parsed=load(bars_path,timeframe)
    segments=[];current=[];previous=None
    interval={"M5":300,"M15":900,"H4":14400}[timeframe]
    for bar in parsed["bars"]:
        if previous is not None and bar["close_time"]-previous!=interval:
            if current:segments.append(current)
            current=[]
        current.append(bar);previous=bar["close_time"]
    if current:segments.append(current)
    qualified=[s for s in segments if len(s)>=min_bars]
    event_counts=Counter()
    # Full-segment structure event report is descriptive only; detect's internal pivots
    # use confirmation bars, and each event's known_at is the closing timestamp.
    for segment in qualified:
        result=detect(segment,as_of=segment[-1]["close_time"],interval=interval)
        event_counts.update(e["kind"] for e in result["events"])
    return {"timeframe":timeframe,"total_bars":len(parsed["bars"]),
            "segments":len(segments),"eligible_segments":len(qualified),
            "eligible_bars":sum(map(len,qualified)),
            "longest_contiguous_bars":max(map(len,segments),default=0),
            "event_counts":dict(event_counts),
            "trades_executed":0,"win_rate":None,"profit_usd":None,
            "caution":"Structure only; not matched entries/exits, no broker fill simulation"}
if __name__=="__main__":
    base=Path("public_xau_bars")
    outputs={tf:inspect(base/f"XAUUSD_{tf}_UNVERIFIED_QUOTE.csv",tf) for tf in ("M5","M15","H4")}
    Path("public_xau_structure_report.json").write_text(json.dumps(outputs,indent=2)+"\n")
    print(json.dumps(outputs))
