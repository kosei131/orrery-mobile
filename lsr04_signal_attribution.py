"""Descriptive research attribution for LSR-04 matched candidate outcomes.

No claim that a missing external signal would have lost. Same candidate
hypothetical outcome is used in included/excluded groups; OPEN/INVALID excluded
from realized comparisons and reported separately. No account-level PnL.
"""
from lsr04_asof_join import align

def compare(symbol,h4,m15,m5,events,*,as_of,buffer,age_bars=3,period=2):
    joined=align(symbol,h4,m15,m5,events,as_of=as_of,buffer=buffer,
                 age_bars=age_bars,period=period)
    groups={}
    for name,keep in (("SIGNAL_MATCHED",True),("SIGNAL_NOT_MATCHED",False)):
        members=[r for r in joined["rows"] if (r["reversal_signal"]=="ALIGNED_UNVERIFIED")==keep]
        closed=[r for r in members if r["hypothetical_outcome"]=="CLOSED"]
        wins=[r for r in closed if r["hypothetical_net_r"]>0]
        losses=[r for r in closed if r["hypothetical_net_r"]<0]
        net=sum(r["hypothetical_net_r"] for r in closed)
        groups[name]=dict(candidate_count=len(members),closed_count=len(closed),
            unresolved_count=len(members)-len(closed),hypothetical_wins=len(wins),
            hypothetical_losses=len(losses),hypothetical_total_net_r=round(net,6),
            hypothetical_mean_net_r=round(net/len(closed),6) if closed else None)
    return dict(status="RESEARCH_ATTRIBUTION_ONLY",groups=groups,
        total_candidates=len(joined["rows"]),execution_allowed=False,
        caveats=["A missing/late/revised signal is not evidence of a losing trade.",
          "External indicator formula and nonrepainting behavior are unverified.",
          "Hypothetical candidate R totals are not realizable portfolio performance.",
          "Overlapping positions, broker spread, gap fills and open-trade mark-to-market not modeled."])

