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

## 既存の出口判定を固定した費用感度

同じ原本ハッシュで候補・出口を再計算した。各候補の次M5始値から構造SLまでの距離で、仮定した一定の往復費用をRへ換算して差し引いた。0、0.30、0.54、0.70ドルの比較は、OHLCのTP/SL到達順や入口を動かさない感度分析。0.54ドルは比較用の仮定であり、対象取引の実測費用は未確認。公開OHLCの価格種別も未確認。

| 戦略 | 決着/候補 | 費用ゼロの平均R | 0.54ドルの平均R | 0.54ドルのPF | 決着群の損益分岐費用 |
|---|---:|---:|---:|---:|---:|
| A 継続 | 24/24 | +0.03786 | −0.01721 | 0.9670 | 0.3712ドル |
| B 反転 | 38/41 | +0.06424 | +0.02963 | 1.0796 | 1.0023ドル |

0.54ドル仮定のBは決着がある6か月のうち3か月でプラス、3か月でマイナス。未決着の3候補はM5履歴の空白による。3件の費用調整後平均が約−0.3753Rなら、41候補の合計は損益ゼロになる。この数値は感度の境界であり、欠損した取引の推定値ではない。

再現コマンドは `python orrery_gold_mtf_ab_cost_study.py PINNED_RAW_SOURCE.csv COMPLETE_BARS_DIR NEW_OUTPUT.json`。候補の確定時刻でUTC月別・時間帯別に集計し、件数と未決着IDを保持する。時間帯を選別するルールの検証には別期間が必要。実Bid/Askでの入口・出口の再判定、実費用控除後の期待値、口座利益率と最大DDは未評価。
