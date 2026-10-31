# Normalized MT5 Bid/Ask history quality audit

`lsr04_tick_quality.audit_ticks` audits a tick iterable in original order;
`audit_capture` accepts the existing capture_days and capture_adaptive output
formats. It does not refetch data, sort/filter away defects, change candidate
rules or authorize backtests/orders. No six-month dataset is bundled.

Required evidence/parameters:

- canonical symbol (XAUUSD or USDJPY), UTC start/end and explicit source label;
- caller-supplied broker specification: symbol, point, trade_contract_size,
  digits (positive point/contract and integer digits);
- explicit max_spread_points and configurable quote-gap research threshold;
- optional capture window manifest and explicit OPEN/CLOSED session intervals
  with session_source. No weekend, holiday or broker timezone is inferred.

Time ranges are half-open [start,end) with exact millisecond-aligned UTC bounds.
An inclusive final endpoint returned by MT5 must already have been excluded
by the existing capture adapters. Submillisecond boundaries from recursive
splits are rejected rather than rounded; supporting those requires an explicit
capture/time-normalization policy. Broker suffix capture remains constrained
by the existing canonical-symbol intake and is not solved by this audit.

The audit reports invalid/nonfinite/crossed quotes, out-of-range rows, time
reversals, same-millisecond distinct quotes, normalized duplicate candidates,
spreads in broker point units, and silence at both horizon edges and internally.
Spread bins are [0,edge0), [edge0,edge1), ..., [last_edge,infinity). An exact
spread threshold is allowed; only strictly greater spreads are flagged.
Decimal quote subtraction avoids threshold cancellation for decimal prices.
Min/max/online mean and histogram are streaming summaries, not percentiles.

Repeated identical normalized (time_msc,bid,ask) records are retained. Raw
flags/volume changes discarded by the existing intake can make different raw
events look identical, so these are duplicate candidates, not proved duplicated
broker events. Time reversals block and make chronology-derived gap summaries
unreliable; input is never sorted to hide the reversal.

For silence longer than max_gap_seconds:

- full explicit CLOSED coverage is labeled closure-explained;
- OPEN duration exceeding the threshold is an open-session gap candidate;
- uncovered duration is unknown-session silence.

A quiet open market may also have no ticks: this is not proof of missing
records. Quotes inside a declared closure are a calendar/data conflict, not
silently deleted. An all-closed empty horizon still has no valid market quotes
and is unsuitable for strategy evaluation. Closure schedules are supplied
claims and require broker verification; UTC here does not establish the
broker server timezone/DST or trading-week rules.

Manifest intervals must be ordered, nonoverlapping, inside the horizon, and
have explicit accepted tick counts. The audit checks holes, per-window actual
counts, ticks outside windows, and explicit at_safety_limit flags. Coverage
of requested windows is not proof that the broker returned all ticks. Missing
windows/calendar evidence is reported, never invented. Adaptive manifests do
not themselves carry broker session/specification proof.

`normalized_quote_sha256` fingerprints only valid in-range normalized quotes
in received order. Invalid/out-of-range records are counted separately and
are not included in that digest; this is not a full raw-source file checksum.
`audit_config_sha256` fingerprints version, audit parameters, manifest,
calendar and provided specification/source. Labels and hashes do not
authenticate a broker or certify provenance. Per-symbol reports remain separate.

Memory is bounded by manifest/calendar sizes, histogram, example cap, and
quotes sharing a millisecond; the tick input may be a generator. Input-row,
example and same-millisecond budgets are explicit. Exceeding a tick budget
raises rather than certifying a partial prefix. Capturing six months may need
chunked storage and separate per-file raw hashes, which are future work.

Structural or spread/calendar conflicts return BLOCKED_TICK_QUALITY.
Otherwise status is REVIEW_TICK_QUALITY, with unresolved gap/duplicate/calendar
and manifest reasons. Every result has completeness_verified=False,
backtest_ready=False and execution_allowed=False. The module is an audit tool,
not proof of coverage, indicator quality, executable fills or profitability.

Validation uses synthetic fixtures only. Tests include explicit closures,
unknown/partly covered calendars, open-session silence, same-time quotes,
invalid chronology/prices, spread thresholds, manifest holes/counts/caps,
half-open boundaries, stream input, digest reproduction, separate symbols,
and both existing capture adapters. Real broker history is still unverified.
