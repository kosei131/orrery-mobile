# Entry timing and fixed exit-horizon diagnostic

Run `python orrery_xau_entry_exit_diagnostic.py` after the existing public
M1/M15 conversion and sweep/VHF sequence report. CI archives
`public_xau_entry_exit_diagnostic.json` with source hashes, timing rows,
per-policy/per-horizon outcomes, skips and common-resolved comparisons.

Predeclared horizons: 60, 120 and 240 minutes; same 10 candidates in the
2026-04-25 to 2026-09-25 UTC entry window, unchanged fixed-6 or sweep-extreme
SL, synthetic 0.6 spread and 1.5R target. The existing stop-spec builder and
fill simulator are reused. No automatic horizon, threshold or lot selection.
Both policies retain invalid pre-entry structures and missing outcomes in
explicit counts. A common-resolved subset across horizons is supplementary,
not a way to hide unresolved candidates.

The simulator now records STOP_AT_OPEN, STOP_INTRAMINUTE, TP_INTRAMINUTE or
TIMEOUT. This metadata does not change outcome calculations. Intraminute
exit timestamps are minute-open lower boundaries; elapsed minutes there are
lower bounds, not exact holding times. Timeout clocks are the final observed
bar close. Source OHLC cannot establish intraminute tick ordering.

Timing records sweep-to-entry and confirmation-to-entry delay. Directional
source quote drift uses only M1 opens at confirmation/entry; missing quotes
remain null. Positive drift means price advanced in the trade direction
before assumed entry. This is not evidence that an earlier executable entry
or captured profit was possible. The fixed <=15/>15-minute cohorts are
purely descriptive, not fitted entry filters. Outcome fields and quotes after
entry do not affect these observations.

Local result: confirmation-to-entry minimum 5, median 10, maximum 35 minutes.
Fixed-6 SL: all 10 resolve to SL or TP within 60 minutes (5 each), hence all
three horizons are identical: mean +0.25R, PF 1.5. The 120-minute timeout
cannot explain the fixed-SL results in this sample. Sweep-extreme SL retains
7 resolved candidates and 3 pre-entry invalidations for every horizon:
60 minutes mean -0.3339R, 120 -0.4224R, 240 -0.3824R. All three remain negative.
No horizon was adopted and no improvement in broker-account profit is claimed.

All data were already inspected, the sample is very small, and real Bid/Ask,
fees, slippage, swap, margin, account loss stops and historical session
exceptions remain unverified/unmodeled here. This is neither a six-month
$3000 account backtest nor the formal 2.6 method. Orders remain disabled.

Next research hypothesis: investigate waiting for retest versus confirmation
entry on ALL causally available confirmed candidates. Never take the current
10 eventual retouches and retrospectively enter them earlier; that would
condition earlier entry on future retouch survival. Preserve original LSR
baseline and report this alternative separately on untouched data when available.
