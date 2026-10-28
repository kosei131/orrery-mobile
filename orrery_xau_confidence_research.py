"""Exploratory PRE-TRADE VHF confidence stratification; no trading recommendation.
Compares existing observed research outcomes, with zero hindsight selection.
Higher VHF does not necessarily mean higher win probability.
"""
import json
from pathlib import Path

def evaluate(pnl_path,sequence_path):
    pnl=json.loads(Path(pnl_path).read_text())
    seq=json.loads(Path(sequence_path).read_text())
    evidence={e["first_poi_touch_close"]:e for e in seq["retouch_evidence"]}
    groups={"lower_vhf":[],"higher_vhf":[]}
    details=[]
    for t in pnl["trades_detail"]:
        evidence_row=evidence[t["touch_close_utc"]]
        vhf=evidence_row["vhf_at_sweep"]
        tier="higher_vhf" if vhf>=0.5 else "lower_vhf"
        groups[tier].append(t)
        details.append({"touch_close_utc":t["touch_close_utc"],"tier":tier,"vhf_at_sweep":vhf,"r":t["r"]})
    summaries={}
    for tier,ts in groups.items():
        wins=sum(x["r"]>0 for x in ts)
        summaries[tier]={"count":len(ts),"wins":wins,"win_rate_pct":round(100*wins/len(ts),2) if ts else None,
                         "mean_r":round(sum(x["r"] for x in ts)/len(ts),4) if ts else None,
                         "sum_r":round(sum(x["r"] for x in ts),4)}
    return {"status":"EXPLORATORY_NOT_TRADABLE","split_vhf":0.5,
            "known_before_trade":True,"total_trades":len(details),
            "groups":summaries,"details":details,
            "high_lot_enabled":False,"target_win_rate_pct":95,
            "limitations":["single sample; in-sample tier grouping","threshold 0.5 is exploratory, not validated",
                           "H4 trend, broker fills, commissions, and out-of-sample performance unverified"]}
if __name__=="__main__":
    r=evaluate(Path("public_xau_hypothetical_pnl.json"),Path("public_xau_sequence_report.json"))
    Path("public_xau_confidence_research.json").write_text(json.dumps(r,indent=2)+"\n")
    print(json.dumps({k:v for k,v in r.items() if k!="details"}))
