# Optional historical carry and daily boundary valuation

`replay_account` and `compare_catalog_accounts` now accept optional
`carry_quote`, `carry_source`, and `boundary_quote_max_age_msc`. The default
remains intraday: carry_quote=None never implies zero overnight cost and a
held position crossing a day boundary is rejected without this evidence.

Callback contract:

    carry_quote(symbol, side, lots, entry_msc, as_of_msc) -> cumulative signed USD cost

Positive means charges; negative means received credits. Source is required
and must identify the caller's historical cost assumption/evidence. Callback
must be deterministic and as-of, not use future posted values or today's swap
rate for past months. It must return zero at the entry clock. Nonfinite,
missing, source-less or same-clock changed values block. The code does not
validate broker provenance, conversion, rates, triple-swap days or posting
calendar; those are inputs, not guessed from weekday or symbol.

At each observed quote (and required boundary), only the difference from the
already booked cumulative value is charged/credited to cash balance. Repeated
identical cumulative totals do not charge again. Floating equity includes the
updated balance. Closing adds price PnL only; it does not charge carry again.
Trade net is price PnL minus upfront round-trip fee minus signed carry cost.
To reuse the existing performance helper's nonnegative cost schema, received
carry is explicitly reported as income; price_gross_pnl_usd and carry_cost_usd
remain separately visible. OPEN positions retain their booked fee/carry and
are excluded from completed-trade wins/expectancy.

Day boundary is the explicit UTC hour (default 10:00 UTC, Hawaii midnight).
A carried position must cross only one observable daily boundary at a time.
If a quote exists exactly at that boundary, use that quote. Otherwise only
the last already-observed quote BEFORE the boundary may be used, within the
explicit max age. Default age is zero (exact boundary required); maximum is
10000ms. This is an explicit last-observed-price policy, not interpolation or
an assertion that the price was executable at the boundary. Never use the
first later quote's price to set the opening equity retroactively.

The carry and historical USD PnL callbacks are evaluated at the boundary clock
using this as-of price. Day starting equity is captured after accrued carry,
before processing boundary-quote SL/TP fills. On a later first quote, current
carry/mark/fills are then applied separately. This preserves chronological
callback invocation and prevents double charging. Quote time and baseline
method are recorded in daily_snapshots. A callback must support boundary
valuation even when there was no quote exactly then. Missing/stale prices,
unobserved intervening days or nonpositive boundary equity stop the run
rather than reset the budget with an invented baseline.

The sampled global equity peak/DD includes the boundary snapshot. New-day
loss budget starts from that observed boundary equity; cost/price movement
already in the baseline is not re-counted as new-day drawdown. Later costs
can trigger the existing daily latch. The prior daily latch resets only at
a valid new session; the three-loss latch retains its no-auto-reset behavior.
This is a declared research convention, not a funding provider's day rule.

Limits remain: single symbol and one active position, no margin/stop-out or
combined XAUUSD+USDJPY risk, no real broker data/calibration, no complete
session-aware six-month replay. Planned entry SL risk reserves price loss and
upfront fee only: unknown future carry is NOT reserved or claimed covered by
the 0.25% planned-risk limit. Actual gap/carry losses can exceed it and remain
recorded. A future as-of carry allowance could be a separate risk input;
actual future carry must not be used for entry sizing.

Status with carry becomes SINGLE_SYMBOL_CARRY_ACCOUNT_RESEARCH (or
MATCHED_SINGLE_SYMBOL_CARRY_ACCOUNT_RESEARCH for the comparison). Without
carry, established intraday status strings remain. All outputs keep
six_month_backtest_complete=False, execution_allowed=False and
market_edge_verified=False. The Windows pilot still does not create or
calibrate these callbacks. Nothing here is a six-month return result.

Synthetic tests cover boundary equity plus floating PnL, one-time cumulative
charges, signed credits, as-of price rather than a later quote, missing/stale
boundary evidence, missing intervening days, invalid/changed cost inputs,
new-day fee breaches, simultaneous boundary/SL accounting, entry-sizing
prefix invariance, open-position costs and callback chronology. The account
comparison forwards identical optional carry settings to both independent
accounts; it does not share their balances or cost ledgers.
