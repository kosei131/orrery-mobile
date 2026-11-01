"""LSR-VHF candidate lifecycle counts, without PnL or trading permissions.

A candidate starts only on SWEEP. A later SWEEP always starts a new id.
Derived IDs are session-local and do not identify real MT5 tickets.
"""
from lsr03_adapter import compare_vhf

def unique_report(symbol,h4,m15,m5,*,as_of,buffer,period=2,min_vhf=.4):
    result=compare_vhf(symbol,h4,m15,m5,as_of=as_of,buffer=buffer,
                       period=period,min_vhf=min_vhf)
    rows=result["vhf_trace"]
    candidates=[]
    current=None
    for row in rows:
        if row["lsr_state"]=="SWEEP":
            current=dict(id=f"{symbol}:{row['side']}:{row['at']}",
                         side=row["side"],created_at=row["at"],
                         reached_structure=False,vhf_confirmed=False,
                         canceled=False,observations=0)
            candidates.append(current)
        if current is None:
            raise ValueError("Trace without initial SWEEP")
        if row["side"]!=current["side"]:
            raise ValueError("Unexpected side change without SWEEP")
        current["observations"]+=1
        if row["lsr_state"] in ("CONFIRM","RETEST"):
            current["reached_structure"]=True
            current["vhf_confirmed"]|=row["decision"]=="REVIEW"
        if row["decision"]=="CANCEL":
            current["canceled"]=True
            current=None
    eligible=[c for c in candidates if c["reached_structure"]]
    kept=[c for c in eligible if c["vhf_confirmed"]]
    return dict(status="SYNTHETIC_UNIQUE_CANDIDATE_COUNT",
                total_candidates=len(candidates),
                structurally_confirmed=len(eligible),
                vhf_confirmed=len(kept),
                filtered=len(eligible)-len(kept),
                candidates=candidates,execution_allowed=False,
                warning="Research candidate counts only; no fills, PnL or causal edge.")

