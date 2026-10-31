# Read-only DEMO capture to account estimate

This connects the existing MT5 historical pilot bundle to the existing
confirmation/retest account comparison, using actual archived Bid/Ask rather
than fabricated M1 ticks. It is a research command, not a trading EA.
No login/password input, order placement, stop modification or live account
access is implemented. No new real-market performance has been observed here.

## Explicit valuation boundary

MetaQuotes documents `order_calc_profit` as a calculation in the CURRENT
account/current trading environment, returning account currency:
https://www.mql5.com/en/docs/python_metatrader5/mt5ordercalcprofit_py
https://www.mql5.com/en/docs/python_metatrader5/mt5symbolinfo_py

Therefore this runner is restricted to canonical XAUUSD, a USD DEMO account,
and currency_profit=USD. It calls the broker calculator rather than guessing
contract value or currency conversion. It still does NOT establish that
historical contract/quantity conditions equal today's snapshot. USDJPY is
blocked pending historical conversion evidence; current conversion rates
are not substituted. Report labels are CURRENT-SPEC ESTIMATES, never verified
historical broker performance. Margin/liquidation and real slippage remain
unmodeled. A zero-trade result is not evidence of profit.

## Windows workflow

1. Use the same already logged-in broker DEMO terminal for both commands.
2. Capture a short continuous segment with the existing read-only
   `lsr03_mt5_pilot.py` workflow. New captures save an account-scope digest
   and a complete optional volume/profit-currency/calc-mode snapshot.
3. Independently retain the printed `run_sha256` from capture.
4. Copy `account_pilot_settings.example.json` to a local settings file. Fill
   USD PER LOT round-trip costs, adverse PRICE-UNIT slippage, and source labels.
   These differ from the original pilot's PRICE-PER-UNIT comparison costs.
   Missing/null values block; explicit zero is a documented assumption, not
   verified free execution. The example stop/target are research hypotheses.
5. Confirm the whole capture avoids the broker's rollover/funding charge
   interval and document that source. The runner requires the explicit
   `no_carry_interval_confirmed=true` assertion; it cannot certify that claim.
   The interval must also stay within one Hawaii risk day. Otherwise use a
   historical carry/boundary integration; do not silently set swap to zero.
6. Run with a NEW output directory and the actual terminal path:

```powershell
python lsr03_mt5_account_pilot.py --pilot orrery_pilot_001 --pilot-run-sha256 CAPTURE_RUN_SHA256 --config account_pilot_settings.local.json --output orrery_account_001 --terminal-path "C:\Program Files\MetaTrader 5\terminal64.exe"
```

The command needs Windows MT5 and its official Python package. This development
environment has not connected to the user's terminal or Funded7. The capture launcher remains unchanged. The account command can also be started
with the guided launcher described below.

## Evidence and checks

`verify_pilot_bundle` validates the independently retained run hash and exact
fixed-name settings/bars/report hashes using bounded reads. The catalog pin
from that marker goes through the existing global tick-quality loader.
The source label must match. Hash verification proves local consistency
relative to a pin, not that a broker or user-provided fee claim is genuine.
Runs lacking the new capture scope/spec metadata are blocked; recapture rather
than guess the account. Raw login/server are not saved. The scope digest is a
comparison token, not anonymization or a credential-security mechanism.

Current account identity and full relevant spec must equal the captured scope
and snapshot. They are rechecked before/after every profit calculation and
before completion. Failed/nonfinite broker results, budget exhaustion, live
or switched accounts and changed volume specs stop without a completed account
marker. Profit calls are explicitly bounded (<=20000). No fallback linear
valuation or guessed exchange rate is used. The read-only call is
`order_calc_profit`, NOT `order_send` or `order_check`.

