"""Five-calendar-month sample-window provisional PnL, bounded by actual source.
Not a complete LSR-02/03 or MT5 broker-quality backtest.
"""
import csv,datetime as dt,json
from pathlib import Path
START=dt.datetime(2026,4,25,tzinfo=dt.timezone.utc)
END=dt.datetime(2026,9,25,tzinfo=dt.timezone.utc)
def run():
    p=Path("public_xau_bars/XAUUSD_M1_UNVERIFIED_QUOTE.csv")
    n=0;first=last=None
    with p.open(newline="") as f:
        for r in csv.DictReader(f):
            t=dt.datetime.fromisoformat(r["timestamp_utc"])
            if first is None:first=t
            last=t
            if START<=t<END:n+=1
    source=json.loads(Path("public_xau_hypothetical_pnl.json").read_text())["trades_detail"]
    detail=json.loads(Path("public_xau_confidence_research.json").read_text())["details"]
    tiers={d["touch_close_utc"]:d["tier"] for d in detail}
    start,end=int(START.timestamp()),int(END.timestamp())
    in_window=sorted([t for t in source if start<=t["touch_close_utc"]<end],key=lambda t:t["touch_close_utc"])
    def calc(trades):
        equity=3000.;peak=equity;dd=0.
        for t in trades:
            equity*=1+.0025*t["r"]
            peak=max(peak,equity);dd=max(dd,(peak-equity)/peak)
        wins=sum(t["r"]>0 for t in trades)
        return {"count":len(trades),"wins":wins,"win_rate_pct":round(100*wins/len(trades),2) if trades else None,
                "end_usd":round(equity,2),"net_usd":round(equity-3000,2),
                "max_closed_trade_dd_pct":round(100*dd,3)}
    high=[t for t in in_window if tiers[t["touch_close_utc"]]=="higher_vhf"]
    out={"window_start_inclusive_utc":START.isoformat(),"window_end_exclusive_utc":END.isoformat(),
         "data_first_utc":first.isoformat(),"data_last_utc":last.isoformat(),
         "m1_rows_in_window":n,"bounds_covered":first<=START and last>=END-dt.timedelta(minutes=1),
         "all_matched_poi_research":calc(in_window),"vhf_at_least_050_research":calc(high),
         "broker_backtest_complete":False,"h4_verified":False,
         "notes":["Date bounds can be covered even when session holes are not verified.",
                  "VHF threshold was chosen on full data: in-sample selection.",
                  "Unknown brokerage bid-ask, true fills, and missing full LSR02 gating."]}
    Path("public_xau_five_month_study.json").write_text(json.dumps(out,indent=2)+"\n")
    print(json.dumps(out))
if __name__=="__main__":run()
