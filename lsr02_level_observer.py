"""Annotate previously confirmed 2.6/pivot levels for review, never order signals.
All values are research hypotheses, not verified author's proprietary rules.
"""
from lsr02_context import analyze

def observe(bars, *, as_of, interval, tenkan, kijun, span_b, shift):
    ctx=analyze(bars,as_of=as_of,interval=interval,
                tenkan=tenkan,kijun=kijun,span_b=span_b,shift=shift)
    result=dict(status="WAIT",execution_allowed=False,
                human_approval_required=True,observed_at=ctx["at"],
                reasons=[],levels=[],cloud_location=ctx["cloud_location"])
    if ctx["cloud"] is None:
        result["reasons"].append("CLOUD_HISTORY_NOT_AVAILABLE")
    for name in ("nearest_support","nearest_resistance"):
        pivot=ctx[name]
        if pivot is not None:
            result["levels"].append(dict(kind=name.upper(),price=pivot["price"],
                                          confirmed_at=pivot["known_at"]))
    divisor=ctx["range_divisor_2_6"]
    if divisor is not None:
        for key in ("buy_pullback_level","sell_pullback_level"):
            result["levels"].append(dict(kind=key.upper(),price=divisor[key],
                                          confirmed_at=divisor["known_at"],
                                          author_match="UNVERIFIED"))
        if divisor["close_cross_up_buy"]:
            result["reasons"].append("2_6_LEVEL_CROSSED_UP_REVIEW_ONLY")
        if divisor["close_cross_down_sell"]:
            result["reasons"].append("2_6_LEVEL_CROSSED_DOWN_REVIEW_ONLY")
    for event in ctx["horizontal_breaks"]:
        result["reasons"].append("CONFIRMED_HORIZONTAL_BREAK_"+event["direction"])
    if ctx["cloud_break"] is not None:
        result["reasons"].append("CLOUD_EXIT_"+ctx["cloud_break"])
    if not result["reasons"]:
        result["reasons"].append("WAIT_FOR_VALIDATED_ENTRY_CONFIRMATION")
    return result
