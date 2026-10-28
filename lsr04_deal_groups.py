"""Research-only MT5 DEMO deal grouping. No trading.

Group all deals by position_id. A position is counted as closed only when
opening and closing volumes balance; mixed INOUT reversals, corrections,
missing provenance, and open positions block streak certification.
"""
from math import isfinite

def _num(x):
    if type(x) not in (int,float) or not isfinite(x):raise ValueError("Finite field required")
    return float(x)

def reconcile(deals,*,entry_in,entry_out,entry_inout,open_position_ids=()):
    if not isinstance(deals,list) or len(deals)>100000:
        raise ValueError("Bounded deal history required")
    if not isinstance(open_position_ids,(list,tuple,set)):
        raise ValueError("Open position IDs required")
    groups={}
    for d in deals:
        pid=getattr(d,"position_id",None)
        if type(pid) is not int or pid<=0:
            raise ValueError("Missing position identity")
        kind=getattr(d,"entry",None)
        if kind not in (entry_in,entry_out,entry_inout):
            raise ValueError("Unknown deal entry category")
        amount=_num(getattr(d,"volume",None))
        if amount<=0:raise ValueError("Positive deal volume required")
        key=(getattr(d,"time_msc",None),getattr(d,"ticket",None))
        if any(type(x) is not int or x<0 for x in key):
            raise ValueError("Deal ordering provenance required")
        amounts=(_num(getattr(d,f,None)) for f in ("profit","commission","swap","fee"))
        pnl=sum(amounts)
        g=groups.setdefault(pid,dict(position_id=pid,opened=0.,closed=0.,
                                     net=0.,last_close=None,deal_count=0,has_reversal=False))
        if kind==entry_in:g["opened"]+=amount
        elif kind==entry_out:
            g["closed"]+=amount
            g["last_close"]=max(g["last_close"] or key,key)
        else:g["has_reversal"]=True
        g["net"]+=pnl;g["deal_count"]+=1
    completed=[];unresolved=[]
    for pid,g in groups.items():
        if g["has_reversal"] or pid in open_position_ids or g["opened"]<=0 or abs(g["opened"]-g["closed"])>1e-7:
            unresolved.append(pid);continue
        completed.append(g)
    completed.sort(key=lambda g:g["last_close"])
    losses=0
    for g in reversed(completed):
        if g["net"]<0:losses+=1
        else:break
    return dict(status="COMPLETE_HISTORY_REQUIRED" if unresolved else "GROUPED_HISTORY_RESEARCH",
                completed_positions=len(completed),unresolved_position_ids=sorted(unresolved),
                consecutive_losses=losses if not unresolved else None,
                positions=[dict(x) for x in completed],execution_allowed=False,
                caveat="Must include full open-to-close history, broker fee attribution and earlier positions for authoritative streak.")
