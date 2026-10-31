"""Count LSR-02 vs research VHF states; no profitability or execution claims."""
from lsr03_adapter import compare_vhf
from test_lsr02_paths import fixture

def report(symbol,h4,m15,m5,*,as_of,buffer,period=2,min_vhf=.4):
    result=compare_vhf(symbol,h4,m15,m5,as_of=as_of,buffer=buffer,
                       period=period,min_vhf=min_vhf)
    base=result["base_trace"];vhf=result["vhf_trace"]
    if len(base)!=len(vhf):raise AssertionError("Unmatched states")
    reviewable=sum(x["state"] in ("CONFIRM","RETEST") for x in base)
    kept=sum(x["decision"]=="REVIEW" for x in vhf)
    rejected=reviewable-kept
    return dict(status="SYNTHETIC_CANDIDATE_COUNTS_NOT_BACKTEST",
        base_rows=len(base),base_reviewable=reviewable,
        vhf_reviewable=kept,vhf_filtered_rows=rejected,
        wait=sum(x["decision"]=="WAIT" for x in vhf),
        cancel=sum(x["decision"]=="CANCEL" for x in vhf),
        execution_allowed=False,
        warning="Rows are repeated state snapshots, not independent trades. No PnL available.")

if __name__=="__main__":
    for sell in (False,True):
        h,f,m=fixture(sell)
        print(("SELL" if sell else "BUY"),report("XAUUSD",h,f,m,
              as_of=m[-1]["close_time"],buffer=.1))
