"""LSR-04 observational-data quality audit; not a signal accuracy audit.

Expected closed bars must be explicitly supplied; observation coverage is not
measurable from events alone. Late/revised/missing observations are distinct.
"""
from math import isfinite

def audit_quality(*,symbol,expected_closes,events,source,revision_id,
                  max_delay_seconds=300):
    if symbol not in ("XAUUSD","USDJPY") or not isinstance(source,str) or not source or not isinstance(revision_id,str) or not revision_id:
        raise ValueError("Explicit source provenance required")
    if type(max_delay_seconds) not in (float,int) or not isfinite(max_delay_seconds) or max_delay_seconds<0:
        raise ValueError("Invalid delay bound")
    if not isinstance(expected_closes,list) or not isinstance(events,list):
        raise ValueError("Expected clock and events required")
    if not expected_closes or any(type(t) not in (int,float) or not isfinite(t) for t in expected_closes):
        raise ValueError("Nonempty finite expected closed times required")
    if sorted(set(expected_closes))!=expected_closes:
        raise ValueError("Expected bar times must be unique and increasing")
    expected=set(expected_closes);by_close={t:[] for t in expected}
    for e in events:
        if not isinstance(e,dict) or e.get("symbol")!=symbol or e.get("timeframe")!="M5" or e.get("source")!=source or e.get("revision_id")!=revision_id:
            raise ValueError("Mixed source/version observations")
        t=e.get("closed_at");at=e.get("observed_at")
        if type(t) not in (int,float) or type(at) not in (int,float) or not isfinite(t) or not isfinite(at) or t not in expected or at<t:
            raise ValueError("Invalid or unconfirmed observation time")
        if e.get("signal") not in ("BUY","SELL","NONE"):
            raise ValueError("Invalid signal")
        by_close[t].append(e)
    observed=sum(bool(v) for v in by_close.values())
    delayed=sum(bool(v) and min(x["observed_at"]-t for x in v)>max_delay_seconds
                for t,v in by_close.items())
    revised=sum(bool(v) and len({x["signal"] for x in v})>1 for v in by_close.values())
    missing=len(expected)-observed
    return dict(status="OBSERVATION_QUALITY_ONLY",expected_bars=len(expected),
                observed_bars=observed,missing_bars=missing,
                coverage=observed/len(expected),late_first_observations=delayed,
                bars_with_revisions=revised,execution_allowed=False,
                verdict="INSUFFICIENT_OR_UNVERIFIED" if missing or delayed or revised else "OBSERVATIONS_COMPLETE_NOT_PROOF",
                caveat="Complete observations do not prove indicator validity, non-repainting, or profitability.")
