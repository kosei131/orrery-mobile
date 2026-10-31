"""Research-only cost and stop-size sensitivity of the same XAUUSD candidate set."""
import json
from pathlib import Path
from orrery_xau_hypothetical_pnl import simulate

def run():
    src=Path("public_xau_bars/XAUUSD_M1_UNVERIFIED_QUOTE.csv")
    candidates=Path("public_xau_sequence_report.json")
    cases=[]
    for spread in (0.6,1.2,2.0):
        for stop in (4.0,6.0,10.0):
            result=simulate(src,candidates,spread_usd=spread,stop_usd=stop)
            cases.append({"spread_usd":spread,"stop_distance_usd":stop,
                          "trades":result["trades"],"skipped":result["skipped_incomplete"],
                          "net_usd":result["net_usd"],"max_dd_pct":result["max_drawdown_pct"],
                          "wins":result["winners"],"losses":result["losers"]})
    baseline=next(x for x in cases if x["spread_usd"]==0.6 and x["stop_distance_usd"]==6.0)
    report={"model":"HYPOTHETICAL ONLY, not broker fill backtest",
            "baseline":baseline,"scenarios":cases,
            "positive_scenarios":sum(x["net_usd"]>0 for x in cases),
            "total_scenarios":len(cases),
            "warnings":["12-event sample, H4 unverified","source is non-broker quote","no account-level simultaneous-position constraints","parameters not calibrated to actual spread, commission or swaps"]}
    Path("public_xau_cost_sensitivity.json").write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps(report))
if __name__=="__main__":run()
