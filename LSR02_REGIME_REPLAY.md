# LSR-02 environment gate integration (experimental)

`replay(..., regime_config={lookback: N, trend_efficiency: T, range_efficiency: R})` enables the optional environment filter. Python keyword values must be supplied explicitly; there are no calibrated or recommended thresholds. Existing calls without this argument retain the historical structure-only comparator, including the existing synthetic viewer. The viewer does not yet show environment-filtered cases.

At every 5m close, classify only the 4H bars already closed at that instant. Candidate creation requires the class to match its side. Insufficient history, conflicting evidence, flat data or stale context blocks creation. A change away from the previously observed directional class invalidates an active candidate and records the class, reason and timestamp.

After environment invalidation, that replay is latched for review: no candidate is resumed or replaced later in the same run. This in-memory latch is not durable across a new process/replay call. A live service must implement durable acknowledgement before it could use this policy. No positions are closed, pending broker orders cancelled, or new orders sent; all cancellation here refers solely to internal research candidates.

Other existing invalidation paths (SL touch/expiry) retain their previous behavior. Neither mode generates READY. News, live spread, sizing and verified account limits remain unconnected. This module is an ORRERY research design, not a verified reproduction of any named trader's method.

Tests use synthetic OHLC with the actual structure detector and classifier, covering BUY/SELL candidate cancellation, stale context, insufficient history, invalid configuration and prefix invariance. These are correctness checks, not trading-performance evidence.
