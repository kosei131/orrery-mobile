"""Conservative H4 coverage diagnostic: distinguish expected closures from data loss.

Market calendar is NOT assumed. Report possible closures only; do not treat a
gap as contiguous without independently verified provider trading sessions.
"""
import datetime as dt
import json
from collections import Counter
from pathlib import Path
from orrery_real_bars_lsr_bridge import load

def classify_gap(prev_open,next_open):
    prev=dt.datetime.fromtimestamp(prev_open,dt.timezone.utc)
    nxt=dt.datetime.fromtimestamp(next_open,dt.timezone.utc)
    missing=(next_open-prev_open)//14400-1
    touches_weekend=any((prev+dt.timedelta(hours=h)).weekday()>=5
                        for h in range(4,int((nxt-prev).total_seconds()//3600),4))
    return {"after_open_utc":prev.isoformat(),"before_open_utc":nxt.isoformat(),
            "missing_h4_grid_bars":missing,
            "possible_market_closure":touches_weekend,
            "status":"UNVERIFIED_SESSION_CALENDAR",
            "safe_to_bridge_for_trading":False}

def audit(path):
    result=load(path,"H4")
    gs=[classify_gap(g["after_open"],g["before_open"]) for g in result["gaps"]]
    patterns=Counter((g["after_open_utc"][11:16],g["before_open_utc"][11:16],g["missing_h4_grid_bars"]) for g in gs)
    return {"source_h4_bars":len(result["bars"]),"gap_count":len(gs),
            "top_gap_patterns":[{"from_utc":a,"to_utc":b,"missing_h4_bars":n,"count":v}
                                for (a,b,n),v in patterns.most_common(12)],
            "weekend_intersecting_gaps":sum(g["possible_market_closure"] for g in gs),
            "gaps_without_weekend":sum(not g["possible_market_closure"] for g in gs),
            "example_gaps":gs[:20],
            "session_calendar_verified":False,
            "h4_safe_for_full_replay":False,
            "strategy_results":None}
if __name__=="__main__":
    path=Path("public_xau_bars/XAUUSD_H4_UNVERIFIED_QUOTE.csv")
    report=audit(path)
    Path("public_xau_h4_gap_report.json").write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps({k:v for k,v in report.items() if k!="example_gaps"}))
