"""Compare simple predetermined 1.5R/2R blend versus fixed target research.
No adaptive target selection using future returns or fitted regimes.
"""
import datetime as dt,json
from pathlib import Path
from orrery_xau_hypothetical_pnl import simulate
START=int(dt.datetime(2026,4,25,tzinfo=dt.timezone.utc).timestamp())
END=int(dt.datetime(2026,9,25,tzinfo=dt.timezone.utc).timestamp())
def run():
    root=Path("public_xau_bars")
    cases={}
    for target in (1.5,2.0):
        x=simulate(root/"XAUUSD_M1_UNVERIFIED_QUOTE.csv",Path("public_xau_sequence_report.json"),reward_r=target)
        cases[target]={t["touch_close_utc"]:t for t in x["trades_detail"] if START<=t["touch_close_utc"]<END}
    common=sorted(set(cases[1.5]) & set(cases[2.0]))
    # Equal allocation to both exits: half risk each, same total 0.25% risk.
    eq=3000.;peak=eq;dd=0.;wins=0
    for when in common:
        r=(cases[1.5][when]["r"]+cases[2.0][when]["r"])/2
        wins+=r>0;eq*=1+.0025*r
        peak=max(peak,eq);dd=max(dd,(peak-eq)/peak)
    out={"status":"RESEARCH_FIXED_SPLIT_NOT_OPTIMIZED",
         "target_policy":"Split total position equally: 50% at 1.5R and 50% at 2.0R; common entries only",
         "trades":len(common),"positive_trades":wins,
         "net_usd":round(eq-3000,2),"max_closed_trade_dd_pct":round(dd*100,3),
         "compared_same_data":True,"broker_fills_verified":False,"high_lot_enabled":False,
         "warning":"Two hypothetical exit outcomes combined without a broker-level multi-leg execution model; cannot infer realized fills."}
    Path("public_xau_fixed_split_tp.json").write_text(json.dumps(out,indent=2)+"\n")
    print(json.dumps(out))
if __name__=="__main__":run()
