"""Stress censored XAU research entries without inventing trade fills.
The alternative outcomes below are *counterfactual bounds*, not executions.
"""
import json,datetime as dt
from pathlib import Path
from orrery_xau_hypothetical_pnl import simulate
START=int(dt.datetime(2026,4,25,tzinfo=dt.timezone.utc).timestamp())
END=int(dt.datetime(2026,9,25,tzinfo=dt.timezone.utc).timestamp())
def calc(known,unknown,unknown_r):
    # Equity updates only illustrative, with missing outcomes placed on their
    # candidate entry timestamps. No simultaneous-position account simulation.
    events=[(t["touch_close_utc"],t["r"]) for t in known]
    events.extend((r["touch_close_utc"],unknown_r) for r in unknown)
    equity=3000.;peak=equity;max_dd=0.
    for _,r in sorted(events):
        equity*=1+.0025*r
        peak=max(peak,equity)
        max_dd=max(max_dd,100*(peak-equity)/peak)
    return {"illustrative_net_usd":round(equity-3000,2),
            "illustrative_max_closed_dd_pct":round(max_dd,3)}
def run():
    path=Path("public_xau_bars/XAUUSD_M1_UNVERIFIED_QUOTE.csv")
    report=Path("public_xau_sequence_report.json")
    audit=json.loads(Path("public_xau_m1_future_window_bias.json").read_text())
    results={}
    for target in (1.5,2.0):
        simulation=simulate(path,report,reward_r=target)
        known=[x for x in simulation["trades_detail"] if START<=x["touch_close_utc"]<END]
        known_times={t["touch_close_utc"] for t in known}
        missing=[x for x in audit["event_details"] if START<=x["touch_close_utc"]<END and x["reason"]!="full_horizon" and x["touch_close_utc"] not in known_times]
        results[str(target)]={"observed_simulated_trades":len(known),
                              "censored_candidates":len(missing),
                              "censored_events":missing,
                              "unresolved_as_minus_1r":calc(known,missing,-1.0),
                              "unresolved_as_plus_target_r":calc(known,missing,target)}
    out={"status":"HYPOTHETICAL_CENSORING_STRESS_NOT_TRADES",
         "period_utc":"2026-04-25 inclusive to 2026-09-25 exclusive",
         "results":results,"mt5_execution_verified":False,
         "high_lot_enabled":False,
         "warning":"Unknown outcomes remain unknown. +/- scenario outcomes are not realized fills or rigorous bounds because stop/target may occur before the M1 gap."}
    Path("public_xau_censored_event_stress.json").write_text(json.dumps(out,indent=2)+"\n")
    print(json.dumps(out))
if __name__=="__main__":run()
