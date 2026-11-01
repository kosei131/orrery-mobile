# LSR-02 experimental detection v0.1

No profitability claim, execution, sizing, or market feed. These functions are not yet connected to the UI or state machine. LSR-01 comparison baseline remains unavailable.

- Input each symbol/timeframe separately: UTC close timestamps, closed OHLC only, exact expected interval. Missing/unfinished bars fail closed. Split session gaps before calling; do not interpolate missing prices. The caller must verify timestamp meaning, provenance, freshness, symbol and timeframe.
- Strict swing pivot: higher high / lower low than `left` preceding and `right` following bars (default 2 each). Equal extremes are not pivots. Available only at the right-hand confirmation close, not at the pivot timestamp.
- Direction: two consecutive confirmed highs AND lows both rising => UP, both falling => DOWN, otherwise RANGE (including insufficient data).
- References: latest confirmed swing, available strictly before the event bar. One event per reference; a sweep consumes that reference. Repeated sweeps and subsequent breaks of that consumed level are deliberately excluded in this version.
- Sweep: wick strictly exceeds reference and closes strictly back inside. Close exactly on level is neither sweep nor break. `direction` describes the breached side (HIGH=UP), NOT a buy/sell recommendation.
- Close beyond a reference: BOS in existing direction; CHoCH against existing direction; BREAK if direction was RANGE. This is a provisional structural label, not an independent trade signal.
- POI hypothesis: last opposite candle between reference pivot and break, full wick range. Known only at break close. If none exists, POI is null and no automatic confirmation is permitted. Overlaps/retests, expiration, major supply/demand zones and multi-timeframe sequencing remain unimplemented.
- Every pivot/event has `known_at`. Historical outputs up to a time must equal outputs computed using only the prefix available at that time. Tests enforce this on synthetic fixtures; real data validation remains outstanding.

Next: join 4H context, 15m sweeps and subsequent 5m confirmation chronologically; enforce invalidation/expiry and only then evaluate retest/risk. No 2.6 hypothesis is used by detection.
