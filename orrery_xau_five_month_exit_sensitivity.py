"""Five-month XAU exit sensitivity, research only, explicitly in-sample.
Compares reward-to-risk targets on the SAME fixed VHF candidate times.
This does not establish an optimal TP or broker-fills performance.
"""
import json,datetime as dt
from pathlib import Path
from orrery_xau_hypothetical_pnl import simulate

START=int(dt.datetime(2026,4,25,tzinfo=dt.timezone.utc).timestamp())
END=int(dt.datetime(2026,9,25,tzinfo=dt.timezone.utc).timestamp())

def run():
    root=Path("public_xau_bars")
    output=[]
    for rr in (1.0,1.5,2.0,2.5,3.0):
        result=simulate(root/"XAUUSD_M1_UNVERIFIED_QUOTE.csv",
                        Path("public_xau_sequence_report.json"),
                        spread_usd=.6,stop_usd=6.0,reward_r=rr)
        trades=[t for t in result["trades_detail"] if START<=t["touch_close_utc"]<END]
        equity=3000.;peak=equity;dd=0.;wins=0
        for t in trades:
            wins+=t["r"]>0
            equity*=1+.0025*t["r"]
            peak=max(peak,equity);dd=max(dd,(peak-equity)/peak)
        output.append({"target_r":rr,"trades":len(trades),"wins":wins,
                       "win_rate_pct":round(100*wins/len(trades),2) if trades else None,
                       "net_usd":round(equity-3000,2),
                       "max_closed_trade_dd_pct":round(dd*100,3),
                       "mean_r":round(sum(t["r"] for t in trades)/len(trades),4) if trades else None})
    r={"status":"IN_SAMPLE_EXIT_SENSITIVITY_NOT_OPTIMIZED","window_utc":"2026-04-25 to 2026-09-25 exclusive",
       "same_entry_rule":True,"fixed_stop_usd":6,"spread_assumption_usd":.6,
       "variants":output,"automatic_target_selection":False,"high_lot_enabled":False,
       "warning":"All five targets evaluated on the same 9-event research sample, hence no out-of-sample inference."}
    Path("public_xau_five_month_exit_sensitivity.json").write_text(json.dumps(r,indent=2)+"\n")
    print(json.dumps(r))
if __name__=="__main__":run()
