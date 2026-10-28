# Confirmation/retest comparison into existing account replay

`lsr03_confirmation_accounts.compare_confirmation_accounts` connects the
existing causal confirmation universe/retest observation records to the
existing pinned tick loader and `lsr03_account_replay.replay_account`.
This is a Python API, not a new downloader, fill engine or order sender.

First-stage scope is two independent $3000 accounts, same symbol, same pinned
Bid/Ask catalog and explicit valuation/cost assumptions. One active position
per account; overlapping candidates are skipped through the existing engine,
not added as independent outcomes. Equity-based 0.25% sizing, sampled floating
DD, Hawaii-midnight daily boundaries, latched daily 1% loss stop and permanent
three-loss run latch are reused. This does not support multiple simultaneous
positions, scale-ins, partial exits, margin or combined-symbol execution.

## As-of prices and clocks

`compile_plans` requires confirmations, retest observations and exact M5 close
references, plus explicit symbol, fixed distance, target R, post-close delay,
entry validity window and maximum holding duration. The study cohort remains
confirmations in [2026-04-25,2026-09-25) UTC, matching the previous experiment,
not the requested separate six-month account horizon. Confirmation plans do
not depend on future retest status; waiting plans become known only at the
observed retest close. No-POI/expiry/unknown observations remain explicit.

All stop/target prices are fixed from the known M5 CLOSE before entry.
For BUY: stop=reference-distance, target=reference+distance*target_r; SELL is
symmetric. A quote must occur strictly after known_at plus an explicit delay
of at least 1ms, within the entry window. Missing exact reference raises;
future quotes are never used to set past target prices. Plans extending the
entry delay beyond the study horizon are omitted explicitly. Targets/stop
geometry can be rejected at actual entry by the existing engine.

This is intentionally a DIFFERENT benchmark from the prior public-M1 model,
which anchored fixed stop/TP distance to its assumed entry fill. Actual
entry-to-stop distance/effective RR can differ from reference distance/R.
Do not compare either account result to earlier R tables as if all execution
conditions were identical. No structure-SL policy is added at this stage;
it still needs a separate quote-verified pre-entry invalidation adapter.

## Observed-quote time-limit exit

Existing account candidates may optionally include positive integer
`max_holding_msc`. Omitting it preserves existing SL/TP-only behavior.
At the first OBSERVED quote at/after actual entry+duration, SL/TP are checked
first; otherwise close at Bid for BUY or Ask for SELL plus adverse explicit
slippage. The shared `market_exit_price` helper is used by the existing
SL/TP fill code and this expiry, avoiding a second closing-price formula.
The engine records `holding_deadline_msc` and `timeout_lag_msc`. It never
interpolates/backdates a deadline quote. Quote-source end before closure
retains an OPEN position; timeout losses count toward existing streak/day
stops. Same-clock re-entry remains prohibited. Carry/boundary requirements
still apply if holding crosses the configured daily boundary.

## Evidence and invocation

The adapter calls the shared `load_catalog_ticks`, including root pin,
source-label matching and global quality checks. A quality-blocked load
returns accounts=None without invoking account replay. Verified local hash
integrity is not proof that prices/costs came from a broker. Compiled plans,
configuration, omissions, input hash and account decisions are retained.
Historical USD PnL callback, volume lattice, fees, slippage and cost source
remain REQUIRED caller inputs. Zero cost is never invented from missing data.

API arguments include:

- path, expected_catalog_sha256, bar_source, as_of: existing pinned catalog contract;
- confirmations, observations, m5: causal signal records and known close references;
- fixed_distance, target_r, entry_delay_msc, entry_window_msc, max_holding_msc;
- volume_min/max/step, pnl_quote, round_trip_cost_per_lot_usd, cost_source, slippage;
- optional existing carry callbacks and explicit daily-boundary quote evidence.

For a 120-minute limit, max_holding_msc=7200000. No default broker fees,
contract values, lot sizes or USDJPY conversion are supplied. Prices in the
public OHLC sample must NOT be expanded into invented ticks to satisfy this
API. Bar/tick lineage remains caller-asserted and is explicitly unverified.

## Actual validation and limits

Synthetic tests cover the two independent account paths through the real
account engine, correct closing sides/slippage, exact and delayed timeout
quotes, OPEN at source end, SL priority, no same-clock reentry, three timeout
loss stopping, unchanged past plans with future data, and no replay on failed
global tick quality. The catalog loader is explicitly mocked only in unit
integration tests; these are NOT real-market or pinned-catalog performance.
Existing account, carry, sizing, risk and tick-fill tests remain in the suite.

No real-market account comparison has run in this step. The available public
M1 data do not provide historical executable Bid/Ask ticks and calibrated
broker costs/quantities. No new dollar profit, ending equity, 95% win rate or
six-month result is reported. `execution_allowed=False`,
`market_edge_verified=False`, `six_month_backtest_complete=False` remain.
Production/demo automatic orders stay disabled. Existing LSR/2.6 modules and
risk settings are unchanged. Next required input is a verifiable short Bid/Ask
segment plus explicit historical valuation/cost/quantity conditions, then
run both account paths on that same evidence before widening the period.
