"""Diagnostic audit of observed research losses; NOT strategy optimization or live trading."""
import csv,datetime as dt,json,collections,hashlib
from math import isfinite
from pathlib import Path

def excursions(candles, trade, spread):
    entry=trade['entry_assumed'];distance=trade['initial_stop_distance']
    start=trade['touch_close_utc'];end=trade['exit_time_utc'];side=trade['side']
    if (side not in ('BUY','SELL') or any(type(x) not in (int,float) or not isfinite(x)
        for x in (entry,distance,start,end,spread)) or entry<=0 or distance<=0 or spread<0 or end<start):
        raise ValueError('Valid trade and explicit spread required')
    # Exit timestamps at intraminute barriers are lower bounds. Exclude that
    # whole bar; TIMEOUT timestamps are bar closes, so its final bar is retained.
    prior=[c for c in candles if start<=c[0] and c[0]+60<=end]
    if any(b[0]<=a[0] for a,b in zip(prior,prior[1:])):
        raise ValueError('Ordered minute observations required')
    def metrics(window):
        if not window:return None,None
        favorable=max(c[1]-entry for c in window) if side=='BUY' else max(entry-c[2]-spread for c in window)
        adverse=max(entry-c[2] for c in window) if side=='BUY' else max(c[1]+spread-entry for c in window)
        return max(0.,favorable)/distance,max(0.,adverse)/distance
    mfe,mae=metrics(prior)
    return dict(mfe_r=mfe,mae_r=mae,fully_elapsed_minutes_observed=len(prior),
                exit_minute_order_known=False,executable_profit_capture_verified=False)


def run():
    source_bytes=Path("public_xau_hypothetical_pnl.json").read_bytes()
    source=json.loads(source_bytes);trades=source["trades_detail"]
    conf=json.loads(Path("public_xau_confidence_research.json").read_text())["details"]
    by_tier={r["touch_close_utc"]:r["tier"] for r in conf}
    path=Path("public_xau_bars/XAUUSD_M1_UNVERIFIED_QUOTE.csv")
    with path.open(newline="") as f:
        candles=[(int(dt.datetime.fromisoformat(x["timestamp_utc"]).timestamp()),float(x["bid_high"]),float(x["bid_low"]),float(x["bid_close"])) for x in csv.DictReader(f)]
    details=[]
    for t in trades:
        side=t['side']
        excursion=excursions(candles,t,source['assumptions']['spread_usd'])
        seconds=t["exit_time_utc"]-t["touch_close_utc"]
        reason=("stop" if t["exit_reason"].startswith("STOP") else "target" if t["exit_reason"]=="TP_INTRAMINUTE" else "timeout")
        details.append({"entry_utc":t["touch_close_utc"],"side":side,"tier":by_tier[t["touch_close_utc"]],
            "outcome_r":t["r"],"exit_reason":reason,"holding_minutes":seconds/60,
            **excursion})
    reasons=collections.Counter(d["exit_reason"] for d in details)
    losers=[x for x in details if x["outcome_r"]<0]
    out={"status":"DIAGNOSTIC_NO_ORDER_PERMISSION","trades":len(details),"losing_trades":len(losers),
         "exit_reasons":dict(reasons),
         "losers_by_tier":dict(collections.Counter(x["tier"] for x in losers)),
         "losers_by_side":dict(collections.Counter(x["side"] for x in losers)),
         "losers_with_observed_half_r_before_exit_minute":sum(x["mfe_r"] is not None and x["mfe_r"]>=.5 for x in losers),
         "losers_with_observed_one_r_before_exit_minute":sum(x["mfe_r"] is not None and x["mfe_r"]>=1 for x in losers),
         "losers_without_fully_elapsed_minute":sum(x["mfe_r"] is None for x in losers),
         "source_pnl_sha256":hashlib.sha256(source_bytes).hexdigest(),
         "assumptions":source["assumptions"],"execution_allowed":False,
         "details":details,"notes":["MFE/MAE use only fully elapsed minutes before exit timestamp; intraminute exit bar is excluded.","No observed full minute remains unknown, never zero. Full source gaps and broker fills are not certified.","MFE does not establish feasible stop move or profit capture."]}
    Path("public_xau_loss_diagnostic.json").write_text(json.dumps(out,indent=2)+"\n")
    print(json.dumps({k:v for k,v in out.items() if k!="details"}))
if __name__=="__main__":run()
