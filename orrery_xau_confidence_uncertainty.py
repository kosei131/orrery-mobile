"""Research-only Wilson win-rate uncertainty and high-lot gating.
Uses observed outcomes; does not train, optimize, or enable orders.
"""
import json, math
from pathlib import Path

def wilson_lower(wins,n,z=1.96):
    if n<1:return None
    p=wins/n
    return (p+z*z/(2*n)-z*math.sqrt(p*(1-p)/n+z*z/(4*n*n)))/(1+z*z/n)

def report(path):
    data=json.loads(Path(path).read_text(encoding="utf-8"))
    groups={}
    for name,g in data["groups"].items():
        n=g["count"];wins=g["wins"]
        lower=wilson_lower(wins,n)
        groups[name]={"trades":n,"wins":wins,"observed_win_rate_pct":g["win_rate_pct"],
                      "wilson_95pct_lower_pct":round(lower*100,2) if lower is not None else None,
                      "mean_r":g["mean_r"]}
    high=groups["higher_vhf"]
    return {"status":"HYPOTHESIS_ONLY_HIGH_LOT_LOCKED",
            "target_win_rate_pct":95,
            "high_lot_enabled":False,
            "confidence_interval_method":"Wilson two-sided 95% lower endpoint",
            "groups":groups,
            "gate_requirements":["independent out-of-sample period","verified H4 and retest","broker quote spread/fees and realistic fills","portfolio level drawdown validation","sufficient observations for lower confidence bound"],
            "reason":"Three wins cannot establish 95% true win rate; selected threshold is in-sample."}
if __name__=="__main__":
    r=report(Path("public_xau_confidence_research.json"))
    Path("public_xau_confidence_uncertainty.json").write_text(json.dumps(r,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(r))
