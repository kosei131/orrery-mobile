"""Independent M15 momentum breakout hypothesis for XAU, research only.

At each CLOSED M15 bar, compare its close with highs/lows of preceding
8 M15 candles, and require six-bar historical trend confirmation.
No VHF, POI, sweep, H4, hindsight pivots, or same-candle entry.
Minimum four-hour cooldown after each event to reduce overlapping signals.
This is a fixed, exploratory hypothesis, NOT a validated strategy.
"""
import json,datetime as dt
from pathlib import Path
from orrery_real_bars_lsr_bridge import load
from orrery_public_xau_sequence_study import segments
from orrery_xau_hypothetical_pnl import simulate

START=int(dt.datetime(2026,4,25,tzinfo=dt.timezone.utc).timestamp())
END=int(dt.datetime(2026,9,25,tzinfo=dt.timezone.utc).timestamp())

def candidates(m15_path):
    bars=load(m15_path,"M15")["bars"]
    out=[]
    last=-10**20
    for seg in segments(bars,900):
        for i in range(12,len(seg)):
            current=seg[i];previous=seg[i-8:i]
            trend_up=seg[i-1]["close"]>seg[i-7]["close"]
            trend_down=seg[i-1]["close"]<seg[i-7]["close"]
            side=("BUY" if trend_up and current["close"]>max(b["high"] for b in previous)
                  else "SELL" if trend_down and current["close"]<min(b["low"] for b in previous)
                  else None)
            if side and current["close_time"]-last>=4*3600:
                out.append({"first_poi_touch_close":current["close_time"],
                            "side":side,"signal_source":"closed_M15_8bar_breakout"})
                last=current["close_time"]
    return out

def run(root=Path("public_xau_bars")):
    events=candidates(root/"XAUUSD_M15_UNVERIFIED_QUOTE.csv")
    candidate_path=Path("public_xau_m15_breakout_candidates.json")
    candidate_path.write_text(json.dumps({"retouch_evidence":events},indent=2)+"\n")
    results={}
    for target in (1.5,2.0):
        sim=simulate(root/"XAUUSD_M1_UNVERIFIED_QUOTE.csv",candidate_path,
                     stop_usd=6.,spread_usd=.6,reward_r=target)
        trades=[x for x in sim["trades_detail"] if START<=x["touch_close_utc"]<END]
        eq=3000.;peak=eq;dd=0.
        for t in sorted(trades,key=lambda r:r["touch_close_utc"]):
            eq*=1+.0025*t["r"];peak=max(peak,eq);dd=max(dd,(peak-eq)/peak)
        results[str(target)]={"trades":len(trades),"wins":sum(t["r"]>0 for t in trades),
                               "net_usd":round(eq-3000,2),
                               "max_closed_trade_dd_pct":round(dd*100,3),
                               "mean_r":round(sum(t["r"] for t in trades)/len(trades),4) if trades else None}
    report={"status":"IN_SAMPLE_INDEPENDENT_M15_BREAKOUT",
            "period":"2026-04-25 inclusive to 2026-09-25 exclusive",
            "candidates_all_dates":len(events),"results":results,
            "model":"8-bar M15 breakout with prior 6-bar close slope, 4h cooldown",
            "broker_verified":False,"h4_filter_used":False,"high_lot_enabled":False,
            "warning":"Research only. Fixed stops/targets and spread assumptions, not genuine MT5 fills. Possible overlapping positions not modeled."}
    Path("public_xau_m15_breakout_comparison.json").write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps(report))
if __name__=="__main__":run()
