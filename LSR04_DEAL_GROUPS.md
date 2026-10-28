# MT5 position lifetime grouping — research only

`lsr04_deal_groups.reconcile` groups IN/OUT deals by position_id and orders
by time_msc/ticket. Partial exits do not finalize a trade. Profit, commission,
swap and fee from entry and exit deals are summed in account currency.
Completion requires a valid running volume balance reaching zero. Duplicate
tickets and unknown deal categories raise ValueError; inconsistent lifetimes,
INOUT reversals and current open positions make the streak unknown.
OUT_BY is intentionally unsupported and rejected, rather than miscounted.
Both ordinary hedging lifetimes and netting additions/reductions can be
accounted for; netting reversals and close-by attribution remain unimplemented.

`history_complete=False` is the default. True is an external assertion that
all relevant lifetimes, earlier streak history and broker fees are accounted
for, not a completeness guarantee obtained from MT5. Unattributed balance,
commission and correction operations must not be filtered out to obtain a
passing result. Fetching today's deals alone is insufficient. An open position
absent from the supplied deals also blocks certification. A breakeven trade
resets the consecutive-loss count. Three fully closed net losses set the
research `loss_streak_stop` flag; unresolved history returns None.

## DEMO history bridge

`demo_day_check` now fetches the explicitly supplied `history_start_utc`
through `now_utc`, without symbol filters, then invokes this grouping engine.
The default history start is the day boundary and completeness defaults to
False. Supply a verified history boundary and explicit completeness assertion
only when earlier trades and all fees really have been accounted for.
A successful MT5 API response alone never sets that assertion.

The bridge validates trade types, symbol/direction consistency, deal time
bounds, required numeric fields, and current POSITION_IDENTIFIER values.
Account login/server/currency/DEMO identity is checked before and after the
reads; identifiers are not returned in the report. Identity changes discard
the result. These reads are not an atomic snapshot and do not certify data
freshness or race-free execution. Unknown cash operations, corrections and separate commission rows block
rather than being ignored. Explicitly verified BALANCE cash rows are
handled separately as described below.
INOUT and OUT_BY remain unresolved/unsupported.

Closed-trade streaks feed the existing account gate; three losses produce
LOSS_STREAK_STOP. `daily_deal_net` includes only deals timestamped on/after
the supplied UTC day boundary (through now), including partial closes and
entry costs. Completed position net includes all lifetime costs, including
pre-day entry costs. Both are account-currency amounts, never presumed USD.
`daily_equity_change` includes floating equity change; it is not expected to
equal daily deal net. `daily_reconciled=False` explicitly records that the full equity
components have not been independently reconciled. UTC boundaries and starting
equity must be externally verified for the intended session/account.

Caller-supplied stop exposure has not been verified against broker positions.
Without a verified daily baseline or with a balance mismatch, a grouped
result returns BLOCKED_DAILY_RECONCILIATION. A matching balance still leaves
BLOCKED_UNVERIFIED_EQUITY_AND_STOP_EXPOSURE (or BLOCKED when existing risk
reasons apply). Other incomplete states also block.
No order API is added. execution_allowed is always False.

Reference: https://www.mql5.com/en/docs/constants/tradingconstants/dealproperties

Validation: synthetic fixtures only, including partial exits, entry fees,
three losses, breakeven reset, out-of-order input, duplicates, invalid
chronology, identifier reuse, missing open lifetimes and unsupported OUT_BY.
No MT5 connection or market profitability has been verified.

Bridge reference: https://www.mql5.com/en/docs/python_metatrader5/mt5historydealsget_py
Bridge tests use fake MT5 records: overnight entry fees versus daily totals,
partial exits, three completed losses, truncated history, cash operations,
account changes, wrong trade direction, failed reads, duplicate/future rows,
missing fee, invalid equity and absent completeness assertions.

## Daily balance reconciliation

`day_start_snapshot` is an externally verified dictionary with `at_utc`,
`login`, `server`, `currency`, `trade_mode`, `balance`, `equity`, `verified`.
It must match the exact supplied session boundary, account identity and
`day_start_equity`. It is not reconstructed from today's closing balance.
No caller baseline means no reconciliation. The snapshot currently must be
supplied by the caller; automated boundary capture/persistence is not added.

`lsr04_daily_reconciliation.reconcile_day` checks, in account currency:

    closing balance - opening balance = daily trade net + external cash net

Default rounding tolerance is 0.01 account-currency units (configurable only
between zero and 0.01). A match requires explicit history completeness and
baseline verification. Missing/unclassified fees remain blocking and a match
does not prove that no offsetting omissions occurred.

`verified_cash_flows={ticket: signed_amount}` is external evidence that a
specific BALANCE deal is a deposit/withdrawal, not an accounting correction.
The bridge checks exact profit/amount agreement, zero volume, position_id=0,
and zero commission/swap/fee. Every supplied evidence ticket must exist in
fetched history, and every nontrade row must be classified. Cash rows are not
passed to position grouping or counted as wins/losses. Only rows at/after
the day boundary count in the day's cash net. CREDIT, correction, separate
commission and other operations remain unsupported and block. The code cannot
authenticate a caller's assertion about the economic purpose of a BALANCE row.

