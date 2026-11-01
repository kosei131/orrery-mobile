# LSR-02 sequence prototype

This is an offline evidence coordinator, not the completed multi-timeframe strategy. It does not fetch bars, authenticate timestamps, derive evidence, size trades, or execute orders. READY is demo-review eligibility only.

The caller must supply evidence from closed bars of the same symbol and correct timeframe. 4H context must already exist at creation. Every subsequent event must have a strictly increasing close time. Events sharing a close time cannot be fed sequentially in this version; an adapter must define deterministic batching first. Audit history is in memory only and is not persistent trade evidence.

A caller-supplied fixed sweep extreme and positive stop buffer define the invalidation boundary. This boundary must already be observable at creation; the prototype does not derive or update the actual subsequent sweep extreme. Therefore it cannot yet implement production LSR-02 stops. Full closed-bar integration and provenance checks remain mandatory before backtesting or use.

WATCH accepts 15m sweep evidence; SWEEP accepts later 5m structural evidence plus a valid POI; CONFIRM accepts a later 5m overlap with POI; RETEST requires another 5m close outside POI in the trade direction and a positive risk gate. Any touched invalidation level, deadline, or missing data/context/news/spread clearance invalidates the candidate. No same-bar fill is modeled. READY must re-pass risk on subsequent calls. No supply/demand override for countertrend entries is implemented.

The separate detector and risk gate are not automatically wired to this coordinator yet. Exact 4H freshness, POI creation provenance, valid feed alignment, same-close batching, transaction costs, risk recalculation and rejection-candle definition need integration tests. No profitability, lot calculation, or market-validation claim is made.
