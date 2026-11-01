"""Chronological stability check for XAU 1.5R vs 2R target hypotheses.
Research only; the TP alternatives were already compared on all data,
so this split is NOT an independent out-of-sample validation.
"""
import datetime as dt,json
from pathlib import Path
from orrery_xau_hypothetical_pnl import simulate

UTC=dt.timezone.utc
START=int(dt.datetime(2026,4,25,tzinfo=UTC).timestamp())
CUT=int(dt.datetime(2026,7,1,tzinfo=UTC).timestamp())
END=int(dt.datetime(2026,9,25,tzinfo=UTC).timestamp())

def replay(rows):
    equity=3000.;peak=equity;dd=0.;wins=0
    for t in sorted(rows,key=lambda r:r["touch_close_utc"]):
        wins+=int(t["r"]>0)
        equity*=1+.0025*t["r"]
        peak=max(peak,equity);dd=max(dd,(peak-equity)/peak)
    return {"trades":len(rows),"wins":wins,
            "win_rate_pct":round(100*wins/len(rows),2) if rows else None,
            "net_usd":round(equity-3000,2),
            "mean_r":round(sum(t["r"] for t in rows)/len(rows),4) if rows else None,
            "max_closed_trade_dd_pct":round(dd*100,3)}

def run():
    root=Path("public_xau_bars")
    results={}
    for target in (1.5,2.0):
        x=simulate(root/"XAUUSD_M1_UNVERIFIED_QUOTE.csv",
                   Path("public_xau_sequence_report.json"),
                   spread_usd=.6,stop_usd=6.,reward_r=target)
        trades=x["trades_detail"]
        results[str(target)]={
            "pre_july":replay([t for t in trades if START<=t["touch_close_utc"]<CUT]),
            "july_to_sept":replay([t for t in trades if CUT<=t["touch_close_utc"]<END])
        }
    out={"status":"DESCRIPTIVE_SPLIT_NO_TARGET_OPTIMIZATION",
         "period":"2026-04-25 to 2026-09-25 exclusive",
         "cut_utc":"2026-07-01T00:00:00Z",
         "models":results,"high_lot_enabled":False,
         "warning":"Target hypotheses 1.5R and 2R were previously compared on this full data; this is not out-of-sample evidence."}
    Path("public_xau_tp_stability_split.json").write_text(json.dumps(out,indent=2)+"\n")
    print(json.dumps(out))
if __name__=="__main__":run()
