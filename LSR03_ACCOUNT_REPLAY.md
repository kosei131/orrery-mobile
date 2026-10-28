# Intraday $3000 account replay prototype

`lsr03_account_replay.replay_account` is the first account-level tick replay
stage for the $3000 research request. It is single-symbol and one-position;
it is not the completed two-symbol/six-month backtest. No MT5 call or order
API exists. The existing candidate-R study remains independent and is not
silently treated as a portfolio input.

Inputs are chronological normalized quotes, confirmed candidate plans and
explicit broker volume min/max/step, historical account-USD PnL callback,
round-trip fee per lot, cost-source label and adverse price slippage. Each
plan contains only id, symbol, side, known_at_msc, eligible_after_msc,
expires_at_msc, stop and target. Future outcome/exit/PnL fields are rejected.
The caller is responsible for producing targets and eligibility as-of the
known clock; schema validation does not prove the absence of lookahead.

The PnL callback signature is:

    pnl_quote(symbol, side, lots, entry_price, close_price, at_msc) -> signed USD

It is required for sizing, actual fills and floating marks. No contract-value
or USDJPY conversion is guessed from a symbol string. Caller valuation may be
synthetic or broker-calibrated; this function does not authenticate it. Broker
currency conversion for a hypothetical stop is evaluated with information
available at that entry clock, not a later actual currency rate. Callback
failure/nonfinite output stops the simulation, never substitutes zero.

Initial capital is exactly $3000. Research trade risk is 0.25% of equity at the
entry event. The existing broker sizing function rounds down to the broker
lot lattice using one-lot adverse stop valuation PLUS the full explicit
round-trip fee. The chosen lot's actual stop valuation is then rechecked;
a nonlinear callback that exceeds budget blocks instead of increasing lots.
The existing account gate checks fixed opening-day 1% daily/basket budgets and
remaining daily capacity. No future trade result affects prior sizing.

Full modeled round-trip fee is charged at entry. This deliberately conservative
timing is an explicit assumption, not actual broker commission posting. Fee
rate must be finite/nonnegative; missing fee is not zero. Slippage uses the
existing replay_exit behavior at entry and exit; BUY opens Ask and marks/closes
Bid, SELL opens Bid and marks/closes Ask. Existing replay_exit is reused for
each observed quote and stop/target fills rather than a second fill formula.
A gap can exceed planned risk and is recorded. Insolvent paths block pending a
proper liquidation model; they do not produce a successful truncated report.

Pending plans are considered at their first eligible quote and consumed even
if skipped. They are not deferred until a profitable/later price appears.
Existing exits settle before that quote's new plans, but same-timestamp
re-entry is prohibited. Overlapping plans skip while a position is open; no
candidate outcomes are simply added as if capital were unlimited. Plan order
is the explicit tie-break for same-quote signals, at most one active position.

Balance changes with upfront fee and closed gross PnL; equity includes current
floating PnL. Peak and maximum sampled equity drawdown update on every quote
and entry/exit mark. OPEN positions remain separate and never count as wins.
Closed-trade statistics reuse the existing realized performance helper, but
its DD/streak convention is not used for this engine's account gates.
Net R uses planned total stop loss including the fee as its denominator.

The explicit daily boundary defaults to 10:00 UTC (Hawaii midnight). If flat
at rollover, new day starting equity is the known cash balance and only the
daily latch resets. A daily drawdown at/above 1% latches new-entry stopping
through the current session, including unrealized breaches that later
recover. Existing positions continue to their SL/TP; no unrequested force
close is introduced. Three net closed losses latch for the remaining run;
breakeven resets the consecutive count, but never an already-held latch.
No automatic next-day reset of the streak latch is assumed.

Overnight positions raise rather than assume swaps/boundary equity. Other
unimplemented features: combined XAUUSD/USDJPY portfolio, swaps/carry, margin,
stop-out/liquidation, deposits/withdrawals, partial exits, trailing, news,
provider rules, verified tick/bar/candidate lineage and streaming six-month
execution. Inputs and callback provenance remain caller assertions. Global
quote quality/catalog validation is not duplicated in this low-level API;
production integration must perform those existing checks before calling it.

Default resource limits: one million quotes, ten thousand candidate plans,
twenty thousand account-event output rows. No successful prefix result on
limit failure. The report includes end balance/equity, closed trade net,
open position, per-decision/transaction events, sampled DD and held stop flags.
It always reports execution_allowed=False, market_edge_verified=False and
six_month_backtest_complete=False. These modeled USD numbers are not real
market performance or a promised return.

Synthetic tests cover entry-time sizing, cost-inclusive risk, BUY/SELL,
future-outcome rejection, no overlap/same-timestamp re-entry, unrealized PnL,
open exclusion, price-gap losses, daily stopping/recovery, three-loss stopping,
expired/unfilled plans, missing valuation/fees, unsupported overnight positions
and resource exhaustion. No actual market dataset is used.

As-of candidate adapter: see LSR03_ACCOUNT_STUDY.md. The engine also accepts
`cancellations` as chronological {id, known_at_msc} events for an existing
plan. A known pre-fill cancellation skips the unfilled plan. Later events
never erase earlier entries or force an existing position out. Unknown IDs,
duplicate events and backward/before-plan clocks are rejected.
