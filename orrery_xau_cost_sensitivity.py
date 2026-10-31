"""Research-only cost and stop-size sensitivity of the same XAUUSD candidate set."""
import json,hashlib
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
                          "wins":result["winners"],"losses":result["losers"],
                          "assumptions":result["assumptions"],
                          "resolved_total_r":round(sum(t["r"] for t in result["trades_detail"]),5),
                          "mean_resolved_r":round(sum(t["r"] for t in result["trades_detail"])/result["trades"],5) if result["trades"] else None,
                          "unresolved_or_unmodeled":result["skipped_incomplete"],
                          "full_candidate_effect_evaluable":result["skipped_incomplete"]==0})
    baseline=next(x for x in cases if x["spread_usd"]==0.6 and x["stop_distance_usd"]==6.0)
    report={"model":"HYPOTHETICAL ONLY, not broker fill backtest",
            "baseline":baseline,"scenarios":cases,
            "scope":"FULL_AVAILABLE_SOURCE_NOT_FIVE_MONTH_WINDOW",
            "parameter_units":"spread_usd and stop_distance_usd are XAUUSD quote-price units, not account-dollar fees",
            "source_m1_sha256":hashlib.sha256(src.read_bytes()).hexdigest(),
            "source_candidates_sha256":hashlib.sha256(candidates.read_bytes()).hexdigest(),
            "selection_allowed":False,"execution_allowed":False,
            "broker_costs_verified":False,
            "comparison_warning":"Stops differ across scenarios; skipped outcomes stay unknown. This grid does not isolate spread effects across different stops.",
            "positive_scenarios":sum(x["net_usd"]>0 for x in cases),
            "total_scenarios":len(cases),
            "warnings":["Small inspected sample; resolved and unresolved counts are reported per scenario; H4 unverified","source is non-broker quote","no account-level simultaneous-position constraints","parameters not calibrated to actual spread, commission or swaps"]}
    Path("public_xau_cost_sensitivity.json").write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps(report))
if __name__=="__main__":run()
