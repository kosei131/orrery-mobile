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


def collect_retests(compared, symbol, *, max_candidates=1000):
    """One first RETEST per existing sweep; preserve later invalidation clock.

    Invalidation is a separate event, never an earlier entry-time feature.
    """
    base=compared['base_trace'];vhf=compared['vhf_trace']
    if len(base)!=len(vhf) or type(max_candidates) is not int or max_candidates<1:
        raise ValueError('Aligned bounded structural/VHF traces required')
    candidates=[];active=None
    for original,flt in zip(base,vhf):
        if original['at']!=flt['at'] or original['state']!=flt['lsr_state'] or original['side']!=flt['side']:
            raise ValueError('Mismatched structural/VHF evidence')
        if original['state']=='SWEEP' and (active is None or active['invalid_at'] is not None):
            active=dict(id=f"{symbol}:{original['at']}:{original['side']}",side=original['side'],
                        sweep_at=original['at'],stop=original['stop'],retest_at=None,
                        invalid_at=None,group=None)
        if active is None:raise ValueError('Missing candidate lifecycle')
        if original['state']=='INVALID':active['invalid_at']=original['at']
        if original['state']=='RETEST' and active['retest_at'] is None:
            if len(candidates)>=max_candidates:raise ValueError('Candidate budget exceeded')
            active['retest_at']=original['at']
            active['group']='VHF_PASS' if flt['decision']=='REVIEW' else 'VHF_FILTERED'
            candidates.append(active)
    return candidates