A nonzero daily external cash net returns BLOCKED_CASH_ADJUSTED_RISK_REQUIRED:
the existing raw-equity risk review is diagnostic and cannot be relied upon
for a cash-adjusted daily limit. This prevents deposit-masked losses from
producing an acceptable overall state. Cash-adjusted risk gating is future
work, not silently approximated here.

`daily_review.balance_reconciled` means only conditional balance agreement.
`daily_reconciled` stays False because floating PnL, credit, blocked funds,
and other broker-specific equity components are not independently verified.
The equity-minus-balance change is labeled `nonbalance_equity_component_change`,
not floating profit. Deposits/withdrawals are separately reported and excluded
from `equity_change_excluding_external_cash`; neither is strategy profit.
Account reads remain non-atomic and require live broker verification.

Sources:
- https://www.mql5.com/en/docs/constants/tradingconstants/dealproperties
- https://www.metatrader5.com/en/terminal/help/trading/performing_deals

Synthetic tests cover balance residuals, floating/equity changes, rounding,
verified deposits/withdrawals, missing/mismatched cash evidence, prior-day
cash exclusion, baseline account/time/equity mismatch and absent verification.

## Account-wide sampled stop exposure

`lsr04_mt5_position_risk.demo_position_risk` reads the complete unfiltered
positions_get result on a broker-reported DEMO account. It does not limit the
account to XAUUSD/USDJPY or infer contract sizes from symbol names. Broker
symbols, including suffixes, must resolve through symbol_info and a fresh
symbol_info_tick. Unsupported symbols are not silently skipped.

For each position the report includes identifier, symbol, direction, actual
volume, entry, SL, Bid/Ask, tick timestamp and two order_calc_profit estimates:

- entry_to_stop_pnl: signed hypothetical price PnL from entry to SL;
- incremental_price_loss: loss from the current closing side to SL, BUY Bid
  or SELL Ask. This estimates additional equity reduction, without adding
  already-incurred floating losses a second time.

A profit-locking SL above a BUY entry or below a SELL entry is allowed only
when it is still adverse to the current closing price. Its additional equity
risk is counted; unrealized/locked profit never offsets another position's
stop risk. A reached/crossed SL blocks instead of producing zero risk.

`cost_allowances={position_identifier: amount}` must include exactly every
open position. Each finite nonnegative amount is externally supplied in
account currency for incremental exit costs, future swaps and adverse
slippage/gaps. No implicit zero is inserted. Explicit zero is a research
assumption, not a statement that broker costs or gap risk are absent.
Already posted costs must not be charged again. Allowance correctness and
actual stop execution are not independently verified; the result is never a
worst-case loss guarantee. No margin/liquidation or pending-order model is
included. Hedged positions are summed without netting or correlation credit.

Quotes must have positive uncrossed Bid/Ask, nonfuture integer time_msc and
age at most 5 seconds by default (configurable up to 30). Exact-boundary age
is allowed; one future millisecond blocks. Caller UTC time must be accurate.
SL, entry, volume, identifiers, broker estimates and all totals must be
finite/valid. Missing SL, missing symbol, invalid side, missing cost allowance
or failed broker calculation discards the whole aggregate: total=None and no
partial rows are returned. An explicitly empty portfolio with empty allowances
is zero only after successful broker reads and checks.

The module rechecks account identity, captured equity, and position
identifier/ticket/symbol/side/volume/entry/SL after valuation. Changes block;
unchanged endpoints do not prove atomicity or absence of transient changes.
Floating prices are sampled and not treated as a guaranteed executable quote.

`demo_day_check(..., stop_cost_allowances=...)` optionally invokes this
valuation with its prior account/position snapshot as a consistency check.
Failure blocks before risk review; success replaces caller existing_stop_risk
with the broker-modeled incremental total. The optional argument defaults to
None for compatibility, leaving the old manually supplied estimate explicitly
unverified. Existing history, daily reconciliation and cash-flow blocks remain
active. Even successful valuation does not remove the final equity/cost and
stop-execution verification block. Full-history open positions currently keep
streak certification blocked conservatively, as in the existing grouping API.

References:
- https://www.mql5.com/en/docs/python_metatrader5/mt5ordercalcprofit_py
- https://www.mql5.com/en/docs/python_metatrader5/mt5symbolinfotick_py

Synthetic tests cover BUY/SELL sides, actual volume, locked-profit stops,
account-wide sums, missing costs, empty portfolios, unsupported symbols,
stale/future/crossed quotes, reached stops, invalid broker calculations,
account/equity/position changes, duplicates and account-bridge integration.
No live MT5 connection, broker fee validation or real-market performance
has been verified by these tests.
