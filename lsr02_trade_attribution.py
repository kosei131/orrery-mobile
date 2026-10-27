"""Research-only trade attribution: rank winners/losers and label observed risks.

Tags express supplied facts, not causal proof. 6-month performance needs real
broker ticks, fills and precommitted strategy rules. No execution features.
"""
from math import isfinite

def num(x):
    return type(x) in (int,float) and isfinite(x)

def report(trades, *, top_n=20):
    if not isinstance(trades,list) or not 0<len(trades)<=100000 or type(top_n) is not int or not 1<=top_n<=100:
        raise ValueError("Invalid history or top_n")
    seen=set();out=[]
    for t in trades:
        if not isinstance(t,dict) or not isinstance(t.get("id"),str) or not t["id"] or t["id"] in seen:
            raise ValueError("Invalid or duplicate trade")
        seen.add(t["id"])
        fields=("opened_at","closed_at","gross_pnl_usd","cost_usd",
                "max_adverse_usd","max_favorable_usd","max_simultaneous_lots")
        if not all(num(t.get(k)) for k in fields):raise ValueError("Incomplete trade record")
        if t["opened_at"]>=t["closed_at"] or t["cost_usd"]<0 or t["max_adverse_usd"]<0 or t["max_favorable_usd"]<0 or t["max_simultaneous_lots"]<=0:
            raise ValueError("Invalid time/risk fields")
        if t.get("strategy") not in ("SCALP","RANGE","STRUCTURE") or t.get("symbol") not in ("XAUUSD","USDJPY"):
            raise ValueError("Invalid strategy/symbol")
        for key in ("averaging_added","support_confirmed","two_six_near","spread_widened","news_window","regime_changed"):
            if type(t.get(key)) is not bool:raise ValueError("Missing flag "+key)
        net=t["gross_pnl_usd"]-t["cost_usd"];tags=[]
        if t["averaging_added"]: tags.append("AVERAGING_ADDED")
        if t["spread_widened"]:tags.append("SPREAD_WIDENED")
        if t["news_window"]:tags.append("NEWS_WINDOW")
        if t["regime_changed"]:tags.append("REGIME_CHANGED")
        if t["support_confirmed"]:tags.append("SUPPORT_CONFIRMED")
        if t["two_six_near"]:tags.append("TWO_SIX_NEAR")
        out.append(dict(id=t["id"],symbol=t["symbol"],strategy=t["strategy"],
            opened_at=t["opened_at"],closed_at=t["closed_at"],
            duration_seconds=t["closed_at"]-t["opened_at"],net_pnl_usd=net,
            gross_pnl_usd=t["gross_pnl_usd"],cost_usd=t["cost_usd"],
            mae_usd=t["max_adverse_usd"],mfe_usd=t["max_favorable_usd"],
            max_simultaneous_lots=t["max_simultaneous_lots"],tags=tags,
            cause_status="CORRELATION_ONLY_NOT_PROVEN"))
    wins=sorted((x for x in out if x["net_pnl_usd"]>0),key=lambda x:(-x["net_pnl_usd"],x["id"]))[:top_n]
    losses=sorted((x for x in out if x["net_pnl_usd"]<0),key=lambda x:(x["net_pnl_usd"],x["id"]))[:top_n]
    total=sum(x["net_pnl_usd"] for x in out)
    grouped={}
    for x in out:
        key=x["strategy"];v=grouped.setdefault(key,dict(trades=0,net_usd=0,wins=0,losses=0))
        v["trades"]+=1;v["net_usd"]+=x["net_pnl_usd"]
        v["wins"]+=x["net_pnl_usd"]>0;v["losses"]+=x["net_pnl_usd"]<0
    return dict(status="RESEARCH_ONLY",execution_allowed=False,
        total_net_usd=total,count=len(out),top_winners=wins,top_losers=losses,
        by_strategy=grouped,attribution_method="OBSERVED_TAGS_NOT_CAUSAL_INFERENCE")
