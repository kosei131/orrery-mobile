"""LSR-VHF 03 matched hypothetical outcomes; NOT real fills or a broker backtest.

Each candidate uses the FIRST confirmed LSR structure timestamp, next 5m open,
the original LSR structural stop and an explicit fixed R target. VHF must have
confirmed AT OR BEFORE that first structural timestamp; later information is
not allowed to retroactively approve the entry. Same hypothetical outcome is
assigned to passed and filtered groups, removing selection-time PnL distortion.
"""
from math import isfinite
from lsr03_adapter import compare_vhf

def audit(symbol,h4,m15,m5,*,as_of,buffer,period=2,min_vhf=.4,
          target_r=2.,cost_r=.08):
    if any(type(x) not in (float,int) or not isfinite(x) for x in (target_r,cost_r)) or not 0<target_r<=10 or not 0<=cost_r<1:
        raise ValueError("Invalid hypothetical R/cost")
    res=compare_vhf(symbol,h4,m15,m5,as_of=as_of,buffer=buffer,
                    period=period,min_vhf=min_vhf)
    base=res["base_trace"];vhf=res["vhf_trace"]
    bars={b["close_time"]:i for i,b in enumerate(m5)}
    rows=[];active=None
    for original,flt in zip(base,vhf):
        if original["state"]=="SWEEP":
            active=dict(id=f"{symbol}:{original['side']}:{original['at']}",
                        side=original["side"],stop=original["stop"],first_structure=None,
                        vhf_pass_at_entry=False)
        if active is None:
            raise ValueError("Missing candidate lifecycle start")
        if original["state"] in ("CONFIRM","RETEST") and active["first_structure"] is None:
            active["first_structure"]=original["at"]
            active["vhf_pass_at_entry"]=flt["decision"]=="REVIEW"
            # Candidate cannot enter on its signal close; next candle is first fill opportunity.
            index=bars.get(original["at"])
            if index is None or index+1>=len(m5):
                outcome=dict(status="NO_NEXT_BAR")
            else:
                entry_index=index+1;entry=m5[entry_index]["open"]
                distance=(entry-active["stop"]) if active["side"]=="BUY" else (active["stop"]-entry)
                if distance<=0:
                    outcome=dict(status="INVALID_STOP")
                else:
                    target=entry+distance*target_r if active["side"]=="BUY" else entry-distance*target_r
                    outcome=dict(status="OPEN",entry=entry,stop=active["stop"],target=target,
                                 entry_at=m5[entry_index]["close_time"])
                    for b in m5[entry_index:]:
                        stop_hit=b["low"]<=active["stop"] if active["side"]=="BUY" else b["high"]>=active["stop"]
                        tp_hit=b["high"]>=target if active["side"]=="BUY" else b["low"]<=target
                        if stop_hit or tp_hit:
                            gross=-1. if stop_hit else target_r
                            outcome.update(status="CLOSED",exit_at=b["close_time"],gross_r=gross,net_r=gross-cost_r,
                                           exit_reason="STOP" if stop_hit else "TARGET")
                            break
            rows.append(dict(id=active["id"],side=active["side"],structural_at=original["at"],
                             group="VHF_PASS" if active["vhf_pass_at_entry"] else "VHF_FILTERED",
                             **outcome))
        if original["state"]=="INVALID":active=None
    groups={}
    for group in ("VHF_PASS","VHF_FILTERED"):
        items=[r for r in rows if r["group"]==group]
        closed=[x for x in items if x["status"]=="CLOSED"]
        groups[group]=dict(candidates=len(items),closed=len(closed),
                           unresolved=len(items)-len(closed),
                           total_net_r=round(sum(x["net_r"] for x in closed),6),
                           mean_net_r=round(sum(x["net_r"] for x in closed)/len(closed),6) if closed else None)
    return dict(status="HYPOTHETICAL_MATCHED_CANDIDATE_RESEARCH",
                rows=rows,groups=groups,execution_allowed=False,
                limitations="No broker bid/ask, commissions in USD, slippage or actual fills; open trades excluded from realized averages; candidate PnL overlaps and cannot be summed as portfolio returns.")

