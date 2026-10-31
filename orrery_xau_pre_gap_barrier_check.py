"""Resolve barrier hits before a research M1 data gap; leave remainder censored.
The spread is synthetic. Entries are never claimed to be broker fills.
"""
import csv,json,datetime as dt
from pathlib import Path
from orrery_xau_hypothetical_pnl import evaluate_exit_bar

def run():
    root=Path("public_xau_bars")
    audit=json.loads(Path("public_xau_m1_future_window_bias.json").read_text())
    with (root/"XAUUSD_M1_UNVERIFIED_QUOTE.csv").open(newline="",encoding="utf-8") as f:
        bars=[(int(dt.datetime.fromisoformat(x["timestamp_utc"]).timestamp()),
               float(x["bid_open"]),float(x["bid_high"]),float(x["bid_low"])) for x in csv.DictReader(f)]
    indices={bar[0]:i for i,bar in enumerate(bars)}
    outcomes={}
    for target_r in (1.5,2.0):
        rows=[];resolved=0;unresolved=0
        for event in audit["event_details"]:
            if event["reason"]=="full_horizon":continue
            idx=indices.get(event["touch_close_utc"])
            if idx is None:
                rows.append({"touch_close_utc":event["touch_close_utc"],"outcome":"NO_ENTRY_BAR"});unresolved+=1;continue
            side=event["side"];entry=bars[idx][1]+(.6 if side=="BUY" else 0)
            stop=entry-6 if side=="BUY" else entry+6
            target=entry+6*target_r if side=="BUY" else entry-6*target_r
            hit=None;time=None
            for bar in bars[idx:idx+event["contiguous_m1_available"]]:
                hit=evaluate_exit_bar(side,entry,stop,target,bar[2],bar[3],.6)
                if hit:
                    time=bar[0];break
            if hit:resolved+=1
            else:unresolved+=1
            rows.append({"touch_close_utc":event["touch_close_utc"],"side":side,
                         "contiguous_minutes":event["contiguous_m1_available"],
                         "outcome":hit.upper() if hit else "CENSORED_BEFORE_BARRIER",
                         "barrier_hit_utc":time})
        outcomes[str(target_r)]={"resolved_before_gap":resolved,"unresolved":unresolved,"details":rows}
    out={"status":"CENSORED_M1_BARRIER_CHECK","results":outcomes,
         "synthetic_spread_usd":.6,"stop_usd":6.0,"high_lot_enabled":False,
         "warning":"Recorded OHLC highs/lows do not prove executable fills or same-minute ordering. Stop prioritized."}
    Path("public_xau_pre_gap_barrier_check.json").write_text(json.dumps(out,indent=2)+"\n")
    print(json.dumps(out))
if __name__=="__main__":run()
