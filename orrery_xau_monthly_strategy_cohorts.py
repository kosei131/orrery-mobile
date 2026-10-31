"""Monthly diagnostic of three XAU research models, fixed 1.5R exits.
Descriptive only, no parameter selection based on in-sample outcomes.
"""
import json,datetime as dt
from pathlib import Path
from collections import defaultdict
from orrery_xau_hypothetical_pnl import simulate

START=int(dt.datetime(2026,4,25,tzinfo=dt.timezone.utc).timestamp())
END=int(dt.datetime(2026,9,25,tzinfo=dt.timezone.utc).timestamp())
SOURCES={"LSR_VHF":"public_xau_sequence_report.json",
         "M15_DIRECT":"public_xau_m15_breakout_candidates.json",
         "M15_RETEST":"public_xau_m15_retest_candidates.json"}
def run():
    root=Path("public_xau_bars")
    results={}
    for name,path in SOURCES.items():
        data=simulate(root/"XAUUSD_M1_UNVERIFIED_QUOTE.csv",Path(path),reward_r=1.5)
        months=defaultdict(list)
        for trade in data["trades_detail"]:
            t=trade["touch_close_utc"]
            if START<=t<END:
                month=dt.datetime.fromtimestamp(t,dt.timezone.utc).strftime("%Y-%m")
                months[month].append(trade)
        details={}
        for month,trades in sorted(months.items()):
            total_r=sum(t["r"] for t in trades)
            details[month]={"trades":len(trades),"wins":sum(t["r"]>0 for t in trades),
                            "total_r":round(total_r,4),
                            "mean_r":round(total_r/len(trades),4)}
        results[name]={"months":details,"positive_months":sum(v["total_r"]>0 for v in details.values()),
                       "negative_months":sum(v["total_r"]<0 for v in details.values())}
    report={"status":"XAU_MONTHLY_COHORT_DIAGNOSTIC","period":"2026-04-25 to 2026-09-25 exclusive",
            "target_r":1.5,"results":results,
            "broker_verified":False,"automatic_trading":False,
            "warning":"Calendar boundary months are partial. Closed-trade outcomes are hypothetical and subject to assumed costs."}
    Path("public_xau_monthly_strategy_cohorts.json").write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps(report))
if __name__=="__main__":run()
