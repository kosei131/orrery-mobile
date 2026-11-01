"""Measure genuinely contiguous H4 UTC-grid windows; never synthesize closed bars."""
import json,datetime as dt
from pathlib import Path
from orrery_real_bars_lsr_bridge import load

def analyze(path):
    bars=load(path,"H4")["bars"]
    windows=[]
    if bars:
        start=prev=bars[0]["open_time"];count=1
        for b in bars[1:]:
            stamp=b["open_time"]
            if stamp-prev==14400:count+=1
            else:
                windows.append((start,prev,count))
                start=stamp;count=1
            prev=stamp
        windows.append((start,prev,count))
    sorted_windows=sorted(windows,key=lambda w:w[2],reverse=True)
    def utc(t):return dt.datetime.fromtimestamp(t,dt.timezone.utc).isoformat()
    report={"status":"OBSERVED_H4_CONTIGUITY_ONLY",
            "source_h4_bars":len(bars),"contiguous_segments":len(windows),
            "segments_at_least_6_bars":sum(w[2]>=6 for w in windows),
            "segments_at_least_12_bars":sum(w[2]>=12 for w in windows),
            "bars_in_segments_at_least_12":sum(w[2] for w in windows if w[2]>=12),
            "longest_segment_bars":max((w[2] for w in windows),default=0),
            "top_segments":[{"start_utc":utc(a),"last_open_utc":utc(b),"bars":n}
                            for a,b,n in sorted_windows[:8]],
            "bridge_gaps":False,"allow_live_trading":False,
            "warning":"H4 session breaks are not broker-calendar verified. Contiguous UTC bars alone do not prove signal quality."}
    return report
if __name__=="__main__":
    r=analyze(Path("public_xau_bars/XAUUSD_H4_UNVERIFIED_QUOTE.csv"))
    Path("public_xau_h4_contiguous_windows.json").write_text(json.dumps(r,indent=2)+"\n")
    print(json.dumps(r))
