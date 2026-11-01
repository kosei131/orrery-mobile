"""LSR-04 append-only signal observation ledger, no orders.

Conflicting later observations are flagged, not used to rewrite historical
signals. This detects revisions only when snapshots are actually supplied;
it cannot certify that an unknown proprietary indicator never repaints.
"""
from math import isfinite

class SignalJournal:
    def __init__(self):
        self._latest={}
        self._events=[]
    def observe(self, *, symbol, timeframe, closed_at, observed_at,
                signal, source, revision_id):
        if symbol not in ("XAUUSD","USDJPY") or timeframe not in ("M5","M15"):
            raise ValueError("Unsupported research scope")
        if signal not in ("BUY","SELL","NONE") or not isinstance(source,str) or not source.strip():
            raise ValueError("Unknown indicator observation")
        if type(revision_id) is not str or not revision_id:
            raise ValueError("Indicator version required")
        for t in (closed_at,observed_at):
            if type(t) not in (float,int) or not isfinite(t):
                raise ValueError("Invalid time")
        if observed_at<closed_at:
            raise ValueError("Cannot observe an unfinished candle as closed")
        key=(symbol,timeframe,closed_at,source,revision_id)
        old=self._latest.get(key)
        if old is not None and observed_at<old["observed_at"]:
            raise ValueError("Nonmonotonic observation")
        revised=old is not None and old["signal"]!=signal
        event=dict(symbol=symbol,timeframe=timeframe,closed_at=closed_at,
                   observed_at=observed_at,signal=signal,source=source,
                   revision_id=revision_id,changed_after_observation=revised,
                   previous_signal=old["signal"] if revised else None)
        self._events.append(dict(event))
        self._latest[key]=dict(event)
        return dict(event,execution_allowed=False)
    def report(self):
        return dict(status="OBSERVATIONS_ONLY",
                    observations=len(self._events),
                    repaint_suspicions=sum(x["changed_after_observation"] for x in self._events),
                    events=[dict(x) for x in self._events],execution_allowed=False,
                    caveat="Only observed revisions detectable; same-source snapshots are required.")
