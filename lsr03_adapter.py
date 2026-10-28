"""LSR-VHF 03: annotate original LSR-02 candidate trace without changing it.

VHF is a trend-strength hypothesis, not the unknown red/green custom signal.
All VHF observations are computed from 15m closes available AT each trace row.
This adapter produces no READY, lot sizing, or orders.
"""
from lsr02_replay import replay
from lsr03_vhf import calculate

def compare_vhf(symbol,h4,m15,m5,*,as_of,buffer,period=14,
                min_vhf=.4,left=1,right=1,lifetime=6000):
    if type(min_vhf) not in (int,float) or not 0<=min_vhf<=1:
        raise ValueError("Invalid research cutoff")
    base=replay(symbol,h4,m15,m5,as_of=as_of,buffer=buffer,
                left=left,right=right,lifetime=lifetime)
    annotated=[]
    for row in base:
        t=row["at"]
        # Cut data off at row's confirmed clock. No later 15m candles.
        bars=[b for b in m15 if b["close_time"]<=t]
        if not bars:
            value=dict(status="INSUFFICIENT_HISTORY",value=None,slope="UNKNOWN")
        else:
            value=calculate(bars,period=period,as_of=t,interval=900)
        passed=(value["status"]=="OK" and value["value"]>=min_vhf
                and value["slope"]=="RISING")
        # Preserve LSR-02 semantics: no filter can promote an INVALID row.
        if row["state"]=="INVALID":
            decision="CANCEL"
        elif row["state"] not in ("CONFIRM","RETEST"):
            decision="WAIT"
        elif passed:
            decision="REVIEW"
        else:
            decision="WAIT"
        annotated.append(dict(at=t,lsr_state=row["state"],side=row["side"],
            vhf_status=value["status"],vhf_value=value["value"],
            vhf_slope=value["slope"],vhf_pass=passed,
            decision=decision,readiness="BLOCKED_UNVERIFIED_GUARDS",
            execution_allowed=False))
    return dict(status="LSR03_VHF_RESEARCH",base_trace=base,
                vhf_trace=annotated,execution_allowed=False,
                author_color_definition="UNVERIFIED",
                comparisons_require_real_broker_data=True)
