# Contiguous, pinned tick-archive catalog — research only

`lsr04_tick_catalog.save_tick_catalog` consumes an iterable of chunks, each
with `ticks` (iterable) and `audit_options` (existing archive audit settings).
It writes bounded child archives sequentially through save_tick_archive,
then writes catalog.json last. It does not collect the full tick history in
memory. Broker capture-to-chunk generation is not added in this step.

Example API shape:

    saved = save_tick_catalog(new_directory, chunks,
        start_utc=explicit_utc_start, end_utc=explicit_utc_end)
    result = verify_tick_catalog(new_directory,
        expected_catalog_sha256=saved['catalog_sha256'],
        expected_shared_options_sha256=saved['shared_options_sha256'])

Retain the root catalog pin independently of the dataset. The trust chain is
root pin -> catalog -> each child manifest pin -> tick/audit bytes -> fresh
audit reproduction. A pin is a local integrity reference, not a broker
signature. A user who changes both data and its externally retained pin has
not authenticated history. Audit implementation compatibility rules from the
single-archive verifier still apply.

Chunk directories are deterministic chunk-000000, chunk-000001, etc. Catalog
references must match that sequence exactly; arbitrary paths, absolute paths,
parent traversal, missing children, unexpected members and visible symlinks
are rejected. Existing roots are never overwritten, resumed or cleaned up.
A capture/generator/write/budget failure leaves an incomplete root with no
completed catalog; verification does not return prefix success. A new
explicit destination is needed after reviewing an incomplete save.

The declared half-open UTC/millisecond intervals must form an exact partition
of the requested horizon in input order, with no gaps, overlaps, reversed
chunks or missing tail. Chunk boundaries own their starting timestamp, not
the preceding chunk's ending timestamp. Individual archive audits retain
out-of-range/duplicate/invalid records and their quality blocks; cataloging
does not repair or deduplicate them. Empty chunks remain in the partition
and are reported as blocked-quality chunks, not silently removed.

Shared options must be byte-equivalent after canonical JSON freezing:
canonical symbol, source label, broker specification, thresholds, spread bins,
resource settings and session_source. Only start/end, capture windows and
session intervals vary by chunk. XAUUSD and USDJPY require separate catalogs.
A source label is a caller assertion, not authentication. Session schedules
and broker specifications still require real broker verification.

Verification reuses verify_tick_archive for every child, checks its pinned
config hash, independently recomputed count/quality and declared bounds,
then checks total counts. The archive verifier now returns its verified
options to avoid reopening unverified metadata for this comparison; previous
save formats and behavior are unchanged. Verification returns no strategy
iterator and never sends orders.

Default budgets are 1000 chunks and 100 million total rows, configurable up
to 10000 chunks and 100 million rows. Each child retains its own audit row
limit. The catalog verifier has separate caller limits and refuses a dataset
larger than them. Metadata read/write limits from the archive module apply.
Counts, source options and catalog metadata fit in memory; tick data are
processed one child/stream at a time. Performance on a real six-month dataset
has not been benchmarked.

A verified catalog proves agreement of local bytes, metadata and declared
interval coverage only. It does not prove that the broker supplied all ticks.
Quality audits remain per chunk: a long quote-silence interval spanning two
chunks may need a separate global audit, especially if each edge is shorter
than the gap threshold. Global silence analysis, streaming verified strategy
consumption, chunk resume, automatic MT5 orchestration and raw-event retention
are future work. Concurrent external filesystem modification is outside this
API guarantee, as documented for the single-archive API.

All results keep completeness_verified=False, backtest_ready=False and
execution_allowed=False. VERIFIED_LOCAL_CATALOG_ONLY is an integrity status,
not a passing market-quality judgment; inspect blocked_quality_chunks and
review_reasons. No actual six-month MT5 history or profitable strategy was
verified by implementing this catalog.

Synthetic tests cover streamed roundtrip, half-open boundaries, gap/overlap
and tail rejection, mixed provenance/specification/policy, modified/missing
children, root-pin mismatch, catalog/archive disagreement, unsafe references,
existing destination protection, chunk/row budgets, empty chunks, interrupted
capture, unexpected files and expected-policy mismatch.
