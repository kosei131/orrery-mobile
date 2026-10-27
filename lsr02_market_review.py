"""Research-only adapter: verified closed OHLC -> regime -> WAIT/DEFENSE.
A regime is not an entry signal; no synthetic candidates are created.
No MT5 login, trading, or execution connection.
"""
from lsr02_regime import classify
from lsr02_decision_journal import decide
from lsr02_structure import detect

def review_closed_bars(bars, *, as_of, interval, lookback, trend_efficiency,
                       range_efficiency, spread_ok, news_clear,
                       risk_budget_ok, loss_halt):
    """Fail closed on invalid/stale bars, insufficient evidence and guard failures."""
    try:
        detect(bars,as_of=as_of,interval=interval)
        assessment=classify(bars,as_of=as_of,interval=interval,
                            lookback=lookback,trend_efficiency=trend_efficiency,
                            range_efficiency=range_efficiency)
    except (ValueError,TypeError,KeyError,IndexError,OverflowError):
        return {"status":"DEFENSE","reason_codes":["INVALID_BAR_DATA"],
                "regime":None,"execution_allowed":False,
                "human_approval_required":True}
    regime=assessment["regime"]
    mapped=("TREND" if regime in ("UP","DOWN") else
            "RANGE" if regime=="RANGE_CANDIDATE" else "UNCLEAR")
    # Incomplete evidence is never upgraded to a trading setup.
    # The decision journal's no-candidate path documents WHY to wait.
    decision=decide(market_regime=mapped, data_fresh=assessment.get("reason")!="STALE_DATA",
        spread_ok=spread_ok,news_clear=news_clear,risk_budget_ok=risk_budget_ok,
        loss_halt=loss_halt,candidates=[],timestamp=as_of)
    if regime=="UNKNOWN" and decision["status"]=="WAIT":
        decision["reason_codes"]=["REGIME_NOT_CONFIRMED"]
    decision["regime"]=regime
    decision["regime_reason"]=assessment["reason"]
    decision["analysis_known_at"]=assessment["known_at"]
    return decision
