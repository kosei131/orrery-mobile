"""Research-only concurrency audit of hypothetical XAU trades.

Pnl simulator currently processes candidates sequentially; this audit detects
entry windows that *could* overlap using conservative full holding horizon.
It does not convert those records into independently executed trades.
"""
import json
from pathlib import Path

def audit(path, horizon_minutes=120, risk_per_position=0.0025, max_total_risk=0.01):
    report=json.loads(Path(path).read_text(encoding="utf-8"))
    trades=sorted(report["trades_detail"],key=lambda t:t["touch_close_utc"])
    overlapping_pairs=[]
    max_open=0
    for i,t in enumerate(trades):
        concurrent=sum(1 for prior in trades[:i]
                       if t["touch_close_utc"]-prior["touch_close_utc"] < horizon_minutes*60)
        max_open=max(max_open,concurrent+1)
        for previous in trades[:i]:
            if t["touch_close_utc"]-previous["touch_close_utc"] < horizon_minutes*60:
                overlapping_pairs.append((previous["touch_close_utc"],t["touch_close_utc"]))
    return {"candidate_count":len(trades),"potential_overlap_pairs":len(overlapping_pairs),
            "max_possible_concurrent_positions":max_open,
            "max_nominal_risk_pct":round(100*max_open*risk_per_position,3),
            "portfolio_risk_cap_pct":round(100*max_total_risk,3),
            "risk_cap_exceeded_by_full_horizon_assumption":max_open*risk_per_position>max_total_risk,
            "pnl_accounts_for_overlap":False,
            "warning":"This is an upper-bound time-window audit. Actual exit timestamps not in PnL trades; no account-level fill/replay validated."}

if __name__=="__main__":
    result=audit(Path("public_xau_hypothetical_pnl.json"))
    Path("public_xau_overlap_audit.json").write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(result))
