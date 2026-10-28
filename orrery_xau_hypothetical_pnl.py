"""Explicitly hypothetical XAUUSD M1 event-touch PnL from verified research candidates.
Not broker fills, not validated LSR-02/03 and not a six-month MT5 backtest.
Uses first NEXT M1 bar after a confirmed retouch M5 close (avoids same-bar hindsight).
Stops and targets evaluated conservatively; same-minute both hit means STOP.
"""
import csv,json,datetime as dt
from pathlib import Path

def evaluate_exit_bar(side, entry, stop, target, bid_high, bid_low, spread_usd):
    """Returns stop, target or none; all quoted bars are assumed bid.
    SELL exits require buying at synthetic ask (bid + spread).
    If both barriers touch in one M1 bar, stop takes priority.
    """
    if side not in ("BUY", "SELL") or spread_usd<0:
        raise ValueError("Invalid side or spread")
    stop_hit=(bid_low<=stop if side=="BUY" else bid_high+spread_usd>=stop)
    target_hit=(bid_high>=target if side=="BUY" else bid_low+spread_usd<=target)
    if stop_hit:return "stop"
    if target_hit:return "target"
    return None

def simulate(m1_path,report_path,spread_usd=0.6,stop_usd=6.0,reward_r=2.0,initial=3000.0,risk_fraction=.0025,horizon_mins=120):
    if spread_usd<0 or stop_usd<=0 or reward_r<=0 or initial<=0 or not 0<risk_fraction<=1 or horizon_mins<1:
        raise ValueError("Invalid research simulation parameters")
    evidence=json.loads(Path(report_path).read_text())["retouch_evidence"]
    with open(m1_path,newline="",encoding="utf-8") as f:
        bars=[(int(dt.datetime.fromisoformat(x["timestamp_utc"]).timestamp()),
               float(x["bid_open"]),float(x["bid_high"]),float(x["bid_low"]),float(x["bid_close"]))
              for x in csv.DictReader(f)]
    by_time={x[0]:i for i,x in enumerate(bars)}
    equity=initial;peak=initial;max_dd=0;trades=[];skipped=0
    for e in sorted(evidence,key=lambda x:x["first_poi_touch_close"]):
        entry_time=e["first_poi_touch_close"]
        idx=by_time.get(entry_time)
        if idx is None:skipped+=1;continue
        # Entry at M1 open beginning exactly when M5 touch bar has just closed.
        # Walk only the observed contiguous minutes. A later gap must not
        # retroactively discard a stop/target already reached.
        future=bars[idx:idx+horizon_mins]
        contiguous=1
        while contiguous<len(future) and future[contiguous][0]-future[contiguous-1][0]==60:
            contiguous+=1
        complete=(contiguous==horizon_mins)
        future=future[:contiguous]
        side=e["side"];ref=future[0][1]
        entry=ref+spread_usd if side=="BUY" else ref
        stop=entry-stop_usd if side=="BUY" else entry+stop_usd
        target=entry+stop_usd*reward_r if side=="BUY" else entry-stop_usd*reward_r
        outcome=None
        exit_time=None
        for bar in future:
            high,low=bar[2],bar[3]
            exit_kind=evaluate_exit_bar(side,entry,stop,target,high,low,spread_usd)
            if exit_kind=="stop":outcome=-1.0;exit_time=bar[0];break
            if exit_kind=="target":outcome=reward_r;exit_time=bar[0];break
        if outcome is None and not complete:
            # Censored at the feed gap or source end: no synthetic liquidation.
            skipped+=1
            continue
        if outcome is None:
            exit_time=future[-1][0]+60
            exit_bid=future[-1][4]
            exit_price=exit_bid if side=="BUY" else exit_bid+spread_usd
            outcome=((exit_price-entry) if side=="BUY" else (entry-exit_price))/stop_usd
        stake=equity*risk_fraction
        pnl=stake*outcome;equity+=pnl;peak=max(peak,equity);max_dd=max(max_dd,(peak-equity)/peak)
        trades.append({"touch_close_utc":entry_time,"side":side,"entry_assumed":entry,"exit_time_utc":exit_time,"r":round(outcome,5),"pnl_usd":round(pnl,4)})
    return {"method":"HYPOTHETICAL next-M1-open fixed-stop fixed-2R research only",
            "trades":len(trades),"skipped_incomplete":skipped,"winners":sum(t["r"]>0 for t in trades),
            "losers":sum(t["r"]<0 for t in trades),"initial_usd":initial,
            "end_usd":round(equity,2),"net_usd":round(equity-initial,2),
            "max_drawdown_pct":round(100*max_dd,3),"assumptions":{"spread_usd":spread_usd,"stop_distance_usd":stop_usd,"target_r":reward_r,"risk_fraction":risk_fraction,"timeout_minutes":horizon_mins,"entry":"next M1 open after M5 POI touch confirms"},
            "not_live_or_mt5_fills":True,"h4_unverified":True,"source_mid_price_not_bid_ask":True,
            "trades_detail":trades}
if __name__=="__main__":
    result=simulate(Path("public_xau_bars/XAUUSD_M1_UNVERIFIED_QUOTE.csv"),Path("public_xau_sequence_report.json"))
    Path("public_xau_hypothetical_pnl.json").write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps({k:v for k,v in result.items() if k!="trades_detail"}))
