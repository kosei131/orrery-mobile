"""In-sample ablation: remove low-VHF entries without altering price outcomes.
This is NOT an independent backtest or an authorization for execution.
"""
import json
from pathlib import Path
def evaluate():
    p=json.loads(Path("public_xau_hypothetical_pnl.json").read_text())
    c=json.loads(Path("public_xau_confidence_research.json").read_text())
    tiers={r["touch_close_utc"]:r["tier"] for r in c["details"]}
    trades=sorted(p["trades_detail"],key=lambda t:t["touch_close_utc"])
    def replay(selected):
        eq=3000.;peak=eq;dd=0.
        for t in selected:
            eq*=1+0.0025*t["r"]
            peak=max(peak,eq);dd=max(dd,(peak-eq)/peak)
        n=len(selected);wins=sum(t["r"]>0 for t in selected)
        return {"trades":n,"wins":wins,"win_rate_pct":round(100*wins/n,2) if n else None,
                "net_usd":round(eq-3000,2),"max_closed_trade_dd_pct":round(100*dd,3),
                "mean_r":round(sum(t["r"] for t in selected)/n,4) if n else None}
    high=[t for t in trades if tiers[t["touch_close_utc"]]=="higher_vhf"]
    low=[t for t in trades if tiers[t["touch_close_utc"]]=="lower_vhf"]
    result={"status":"IN_SAMPLE_FILTER_ABLATION_ONLY","all":replay(trades),"vhf_gte_050":replay(high),
            "vhf_040_to_050":replay(low),"filtered_out_count":len(low),
            "high_lot_enabled":False,
            "limitations":["Threshold chosen after examining all outcomes; selection bias.",
            "3 surviving observations are insufficient to estimate future win rate.",
            "Spread is assumed, broker fills and H4 unverified."]}
    Path("public_xau_vhf_ablation.json").write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps(result))
if __name__=="__main__":evaluate()
