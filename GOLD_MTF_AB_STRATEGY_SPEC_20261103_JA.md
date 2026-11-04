# ORRERY FX — Gold A/B multi-timeframe research hypothesis (2026-11-03 HST)

This is a **new separate research hypothesis**, not a change to locked HalfTrend/LSR02 strategies, not live trading and not validated alpha.

## Frozen comparison rules for the initial diagnostic

- Input: XAUUSD complete H4, M15, M5 bars, confirmed and time-aligned in UTC; fail closed on missing bars. No artificial data filling or futures.
- H4 direction: last 3 confirmed bars have strictly rising highs and lows for UP (falling for DOWN). Otherwise no signal.
- M15 sweep: last eligible confirmed M15 candle wicks beyond the previous 8-candle low/high then closes back within it. If one candle sweeps both boundaries, reject the event as directionally ambiguous. Sweep expires after 60 minutes.
- M5 confirmation: current closed M5 candle closes through the structural high/low of the five contiguous M5 candles closed by the sweep timestamp, with a directionally supporting body. Earliest confirmation only. Cancel after structural invalidation before confirmation.
- A continuation: BUY after low-side sweep when H4 is UP, SELL after high-side sweep when H4 is DOWN.
- B counter-sweep: opposite H4 direction only, and M15 wick must also clear the prior three completed H4 bars' most extreme high/low (including the most recently closed H4 bar) in the reversal direction. A and B never share performance cohorts.
- Research stop: opposite sweep extreme plus 0.10 XAU price buffer. It is an **indicative structural stop**, not an actual broker stop or risk sizing instruction.
- Minimum price room: the prior 3 completed H4 outer extreme must offer at least 1.5 times the indicative stop distance, otherwise reject. No forced 1.5R target or assumption of fill.
- Candidate timestamp: current confirmed M5 close. Indicative signal close is **not a filled entry**. Actual next available Bid/Ask entry, fees, slippage, timestamp cross-source matching, realized R, win rate, PF and drawdown are **unverified**.
- Source validity: results from public M15 OHLC samples cannot be combined with other providers' ticks, nor used as a substitute for the 28-day frozen HalfTrend prospective study.
- Required following experiments: count every candidate by A/B and month; preserve missing/invalid candidates; align H4/M15/M5 bar coverage; evaluate fixed candidate IDs on the same broker Bid/Ask feed; compare a no-filter baseline with VHF filter using the same entry universe; test period and spread robustness. Do not optimize after reviewing holdout.
- Execution, deployment, trade approval, strategy adoption and merging remain disabled.

Implementation: `orrery_gold_mtf_ab_hypotheses.py`; regression tests: `test_gold_mtf_ab_hypotheses.py`. A passed unit-test or CI check verifies software behavior **only**, not strategy profitability.

## Public-source candidate-count replay

`python orrery_gold_mtf_ab_replay.py PINNED_RAW_SOURCE.csv COMPLETE_BARS_DIR NEW_OUTPUT.json`

The reporter scans completed H4/M15/M5 candles on one pinned public source, refuses missing contiguous lookback, and outputs signal counts by A/B plus unknown actual PnL fields. This only measures observable candidate frequency. No quote-basis verified Bid/Ask is present and there is no independent execution chronology, fee, slippage, or actual win rate. New tests: `test_gold_mtf_ab_replay.py`. The research branch must not adopt its results into locked strategy definitions.
