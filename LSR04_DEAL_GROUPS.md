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

The existing demo_day_check remains blocked: it is not yet wired to a full
history fetch and this grouping result. Daily equity reconciliation, deposits,
withdrawals, timezone session boundaries, account identity recheck, complete
SL exposure and authoritative broker fee coverage are subsequent work.
No order API is added. execution_allowed is always False.

Reference: https://www.mql5.com/en/docs/constants/tradingconstants/dealproperties

Validation: synthetic fixtures only, including partial exits, entry fees,
three losses, breakeven reset, out-of-order input, duplicates, invalid
chronology, identifier reuse, missing open lifetimes and unsupported OUT_BY.
No MT5 connection or market profitability has been verified.
