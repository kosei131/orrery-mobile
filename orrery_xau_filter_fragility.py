"""Counterfactual sample fragility: high VHF 3 wins and future loss scenarios.
Does not select thresholds or enable orders.
"""
import json
from pathlib import Path
def report():
    d=json.loads(Path("public_xau_vhf_ablation.json").read_text())
    three=d["vhf_gte_050"]
    scenarios=[]
    for losses in range(4):
        wins=3-losses
        # Simple fixed-risk arithmetic, illustrative; distinct from actual sample chronology.
        net_r=2*wins-losses
        scenarios.append({"losses_among_three":losses,"wins":wins,"total_r":net_r,
                          "approx_fixed_3000_usd_pnl":round(3000*.0025*net_r,2)})
    result={"status":"ILLUSTRATIVE_NOT_FORECAST","observed_high_vhf":three,
            "hypothetical_3_trade_stress":scenarios,
            "execution_permitted":False,
            "priority":"Independent unseen market period and true broker bid/ask before sizing."}
    Path("public_xau_filter_fragility.json").write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps(result))
if __name__=="__main__":report()