Native captured M15/M5 bars go through the same sequence logic as the public
research, now factored into `report_from_bars`. Existing file-based results
remain unchanged. The signal filter remains the original exploratory VHF
14 / >=0.4 rising, not a newly optimized parameter set or Kou replication.
The account cohort is explicitly the captured tick horizon, so October or
other pilot dates are not silently excluded by the older April-September
research window. Public research defaults retain their original bounds.

Both account modes use known M5 CLOSE-based fixed-distance stop/TP, strictly
post-close quote eligibility, single active position, initial $3000,
0.25% entry risk, existing daily 1% and three-loss stops, and observed-quote
holding limits. This differs from the older fill-anchored public-M1 benchmark.
The command does not add pyramiding, partial exits, multiple simultaneous
positions or formal Type A/B adoption. OPEN positions and insufficient data
stay distinct. A short capture can legitimately produce zero candidates.

## Outputs

The exclusive new directory contains:

- account_settings.json: explicit account-cost and no-rollover assertions;
- sequence.json: causal confirmations and separate retest observations;
- account_report.json: two independent research accounts or quality-blocked result;
- account_run.json: completion marker written last with file hashes/input pins.

Failures may leave a partial directory, never overwrite or implicitly resume.
The source bundle is rechecked before writing results. These sampled checks
are not an atomic terminal/filesystem transaction. Exit 0 means a modeled
research report, not trading success; exit 2 is global-quality blocked; exit 1
is sanitized capture/valuation/configuration failure. All reports keep orders
disabled, market_edge_verified=False and historical_broker_conditions_verified=False.
The caller's costs/no-rollover assertion and bar/tick lineage are not certified.

## Validation

Injected fake-DEMO tests run capture -> archive/catalog hashes -> source
sequence -> existing accounts -> exclusive completion marker. They also test
account/spec changes, missing costs/carry assertions, tampered capture files,
missing identity metadata, calculation failure, call budgets, unsupported
conversion, read-only calls and identifier omission. These are synthetic API
tests, not an actual Windows/broker run. Actual connection, broker history,
calibrated costs and the first real quote-based account comparison remain open.


## Windowsで最初の比較を実行する手順

この開発環境から利用者のWindows MT5へ接続することはできません。
ここから必要なのは追加のインジケーターではなく、端末上での実データ実行です。

1. 最新の研究ブランチをWindowsへ取得し、同じUSD建てDEMO口座をMT5で開きます。
   Pythonと公式MetaTrader5パッケージが必要です。
2. まだ新形式の取得データがなければ `START_REAL_MT5_PILOT.cmd` で短い
   XAUUSD履歴を取得し、成功時に表示された `run_sha256` を別に保存します。
   後から同じフォルダーを読み直して作ったハッシュで代用しません。
3. `account_pilot_settings.example.json` を別名のローカルJSONへコピーします。
   手数料の往復USD/lot、スリッページの価格単位、根拠を入力します。
   対象期間がブローカーのロールオーバーをまたがないことを確認し、
   根拠と `no_carry_interval_confirmed=true` を設定します。
   不明な費用を0で埋めたり、未確認の項目をtrueにしたりしません。
   同一ハワイ日次区間の条件も必要です。
4. `START_MT5_ACCOUNT_COMPARISON.cmd` をダブルクリックし、取得フォルダー、
   別途保存したハッシュ、設定JSON、MT5実行ファイル、新しい出力名を入力します。
   既存出力は上書きしません。コスト未設定・ハッシュ不一致は端末起動前に停止します。
5. 成功後の `account_report.json` と `account_run.json` を確認します。
   元の取得データ・ハッシュ・設定と一緒に保存します。候補ゼロや未決済は
   利益実績として扱いません。終了コード2は品質停止、1は実行失敗です。

ランチャーは配列引数で既存エンジンを起動し、評価ロジックは複製しません。
実口座へのログインや発注処理はありません。画面に口座IDやパスワードを入力する
必要はありません。ランチャーテストは模擬起動であり、実端末の接続証明ではありません。
この短期間の比較が実行できても、6か月検証や利益優位性の確認は別工程です。
