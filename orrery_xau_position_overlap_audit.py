"""Audit overlap and open-position concurrency in XAU research signals.

Descriptive research only. Trade profit simulations are not portfolio-level
executions, and overlapping entries can overstate achievable sizing.
"""
import json,datetime as dt
from pathlib import Path
from orrery_xau_hypothetical_pnl import simulate

START=int(dt.datetime(2026,4,25,tzinfo=dt.timezone.utc).timestamp())
END=int(dt.datetime(2026,9,25,tzinfo=dt.timezone.utc).timestamp())

def overlap_audit(trades):
    trades=sorted((t for t in trades if START<=t["touch_close_utc"]<END),
                  key=lambda t:(t["touch_close_utc"],t["exit_time_utc"]))
    active=[];overlap=0;max_concurrent=0;overlap_by_side={"BUY":0,"SELL":0}
    for t in trades:
        # Existing position exits at the start of an M1 minute. Equal exit
        # and entry timestamps are not marked as concurrent.
        active=[x for x in active if x>t["touch_close_utc"]]
        if active:
            overlap+=1
            overlap_by_side[t["side"]]+=1
        active.append(t["exit_time_utc"])
        max_concurrent=max(max_concurrent,len(active))
    return {"trades":len(trades),"entries_while_position_open":overlap,
            "overlap_entry_pct":round(overlap/len(trades)*100,2) if trades else None,
            "maximum_concurrent_positions":max_concurrent,
            "overlap_entries_by_side":overlap_by_side}

def run():
    root=Path("public_xau_bars")
    sources={
      "LSR_VHF":"public_xau_sequence_report.json",
      "M15_DIRECT":"public_xau_m15_breakout_candidates.json",
      "M15_RETEST":"public_xau_m15_retest_candidates.json"
    }
    results={}
    for name,path in sources.items():
        sim=simulate(root/"XAUUSD_M1_UNVERIFIED_QUOTE.csv",
                     Path(path),reward_r=1.5)
        results[name]=overlap_audit(sim["trades_detail"])
    out={"status":"IN_SAMPLE_POSITION_OVERLAP_AUDIT",
         "period_utc":"2026-04-25 to 2026-09-25 exclusive",
         "results":results,"portfolio_equity_execution_verified":False,
         "automatic_trade_execution_enabled":False,
         "warning":"Overlap checked using modeled entry and exit timestamps, not broker fills. Does not net opposing exposures or model account margin."}
    Path("public_xau_position_overlap_audit.json").write_text(json.dumps(out,indent=2)+"\n")
    print(json.dumps(out))
if __name__=="__main__":run()
