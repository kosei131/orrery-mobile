"""LSR-04 as-of join to LSR-03 candidates; research only.

Signal freshness is measured at the LSR candidate's FIRST structural close.
Only snapshots observed by that time are eligible. Repaint revisions are never
retroactively applied. Original indicator provenance remains UNVERIFIED.
"""
from lsr03_matched_outcomes import audit

def align(symbol,h4,m15,m5,events,*,as_of,buffer,age_bars=3,period=2):
    if type(age_bars) is not int or not 0<=age_bars<=12:
        raise ValueError("Invalid freshness window")
    if not isinstance(events,list):
        raise ValueError("Signal observations must be a list")
    base=audit(symbol,h4,m15,m5,as_of=as_of,buffer=buffer,period=period)
    used=[]
    for e in events:
        if not isinstance(e,dict) or e.get("symbol")!=symbol or e.get("timeframe")!="M5" or e.get("signal") not in ("BUY","SELL","NONE"):
            raise ValueError("Invalid external signal observation")
        t=e.get("closed_at");o=e.get("observed_at")
        if type(t) not in (int,float) or type(o) not in (int,float) or not 0<=t<=o<=as_of:
            raise ValueError("Unconfirmed, future or invalid signal observation")
        used.append(e)
    output=[]
    for candidate in base["rows"]:
        decision_at=candidate["structural_at"]
        # An observation after the structure decision never authorizes that earlier candidate.
        eligible=[e for e in used if e["observed_at"]<=decision_at and
                 e["closed_at"]<=decision_at and
                 decision_at-e["closed_at"]<=age_bars*300]
        # Most recently observed state per indicator source + candle; later revisions
        # can invalidate a signal but cannot alter what was known earlier.
        latest={}
        for e in sorted(eligible,key=lambda x:x["observed_at"]):
            key=(e.get("source"),e.get("revision_id"),e["closed_at"])
            latest[key]=e
        matching=[e for e in latest.values() if e["signal"]==candidate["side"]]
        opposite=[e for e in latest.values() if e["signal"] not in ("NONE",candidate["side"])]
        # Independent original code + non-repaint proof is required for production;
        # this is merely a research classification.
        status="ALIGNED_UNVERIFIED" if matching and not opposite else "WAIT_CONFLICT" if opposite else "WAIT_NO_MATCH"
        output.append(dict(id=candidate["id"],side=candidate["side"],
            structural_at=decision_at,vhf_group=candidate["group"],
            reversal_signal=status,hypothetical_outcome=candidate["status"],
            hypothetical_net_r=candidate.get("net_r"),
            execution_allowed=False))
    return dict(status="RESEARCH_AS_OF_JOIN",rows=output,
        execution_allowed=False,
        caveat="Not independently validated indicator signals, real fills, or trade-level backtest.")
