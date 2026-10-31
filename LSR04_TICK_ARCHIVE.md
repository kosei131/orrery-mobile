# Reproducible normalized-tick archive — research only

`lsr04_tick_archive.save_tick_archive(path, ticks, audit_options=...)` streams
normalized ticks to a new, exclusively created directory. It writes:

- ticks.jsonl: exact serialized normalized rows in supplied order;
- audit.json: the existing lsr04_tick_quality audit result;
- manifest.json: schema/encoding, effective audit options, row and byte counts,
  SHA-256 hashes of both files, and a digest of the audit implementation.

The manifest is written last as the completion marker. Data and metadata files
are flushed/fsynced, but there is no directory-level atomic publication or
power-loss durability guarantee. An interruption can leave an incomplete
folder, which the verifier rejects. The writer never overwrites an existing
folder/file/symlink, silently resumes, or cleans up an incomplete archive.
Review or choose another destination explicitly after a failed write.

The return value includes manifest_sha256 and audit_config_sha256. Retain the
manifest pin independently of the archive. A local manifest alone can be
replaced along with local data: a hash is not a signature or broker proof.

`verify_tick_archive(path, expected_manifest_sha256=..., expected_audit_config_sha256=...,
max_ticks=...)` requires the independent manifest pin. It checks the exact
file inventory, regular files (rejecting visible symlinks), schema, UTF-8 JSON,
duplicate keys, byte/row counts, full tick-file hash and stored audit hash.
It then streams the saved rows through the existing auditor with the saved
options and requires exact canonical audit-result agreement. An optional
expected audit_config_sha256 additionally binds the caller's intended
conditions. A different audit implementation digest is rejected rather than
quietly reinterpreting an old report. Source-code newlines are normalized for
this digest so CRLF/LF checkouts do not change its identity.

Verification returns the recomputed report and integrity metadata after the
whole stream has been consumed. It does not expose a partially verified tick
iterator to a strategy. Downstream strategy consumption/integration is future
work; do not treat verification as order or backtest authorization. concurrent
external mutation/replacement is outside this local-file API's guarantee.
The application does not implement authenticated immutability or hostile
filesystem race protection.

The canonical rows have exactly time_msc, bid, ask. Same-millisecond and
identical normalized rows are retained. No data sorting/deduplication occurs.
Finite JSON-compatible quotes that the auditor flags (zero/crossed prices,
wrong chronology, out-of-range timestamps) can be archived with a blocked
quality report. NaN/Infinity, missing/extra raw fields and unsupported JSON
values are rejected instead of normalized away. This format does not preserve
raw MT5 flags/volume/last fields and is not a raw broker-event archive.

Effective options include source, symbol, UTC bounds, broker specification,
spread/gap thresholds, calendar provenance, capture manifest, audit row/example
limits and spread bins. Datetimes are frozen as UTC ISO strings. Caller inputs
are copied through canonical JSON before writing. No account credentials or
account IDs are collected by the writer; callers must avoid putting private
information in source/provenance labels. Six-month datasets should use bounded
chunks; multi-chunk catalogs, resume behavior and a dataset-wide trust root
are not implemented in this step.

Input is streaming. Each line is limited to 4096 bytes, metadata to 64 MiB,
and the verifier has an independent row budget (up to 100 million). A row/size
limit, malformed/truncated line, write failure, missing file, unexpected file,
unsupported schema, wrong pin, changed configuration or audit mismatch blocks
success. The audit's own resource limits also remain active. The existing
HaltStore persistence has separate responsibility and is unchanged.

A locally verified archive may still have BLOCKED_TICK_QUALITY. All save/verify
results keep completeness_verified=False, backtest_ready=False and
execution_allowed=False. No real MT5 dataset, broker authenticity, coverage,
trade profitability or executable fill quality has been verified here.

Synthetic tests cover roundtrip streaming, independent pin/config checks,
modified/truncated/appended ticks, audit/manifest tampering, recomputation of
forged reports, incomplete writes, existing destination protection, duplicate
records, invalid-quality preservation, schema/auditor-version mismatch,
duplicate JSON keys, nonfinite/extra input fields and independent row budgets.
