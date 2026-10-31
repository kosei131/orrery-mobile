"""Independent breakout-retest research; no live trading or broker execution.
Confirm M15 breakout first, then a later CLOSED M5 bar retouches the
previous eight-M15-bar boundary and closes on breakout side.
Predeclared 60-minute retest limit; same 4h cooldown as breakout baseline.
"""
import json,datetime as dt
from pathlib import Path
from bisect import bisect_right
from orrery_real_bars_lsr_bridge import load
from orrery_public_xau_sequence_study import segments
from orrery_xau_hypothetical_pnl import simulate

START=int(dt.datetime(2026,4,25,tzinfo=dt.timezone.utc).timestamp())
END=int(dt.datetime(2026,9,25,tzinfo=dt.timezone.utc).timestamp())
def signals(root):
    m15=load(root/"XAUUSD_M15_UNVERIFIED_QUOTE.csv","M15")["bars"]
    m5=load(root/"XAUUSD_M5_UNVERIFIED_QUOTE.csv","M5")["bars"]
    t5=[x["close_time"] for x in m5]
    rows=[];last=-10**20
    for seg in segments(m15,900):
        for i in range(12,len(seg)):
            b=seg[i];prev=seg[i-8:i]
            upper=max(x["high"] for x in prev);lower=min(x["low"] for x in prev)
            up=seg[i-1]["close"]>seg[i-7]["close"]
            down=seg[i-1]["close"]<seg[i-7]["close"]
            side=("BUY" if up and b["close"]>upper else
                  "SELL" if down and b["close"]<lower else None)
            if not side or b["close_time"]-last<4*3600:continue
            # Cooldown begins at initial breakout, including those without retest.
            last=b["close_time"]
            level=upper if side=="BUY" else lower
            p=bisect_right(t5,b["close_time"])
            for k in range(p,len(m5)):
                x=m5[k]
                if x["close_time"]>b["close_time"]+3600:break
                # Must not bridge a missing M5 bar between breakout and retest.
                if k>p and x["close_time"]-m5[k-1]["close_time"]!=300:break
                if x["low"]<=level<=x["high"] and (
                    (side=="BUY" and x["close"]>level) or
                    (side=="SELL" and x["close"]<level)):
                    rows.append({"first_poi_touch_close":x["close_time"],"side":side,
                                 "breakout_close_utc":b["close_time"],
                                 "signal_source":"M15_breakout_then_M5_level_retest"})
                    break
    return rows
def run(root=Path("public_xau_bars")):
    entries=signals(root)
    p=Path("public_xau_m15_retest_candidates.json")
    p.write_text(json.dumps({"retouch_evidence":entries},indent=2)+"\n")
    results={}
    for target in (1.5,2.0):
        sim=simulate(root/"XAUUSD_M1_UNVERIFIED_QUOTE.csv",p,reward_r=target,
                     spread_usd=.6,stop_usd=6.)
        trades=sorted((x for x in sim["trades_detail"] if START<=x["touch_close_utc"]<END),
                      key=lambda x:x["touch_close_utc"])
        eq=3000.;peak=eq;dd=0.
        for x in trades:
            eq*=1+.0025*x["r"];peak=max(peak,eq);dd=max(dd,(peak-eq)/peak)
        results[str(target)]={"trades":len(trades),"wins":sum(x["r"]>0 for x in trades),
                               "win_rate_pct":round(100*sum(x["r"]>0 for x in trades)/len(trades),2) if trades else None,
                               "net_usd":round(eq-3000,2),
                               "max_closed_trade_dd_pct":round(dd*100,3),
                               "mean_r":round(sum(x["r"] for x in trades)/len(trades),4) if trades else None}
    report={"status":"IN_SAMPLE_BREAKOUT_RETEST_RESEARCH","candidates_all_dates":len(entries),
            "period":"2026-04-25 inclusive to 2026-09-25 exclusive",
            "results":results,"high_lot_enabled":False,"broker_verified":False,
            "caveat":"Does not model portfolio overlap; feed gaps, spread, slippage and broker fills unverified. Retest may not be achievable at assumed next M1 open."}
    Path("public_xau_m15_retest_comparison.json").write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps(report))
if __name__=="__main__":run()
