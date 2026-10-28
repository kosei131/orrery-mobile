# Pinned ticks to matched LSR02/03 candidate outcomes

`lsr03_tick_study.study_catalog` connects the existing pinned catalog,
LSR02/03 adapter and Bid/Ask replay_exit to a descriptive price-R report.
It does not change LSR01, LSR02, VHF, Reversal04 or the existing 2.6 modules.

Required inputs are a catalog path and independent root hash, explicit
h4/m15/m5 closed bars and matching bar_source label, as_of exactly at the
catalog horizon end, structural buffer, fixed benchmark target_r,
round_trip_cost_per_unit and adverse slippage in quote-price units.
Source-label agreement is a consistency check, not OHLC provenance proof.
Caller OHLC is hashed for report reproduction but not reconstructed or
matched against the stored ticks in this step. A source, bar or broker-spec
mismatch must be resolved before any real strategy conclusion.

The study verifies every catalog member, rechecks manifest/tick hashes during
its own read, then runs one combined horizon quality audit over all quotes,
windows and session intervals. This catches quote-silence intervals spanning
chunk boundaries which per-chunk edge checks may miss. Structural quality
issues, unknown/open-session long-gap candidates and absent window manifests
block outcomes. Explicit broker-verified CLOSED intervals may explain a gap;
no weekend/holiday calendar is invented. Same-millisecond duplicates remain
ambiguous normalized events and are retained in audit findings.

Existing compare_vhf produces the original structural and annotated traces.
The study evaluates the first RETEST of each unique sweep candidate only.
The VHF group is fixed at that RETEST using only available confirmed closes.
Entry requires the first quote strictly after that close plus explicit delay
(default 1ms). A candidate invalidated/expired before its first available fill
is not entered. Each candidate's fill outcome is calculated once, then reused
for the LSR02 baseline, VHF-pass and VHF-filtered groups.

BUY enters Ask and exits Bid, SELL enters Bid and exits Ask. Existing
replay_exit supplies stop/target and first-quote gap behavior. Stop stays the
original structural stop. Target is explicitly actual modeled entry +/-
target_r * initial stop distance: this is a fixed-R execution benchmark,
not the author's 2.6 analysis or a replacement of existing target research.
Slippage is adverse at both entry and exit. A nonpositive modeled exit is
rejected as unrepresentable. Costs are a nonnegative explicit round-trip
quote-price-per-unit amount, separate from spread and slippage already in
prices. This is not broker commission/swap/currency attribution; conversion
to account-currency PnL and broker fee evidence remain required future work.

Report fields include individual fills, price risk, gross/cost/net R,
closed/open/not-filled counts, mean net R, average win/loss R, win rate and
PF based on R for each group. Filtered positive outcomes are reported as
missed_profit_r and filtered negative outcomes as avoided_loss_r. Both are
reported, never just the favorable side of filtering. OPEN outcomes are not
wins or closed-trade average inputs. No trades are fabricated when no
candidate or post-signal quote exists.

Independent candidates can overlap and do not form an investable portfolio.
No balance/equity curve, account DD, simultaneous-risk, daily loss stop,
loss-streak simulation, margin/liquidation or live order gate is claimed by
this report. Type A-like directional structural conditions come from the
existing adapter, but formal Type A/B classification/certification is not
implemented. No 04 adoption, profitable configuration, OOS result or real
market edge is asserted. market_edge_verified=False,
bar_provenance_verified=False, portfolio_metrics_available=False and
execution_allowed=False remain explicit.

This pilot intentionally reads a bounded tick list to reuse the existing
list-based fill simulator. Defaults: 500000 ticks, 1000 candidates, five
million candidate/tick visits. Limits are enforced without returning a
successful partial study. It is not a streaming six-month strategy engine.
Longer histories require bounded segments or a later streaming execution
model with the same tested semantics. Existing structural replay rejects
missing bar intervals; session-aware OHLC handling is not bypassed or filled
with invented candles. The current module therefore requires suitable
continuous closed-bar inputs and a compatible history horizon.

Validation uses synthetic OHLC and quote fixtures only: BUY/SELL, post-close
fills, identical outcomes under different VHF cutoffs, stop gaps, costs
turning gains negative, open/no-fill handling, source/horizon mismatch,
invalid ticks, global gaps, work budgets and no-candidate behavior. A separate
fixture catches silence spanning two individually acceptable chunks.
Actual Windows MT5 data capture, broker-cost calibration and the first
real-data PnL report remain outstanding.
