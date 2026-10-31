"""Research-only fixed-confidence risk-sizing comparison.
No broker fills or order permission; uses fixed observed R and chronological evidence.
"""
import json
from pathlib import Path

def analyze(pnl_file,confidence_file,starting=3000.0,base_risk=.0025,high_risk=.005):
    pnl=json.loads(Path(pnl_file).read_text())
    conf=json.loads(Path(confidence_file).read_text())
    tiers={x["touch_close_utc"]:x["tier"] for x in conf["details"]}
    source=sorted(pnl["trades_detail"],key=lambda x:x["touch_close_utc"])
    results={}
    for mode in ("uniform_025pct","high_vhf_050pct"):
        equity=starting;peak=starting;dd=0.0;rows=[]
        for t in source:
            risk=high_risk if mode=="high_vhf_050pct" and tiers[t["touch_close_utc"]]=="higher_vhf" else base_risk
            gain=equity*risk*t["r"]
            equity+=gain;peak=max(peak,equity);dd=max(dd,(peak-equity)/peak)
            rows.append({"utc":t["touch_close_utc"],"tier":tiers[t["touch_close_utc"]],"risk_pct":risk*100,"pnl_usd":round(gain,4)})
        results[mode]={"ending_usd":round(equity,2),"net_usd":round(equity-starting,2),
                       "max_closed_trade_dd_pct":round(100*dd,3),"trades":len(rows)}
    return {"status":"RESEARCH_ONLY_NO_HIGH_LOT_PERMISSION","starting_usd":starting,
            "threshold_fixed_after_inspection":0.5,
            "models":results,"trade_count":len(source),
            "not_out_of_sample":True,
            "warning":"This tests an in-sample confidence split on only 3 high-tier wins; high risk is hypothetical and is not recommended until independent validation."}
if __name__=="__main__":
    result=analyze(Path("public_xau_hypothetical_pnl.json"),Path("public_xau_confidence_research.json"))
    Path("public_xau_sizing_whatif.json").write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps(result))
