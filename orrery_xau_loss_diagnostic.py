"""Diagnostic audit of observed research losses; NOT strategy optimization or live trading."""
import csv,datetime as dt,json,collections
from pathlib import Path

def run():
    trades=json.loads(Path("public_xau_hypothetical_pnl.json").read_text())["trades_detail"]
    conf=json.loads(Path("public_xau_confidence_research.json").read_text())["details"]
    by_tier={r["touch_close_utc"]:r["tier"] for r in conf}
    path=Path("public_xau_bars/XAUUSD_M1_UNVERIFIED_QUOTE.csv")
    with path.open(newline="") as f:
        candles=[(int(dt.datetime.fromisoformat(x["timestamp_utc"]).timestamp()),float(x["bid_high"]),float(x["bid_low"]),float(x["bid_close"])) for x in csv.DictReader(f)]
    indices={row[0]:i for i,row in enumerate(candles)}
    details=[]
    for t in trades:
        start=indices[t["touch_close_utc"]];end=indices.get(t["exit_time_utc"],len(candles)-1)
        window=candles[start:min(end+1,len(candles))]
        side=t["side"];entry=t["entry_assumed"];spread=.6;stop=6.
        favorable=max(x[1]-entry for x in window) if side=="BUY" else max(entry-(x[2]+spread) for x in window)
        adverse=max(entry-x[2] for x in window) if side=="BUY" else max(x[1]+spread-entry for x in window)
        seconds=t["exit_time_utc"]-t["touch_close_utc"]
        reason=("stop" if abs(t["r"]+1)<1e-4 else "target" if abs(t["r"]-2)<1e-4 else "timeout")
        details.append({"entry_utc":t["touch_close_utc"],"side":side,"tier":by_tier[t["touch_close_utc"]],
            "outcome_r":t["r"],"exit_reason":reason,"holding_minutes":seconds/60,
            "mfe_r":round(favorable/stop,3),"mae_r":round(adverse/stop,3)})
    reasons=collections.Counter(d["exit_reason"] for d in details)
    losers=[x for x in details if x["outcome_r"]<0]
    out={"status":"DIAGNOSTIC_NO_ORDER_PERMISSION","trades":len(details),"losing_trades":len(losers),
         "exit_reasons":dict(reasons),
         "losers_by_tier":dict(collections.Counter(x["tier"] for x in losers)),
         "losers_by_side":dict(collections.Counter(x["side"] for x in losers)),
         "losing_trades_that_first_reached_half_r":sum(x["mfe_r"]>=.5 for x in losers),
         "losing_trades_that_first_reached_one_r":sum(x["mfe_r"]>=1 for x in losers),
         "details":details,"notes":["MFE/MAE are descriptive whole-minute price extremes; same-bar ordering is unknown.","Some end bars are included conservatively; no broker spreads or fills verified.","MFE does not establish feasible stop move or profit capture."]}
    Path("public_xau_loss_diagnostic.json").write_text(json.dumps(out,indent=2)+"\n")
    print(json.dumps({k:v for k,v in out.items() if k!="details"}))
if __name__=="__main__":run()
