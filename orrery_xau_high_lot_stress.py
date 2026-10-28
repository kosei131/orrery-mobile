"""Counterfactual failure stress for in-sample VHF-based risk sizing.
For every combination of 1, 2, or 3 high-VHF winning candidates, replace
the realized 2R result with -1R. This is a loss stress test, not a forecast.
"""
import json,itertools
from pathlib import Path

def run():
    trades=json.loads(Path("public_xau_hypothetical_pnl.json").read_text())["trades_detail"]
    rows=json.loads(Path("public_xau_confidence_research.json").read_text())["details"]
    tier={x["touch_close_utc"]:x["tier"] for x in rows}
    trades=sorted(trades,key=lambda x:x["touch_close_utc"])
    ids=[i for i,t in enumerate(trades) if tier[t["touch_close_utc"]]=="higher_vhf"]
    def replay(replaced,scaled):
        equity=3000.;peak=3000.;dd=0.
        for i,t in enumerate(trades):
            risk=.005 if scaled and i in ids else .0025
            realized=-1 if i in replaced else t["r"]
            equity*=1+risk*realized
            peak=max(peak,equity);dd=max(dd,(peak-equity)/peak)
        return {"net_usd":round(equity-3000,2),"max_dd_pct":round(100*dd,3)}
    out=[]
    for n in range(4):
        alternatives=[replay(set(combo),True) for combo in itertools.combinations(ids,n)]
        baseline=[replay(set(combo),False) for combo in itertools.combinations(ids,n)]
        out.append({"forced_high_tier_losses":n,"cases":len(alternatives),
                    "high_lot_min_net_usd":min(x["net_usd"] for x in alternatives),
                    "high_lot_max_net_usd":max(x["net_usd"] for x in alternatives),
                    "base_lot_min_net_usd":min(x["net_usd"] for x in baseline),
                    "base_lot_max_net_usd":max(x["net_usd"] for x in baseline),
                    "high_lot_worst_dd_pct":max(x["max_dd_pct"] for x in alternatives)})
    result={"status":"COUNTERFACTUAL_RESEARCH_ONLY","high_vhf_trades":len(ids),
            "scenarios":out,"high_lot_enabled":False,
            "warning":"Selectively flipping wins to -1R is a fragility stress, not an empirical probability estimate or independent backtest."}
    Path("public_xau_high_lot_stress.json").write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps(result))
if __name__=="__main__":run()
