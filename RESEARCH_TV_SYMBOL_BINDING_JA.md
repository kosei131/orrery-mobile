# TradingView CSVとBid/Ask履歴の銘柄固定（2026-11-01）

基準: fix/fx-safety-verification / cb21d887bebeed1c69ba8cab54070c93e26fe758。
GitHubの全PR一覧を確認し、既存PRは#1のみ。今回の独立研究変更と重複する研究PRはない。
基準コミットのActions 41293388725 / 41293385343は成功。

## 事前の検査条件

CSV設定の銘柄とピン留めBid/Askカタログの銘柄が一致しなければ、
口座候補作成・USD評価関数の呼出し前に拒否する。
一致する入力のEntry/SL/TP、ロット、取引、残高、停止条件を変えない。
これはデータ結合の不具合検査で、期待値向上の売買仮説ではない。

## 修正前に再現した事実

test_tradingview_studyの合成OHLC・合成XAUUSDカタログを使い、
settings.symbolだけをUSDJPYにしてstudy(..., account_inputs=...)を呼んだ。
studyのsymbolはUSDJPY、modelled_accounts.symbolはXAUUSDのまま、
TRADINGVIEW_BARS_ACCOUNT_MODEL_RESEARCHとして口座結果が返った。
いずれも合成価格であり、USDJPY/XAUUSDの実市場損益ではない。
新規の不一致回帰テストが修正前には失敗することを確認した。

原因は、CSV設定のsymbolを下位compare_catalog_accountsに渡していなかったこと。
下位関数がカタログのsymbolで候補を再生成し、上位で付いた銘柄名との不一致を検査していなかった。

## 修正

- compare_catalog_accountsに明示的なexpected_symbolを追加。
- 指定値はXAUUSD/USDJPYのみ。カタログの銘柄と不一致なら、候補作成とUSD評価前にValueError。
- TradingView入口はsettings.symbolを必ず渡し、account_inputsからの上書きも拒否。
- 実行条件を記録するconfigにexpected_symbolを含める。
- 既存の下位API呼出しとの互換性のためNone既定値は維持する。
  Noneの直接呼出しには今回の銘柄照合を保証しない。TradingView入口ではNoneにならない。

## 検証範囲と判断

5件の回帰テストを追加した。合成USDJPY設定×XAUUSD履歴の拒否、上書き拒否、
合成USDJPY履歴×XAUUSD指定の拒否、USDJPY一致時の候補生成、XAUUSD一致時の
既存口座・候補結果との同一性、無効銘柄のカタログ読込前拒否を含む。
不一致時はUSD評価関数が呼ばれず、下位APIでは候補コンパイラも呼ばれないことを検査する。
一致例でもexecution_allowed=Falseを維持する。

実行済み: python -m unittest test_tradingview_study test_lsr03_account_study -q は30件成功。
python -m unittest discover -q は872件中867件成功、環境依存の5件スキップ、失敗なし。
git diff --checkも成功。CIは研究ブランチに保存後、別途確認する。

この変更は不一致の口座比較を止めるためのレビュー候補。売買戦略の採用・変更ではない。
計画リスク0.25%、日次損失1%、合計SL上限1%、3連敗停止、日次境界10:00 UTCは変更していない。
既存lsr03_trade_learning/lsr03_learning_rollupは調査したが、不正な銘柄結合結果を学習入力に
流さないことを先に修正した。新しい勝敗分析やパラメータ調整は実施していない。

## 収益性評価は保留

対象はTradingView入口のLSR02/VHF03比較だけ。Reversal04/HalfTrend05/未定義2.6は未統合。
ユーザーPC保存の標準M5/M15/H4 CSV本体・設定・取得時点がこちらに未提供。
同一提供元・同一銘柄・同期間の検査済みBid/Ask履歴、履歴USD評価、ロット仕様、
手数料・滑り・日跨ぎ費用も未取得である。
そのため未使用期間の期待値・利益率・PF・最大DD・取引数は未計算（0とはしない）。
6か月セッション対応、未使用期間比較、注文承認固定、約定照合も完了とは呼ばない。

次はCSVとカタログを受領して今回の銘柄固定に加え、期間・時間足整合性・セッションの
照合を行う。その後に固定条件で開発期間と未使用期間を分けて口座比較する。
PC/MT5/Dotsの操作・接続、MT5への注文送信、基準ブランチへのマージ・配備は実施しない。
