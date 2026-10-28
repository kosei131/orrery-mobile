# Requested $3000 / six-calendar-month real-data backtest

The fixed request is stored in backtest_3000.json:
initial equity USD 3000; XAUUSD and USDJPY separately; April 27 through
October 27, 2026, midnight Hawaii to midnight Hawaii, [start,end). UTC bounds
are April 27 10:00 through October 27 10:00 (183 calendar days).
The period excludes October 27 after its Hawaii midnight; extending to a
later exact observation time requires an explicit updated horizon.

The initial research baseline uses the existing conservative 0.25% trade
risk, 1% daily loss, 1% basket risk and three-loss stop. At the initial $3000
this means $7.50 proposed trade risk and $30 day/basket budgets. These are
research settings, not actual broker quantity calculations or funding rules.
The research daily boundary is Hawaii midnight (10:00 UTC), separate from
broker/provider session rules. No hypothetical return is inferred from them.

Run the evidence check from the repository directory:

    python lsr03_backtest_preflight.py --config backtest_3000.json

catalogs is empty by default, not filled with synthetic data or an assumed
zero-profit series. When actual captured history is available, supply each
symbol's explicit catalog path and independently retained catalog_sha256.
The existing catalog verifier checks every archive. The checker additionally
binds symbol and exact requested horizon, and reports quality deficiencies.
It never extrapolates a short pilot into six months.

This command is an evidence check, not a backtest implementation. It always
returns BACKTEST_NOT_RUN and exit 2. Profit, ending equity, return, DD and
trade count remain null. A matching local catalog alone cannot lift these
remaining implementation blockers:

- time-ordered account replay with floating equity, simultaneous exposure,
  actual daily and streak stops;
- historical account-USD valuation, executable quantities, margin and
  verified commissions/swaps/slippage;
- structural OHLC replay across actual market sessions without invented bars.

The existing short Windows DEMO pilot can test data access but does not solve
these six-month requirements. Account engine and cost/session work can be
implemented independently; actual real-market validation still requires the
Windows DEMO terminal's history or equivalent verified exports. Do not ask for
account passwords or claim the environment is connected without evidence.

Current execution in the development environment: both symbol catalogs are
missing; BACKTEST_NOT_RUN, net profit null. This is not $0 profit and not a
$3000 ending balance. No real six-month run or performance result exists.
Unit tests exercise missing/invalid inputs, pinned short-history rejection,
exact request/risk settings, no input mutation and absence of fake metrics.
