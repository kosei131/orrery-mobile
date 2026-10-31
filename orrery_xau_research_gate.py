"""Fail-closed research progression gate for three XAU candidate strategies.

Does not enable orders. Gates are predeclared research prerequisites, not
statistical proof of profitability or safe deployment.
"""
import json
from pathlib import Path

MIN_TRADES=100
MIN_ACTIVE_MONTHS=4
MAX_NEGATIVE_MONTH_SHARE=.25
MIN_MEAN_R=.10

def decide(model,months):
    vals=list(months.values())
    trades=sum(x["trades"] for x in vals)
    total_r=sum(x["total_r"] for x in vals)
    negative=sum(x["total_r"]<0 for x in vals)
    mean_r=total_r/trades if trades else None
    reasons=[]
    if trades<MIN_TRADES:reasons.append("INSUFFICIENT_TRADES")
    if len(vals)<MIN_ACTIVE_MONTHS:reasons.append("INSUFFICIENT_MONTHS")
    if vals and negative/len(vals)>MAX_NEGATIVE_MONTH_SHARE:reasons.append("NEGATIVE_MONTH_CONCENTRATION")
    if mean_r is None or mean_r<MIN_MEAN_R:reasons.append("LOW_OR_NEGATIVE_EXPECTANCY")
    return {"model":model,"trades":trades,"active_months":len(vals),
            "mean_r":round(mean_r,4) if mean_r is not None else None,
            "negative_months":negative,"research_gate":"PASS_FOR_FURTHER_OUT_OF_SAMPLE_RESEARCH" if not reasons else "BLOCK",
            "block_reasons":reasons}

def run():
    src=json.loads(Path("public_xau_monthly_strategy_cohorts.json").read_text())
    results={model:decide(model,item["months"]) for model,item in src["results"].items()}
    out={"status":"RESEARCH_PROGRESS_GATE_NOT_TRADE_AUTHORIZATION",
         "fixed_requirements":{"minimum_trades":MIN_TRADES,"minimum_active_months":MIN_ACTIVE_MONTHS,
                               "maximum_negative_month_share":MAX_NEGATIVE_MONTH_SHARE,"minimum_mean_r":MIN_MEAN_R},
         "results":results,"broker_verified":False,"live_enabled":False,"demo_auto_orders_enabled":False,
         "warning":"These heuristics cannot prove an edge, and passing them would permit only further untouched-data evaluation. All candidate data have already been inspected."}
    Path("public_xau_research_gate.json").write_text(json.dumps(out,indent=2)+"\n")
    print(json.dumps(out))
if __name__=="__main__":run()
