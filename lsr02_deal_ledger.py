"""Offline MT5 deal-ledger aggregation for research (not a native file parser).

Input: normalized MT5 deals with explicit position_id, entry IN/OUT,
volume, profit, commission, swap, fee and UTC epoch seconds.
Hedging position_id is expected to identify one directional position.
Reject reversals, adjustments, incomplete positions and duplicate deals.
No AI attribution or MAE/MFE without market quotes; no broker auth/orders.
"""
from math import isfinite

def valid_number(v):
    return type(v) in (int,float) and isfinite(v)

def aggregate(deals):
    if not isinstance(deals,list) or not 1<=len(deals)<=100000:
        raise ValueError("Expected 1-100000 normalized MT5 deals")
    seen=set();groups={}
    for deal in deals:
        if not isinstance(deal,dict): raise ValueError("Invalid deal")
        ticket=deal.get("ticket")
        if type(ticket) is not int or ticket<=0 or ticket in seen:
            raise ValueError("Duplicate/invalid deal ticket")
        seen.add(ticket)
        position=deal.get("position_id")
        if type(position) is not int or position<=0:raise ValueError("Missing position_id")
        if deal.get("entry") not in ("IN","OUT") or deal.get("symbol") not in ("XAUUSD","USDJPY"):
            raise ValueError("Unsupported entry or symbol")
        for k in ("time_utc","volume","profit","commission","swap","fee"):
            if not valid_number(deal.get(k)):raise ValueError("Invalid numeric deal field")
        if deal["time_utc"]<0 or deal["volume"]<=0:raise ValueError("Bad deal time/volume")
        group=groups.setdefault(position,[])
        group.append(deal)
    completed=[];unclosed=[]
    for position,items in groups.items():
        items.sort(key=lambda d:(d["time_utc"],d["ticket"]))
        if items[0]["entry"]!="IN" or len({d["symbol"] for d in items})!=1:
            raise ValueError("Broken position chronology/symbol")
        volume=0.;opened=None;closed=None;adds=0;max_volume=0.
        for item in items:
            q=item["volume"]
            if item["entry"]=="IN":
                if volume<=1e-8:opened=item["time_utc"]
                else:adds+=1
                volume+=q
                max_volume=max(max_volume,volume)
            else:
                if q>volume+1e-8:raise ValueError("Exit exceeds current position")
                volume-=q
                closed=item["time_utc"]
                if volume<1e-8:volume=0.
                elif closed==opened:raise ValueError("Ambiguous simultaneous fill")
        pnl=sum(d["profit"]+d["commission"]+d["swap"]+d["fee"] for d in items)
        result=dict(position_id=position,symbol=items[0]["symbol"],opened_at=opened,
                    closed_at=closed if volume==0 else None,net_pnl_usd=pnl,
                    max_simultaneous_lots=max_volume,averaging_added=adds>0,
                    exit_deals=sum(d["entry"]=="OUT" for d in items),
                    deal_tickets=[d["ticket"] for d in items])
        (completed if volume==0 else unclosed).append(result)
    completed.sort(key=lambda x:(x["closed_at"],x["position_id"]))
    return dict(status="RESEARCH_ONLY",source="NORMALIZED_MT5_DEALS_UNVERIFIED",
                completed=completed,unclosed=unclosed,
                execution_allowed=False,
                limitations=["No Bid/Ask MAE/MFE, slippage or entry-price reconstruction.",
                             "Position IDs across reversal/netting require separate logic.",
                             "PnL assumed account currency USD; conversion unverified."])
