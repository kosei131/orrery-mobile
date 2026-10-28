# LSR02/03 candidates -> independent $3000 intraday accounts

`lsr03_account_study.compare_catalog_accounts` connects pinned tick evidence,
existing LSR02/VHF traces and the intraday account replay engine. It reuses
load_catalog_ticks for full catalog verification/global quote-quality checks,
collect_retests for unique first-RETEST candidate extraction, and replay_account
for broker-quantity rounding, costs, balances, floating marks and stop rules.
No independent fill/position/equity formula is introduced here.

The existing price-R study now uses the same loader and RETEST collector,
preserving its established behavior and tests. The account comparison does not
call its already-computed future outcomes or scale total candidate R by $7.50.
It constructs as-of plans instead: known clock, strictly later eligibility,
predefined expiry, original structural SL and a benchmark target.

The target is frozen at RETEST close:

    BUY target = RETEST close + target_r * (RETEST close - original SL)
    SELL target = RETEST close - target_r * (original SL - RETEST close)

This is explicitly RETEST_CLOSE_FIXED_R_BENCHMARK_NOT_2_6. It is neither the
author's 2.6 definition nor a replacement of existing context/target research.
It differs from the older independent price-R study's target measured from
actual modeled entry; do not compare those output populations as if target
policy were held constant. Within this account comparison, both accounts use
identical fixed targets/plans, clocks, fees and quotes. Actual entry gaps that
invalidate SL/entry/target geometry skip rather than move target opportunistically.

The VHF pass/filtered group is frozen at the first confirmed RETEST, using
existing compare_vhf's as-of closed bars. Later structural invalidation is a
separate timestamped cancellation event. replay_account applies it only when
that event is already observable by the first eligible quote, preventing stale
unfilled entries. A later invalidation cannot retroactively delete a filled
trade and does not introduce a new forced exit rule; an open position still
uses its existing SL/TP. No future PnL/exit outcome fields enter a plan.

The LSR02 account receives every valid covered candidate. The LSR03 account
receives the VHF-pass subset. Each starts with its own $3000, lot sizing,
equity, fees and held stop state. A trade rejected while the LSR02 account is
busy/stopped may still be eligible in LSR03: this is an actual account-path
comparison, not additive independent-candidate loss attribution. It does not
combine the two accounts or recommend trading both as a shared portfolio.

Plans whose RETEST precedes the pinned quote horizon are explicitly omitted,
not entered late at the archive's first quote. Invalid target geometry or
an already-expired delayed RETEST is omitted with a reason. No candidate is
fabricated when the structure engine emits none. Global quote-quality blocking
returns accounts=None, not a fake unchanged-equity performance result.

Required account assumptions remain explicit: historical USD PnL callback,
broker volume min/max/step, round-trip USD fee per lot and its source,
adverse slippage, day boundary and research target. Callback must be a pure,
deterministic as-of function of its parameters for matched comparison;
its provenance cannot be authenticated by a Python callable. Source-label
agreement and OHLC hashes are not proof that warmup bars came from the same
market feed. bar_provenance_verified remains False.

Report includes both account paths, eligible/pass/filtered counts, exact plans,
groups, cancellations/omissions, global audit, root catalog pin, OHLC hash and
research parameters. Integrity, bar/source, sizing and callback failures are
not ignored. A blocked second account does not produce a successful partial
comparison. Existing engine/candidate/tick resource limits still apply.

Scope remains single symbol, one position per account, intraday, $3000 and
0.25% research risk. Overnight/swap, margin/liquidation, XAUUSD+USDJPY combined
account, historical broker fee/FX evidence, session-aware six-month replay,
OOS evaluation and actual Windows broker data are unfinished. The Windows
pilot still creates the original price-R report; this account comparison is
an explicit Python API requiring a historical USD valuation callback, not
automatically activated in that CLI. It never authorizes orders or claims a
completed six-month run: execution_allowed=False, market_edge_verified=False,
six_month_backtest_complete=False.

Synthetic tests connect the real candidate path to account sizing/fills,
check target/as-of prefix invariance, independent VHF-filtered capital,
OPEN exclusion, global quality and source rejection, trace alignment,
expiry/delay, pre-fill cancellation, post-fill invariance and invalid
cancellation clocks/identities. These are code-behavior tests, not market
profit or a $3000 six-month result.
