"""Research-only comparison: POI retest with vs without VHF gate.
Uses identical source M1 simulator and same assumed costs. Not live-ready.
"""
import json
from pathlib import Path
from lsr02_structure import detect
from lsr03_vhf import calculate
from orrery_real_bars_lsr_bridge import load
from orrery_public_xau_sequence_study import segments
from orrery_xau_hypothetical_pnl import simulate

def run(root=Path("public_xau_bars")):
    m15=load(root/"XAUUSD_M15_UNVERIFIED_QUOTE.csv","M15")["bars"]
    m5=load(root/"XAUUSD_M5_UNVERIFIED_QUOTE.csv","M5")["bars"]
    events15=[];events5=[];m5_by_segment={}
    for bars,sec,out in ((m15,900,events15),(m5,300,events5)):
        for seg_idx,g in enumerate(segments(bars,sec)):
            if len(g)<8:continue
            d=detect(g,as_of=g[-1]["close_time"],interval=sec)
            if sec==300:m5_by_segment[seg_idx]=g
            for e in d["events"]:
                if (sec==900 and e["kind"]=="SWEEP") or (sec==300 and e["kind"] in ("BOS","CHoCH")):
                    out.append({"time":e["known_at"],"direction":e["direction"],
                                "poi":e.get("poi"),"segment_start":g[0]["close_time"],
                                "segment_index":seg_idx})
    all_rows=[];selected=[];used=set()
    m15_segments=segments(m15,900)
    for sweep in sorted(events15,key=lambda x:x["time"]):
        reverse="DOWN" if sweep["direction"]=="UP" else "UP"
        matches=[(i,x) for i,x in enumerate(events5)
                 if i not in used and x["direction"]==reverse
                 and sweep["time"]<x["time"]<=sweep["time"]+3600
                 and x["segment_start"]<=sweep["time"]]
        if not matches:continue
        idx,confirm=min(matches,key=lambda p:(p[1]["time"],p[0]))
        used.add(idx)
        poi=confirm["poi"]
        if not isinstance(poi,dict) or "high" not in poi or "low" not in poi:continue
        segment=m5_by_segment[confirm["segment_index"]]
        later=[b for b in segment if confirm["time"]<b["close_time"]<=confirm["time"]+3600]
        touches=[b for b in later if b["low"]<=poi["high"] and b["high"]>=poi["low"]]
        if not touches:continue
        row={"sweep_close":sweep["time"],"confirmation_close":confirm["time"],
             "first_poi_touch_close":touches[0]["close_time"],"side":"BUY" if reverse=="UP" else "SELL",
             "poi_low":poi["low"],"poi_high":poi["high"]}
        all_rows.append(row)
        old=next((g for g in m15_segments if g[0]["close_time"]<=sweep["time"]<=g[-1]["close_time"]),None)
        if old:
            known=[b for b in old if b["close_time"]<=sweep["time"]]
            v=calculate(known,period=14,as_of=sweep["time"],interval=900)
            if v["status"]=="OK" and v["value"]>=.4 and v["slope"]=="RISING":
                selected.append(dict(row,vhf_at_sweep=v["value"]))
    evidence_file=Path("public_xau_alt_no_vhf_evidence.json")
    evidence_file.write_text(json.dumps({"retouch_evidence":all_rows}))
    pnl=simulate(root/"XAUUSD_M1_UNVERIFIED_QUOTE.csv",evidence_file)
    old_pnl=json.loads(Path("public_xau_hypothetical_pnl.json").read_text())
    import datetime as dt
    start=int(dt.datetime(2026,4,25,tzinfo=dt.timezone.utc).timestamp())
    end=int(dt.datetime(2026,9,25,tzinfo=dt.timezone.utc).timestamp())
    breakdown={}
    for t in pnl["trades_detail"]:
        month=dt.datetime.fromtimestamp(t["touch_close_utc"],tz=dt.timezone.utc).strftime("%Y-%m")
        for key in (("side:"+t["side"]),("month:"+month)):
            if key not in breakdown:breakdown[key]={"trades":0,"wins":0,"sum_r":0.0}
            row=breakdown[key]
            row["trades"]+=1;row["wins"]+=int(t["r"]>0);row["sum_r"]+=t["r"]
    breakdown={k:dict(v,win_rate_pct=round(100*v["wins"]/v["trades"],2),
                       mean_r=round(v["sum_r"]/v["trades"],3))
               for k,v in breakdown.items()}
    five_month=[t for t in pnl["trades_detail"] if start<=t["touch_close_utc"]<end]
    five_month_by_side={side:{"trades":len(x),"wins":sum(t["r"]>0 for t in x),
                               "sum_r":round(sum(t["r"] for t in x),3)}
                        for side in ("BUY","SELL")
                        for x in [[t for t in five_month if t["side"]==side]]}
    # Record a loss only after its simulated exit time is known.
    # Reset each UTC day. This is still hypothetical replay, not broker trading.
    daily_loss_streak=0;current_day=None;pending=[]
    guarded_equity=3000.;guarded_peak=3000.;guarded_dd=0.;guarded_taken=0;guarded_skipped=0;guarded_wins=0
    for trade in sorted(pnl["trades_detail"],key=lambda t:t["touch_close_utc"]):
        entry_time=trade["touch_close_utc"]
        day=dt.datetime.fromtimestamp(entry_time,tz=dt.timezone.utc).date()
        if day!=current_day:
            current_day=day;daily_loss_streak=0
        newly_closed=sorted((p for p in pending if p["exit_time_utc"]<=entry_time),key=lambda p:p["exit_time_utc"])
        pending=[p for p in pending if p["exit_time_utc"]>entry_time]
        for closed in newly_closed:
            if dt.datetime.fromtimestamp(closed["exit_time_utc"],tz=dt.timezone.utc).date()==day:
                daily_loss_streak=daily_loss_streak+1 if closed["r"]<0 else 0
        if daily_loss_streak>=2:
            guarded_skipped+=1;continue
        guarded_taken+=1;guarded_wins+=int(trade["r"]>0)
        guarded_equity*=1+0.0025*trade["r"]
        guarded_peak=max(guarded_peak,guarded_equity)
        guarded_dd=max(guarded_dd,(guarded_peak-guarded_equity)/guarded_peak)
        pending.append(trade)
    daily_guard={"taken":guarded_taken,"skipped":guarded_skipped,
                 "wins":guarded_wins,"net_usd":round(guarded_equity-3000,2),
                 "max_closed_trade_dd_pct":round(100*guarded_dd,3),
                 "warning":"Outcome reuse and sequential equity replay; pending positions and balance are not fully account-executed."}
    result={"status":"RESEARCH_ABLATION_NOT_LSR02","matched_sweeps":len(used),"breakdown":breakdown,"daily_two_loss_guard_research":daily_guard,
            "five_month_no_vhf_by_side":five_month_by_side,
            "poi_touch_without_vhf":len(all_rows),"poi_touch_with_vhf":len(selected),
            "no_vhf_model":{"trades":pnl["trades"],"wins":pnl["winners"],"losses":pnl["losers"],
                "net_usd":pnl["net_usd"],"max_dd_pct":pnl["max_drawdown_pct"],"skipped":pnl["skipped_incomplete"]},
            "existing_vhf_model":{"trades":old_pnl["trades"],"wins":old_pnl["winners"],"losses":old_pnl["losers"],
                "net_usd":old_pnl["net_usd"],"max_dd_pct":old_pnl["max_drawdown_pct"]},
            "high_lot_enabled":False,"broker_verified":False,
            "warning":"Both variants in-sample. One-to-one pair matching is established before VHF gating; cost is assumed; source quote is not broker bid-ask."}
    Path("public_xau_alt_model_comparison.json").write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps(result))
if __name__=="__main__":run()
