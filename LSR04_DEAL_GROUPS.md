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
freshness or race-free execution. Unknown cash operations, balance changes,
corrections and separate commission rows block rather than being ignored.
INOUT and OUT_BY remain unresolved/unsupported.

Closed-trade streaks feed the existing account gate; three losses produce
LOSS_STREAK_STOP. `daily_deal_net` includes only deals timestamped on/after
the supplied UTC day boundary (through now), including partial closes and
entry costs. Completed position net includes all lifetime costs, including
pre-day entry costs. Both are account-currency amounts, never presumed USD.
`daily_equity_change` includes floating equity change; it is not expected to
equal daily deal net. `daily_reconciled=False` explicitly records that cash
flows and floating PnL have not been reconciled. UTC boundaries and starting
equity must be externally verified for the intended session/account.

Caller-supplied stop exposure has not been verified against broker positions.
Even a passing nested risk review returns BLOCKED_UNVERIFIED_STOP_EXPOSURE;
a failing review returns BLOCKED. Other incomplete states also block.
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
