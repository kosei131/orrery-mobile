# HalfTrend Structure Confirmation 05 — 第1工程

実装日：2026-10-29（ハワイ）。独立した研究候補。正式採用/発注/実市場の利益証明ではない。
既存LSR-01/02/VHF03/Reversal04/2.6・SL・ロット・口座停止設定は変更しない。

## 固定した参照実装

作者：Alex Orekhov (everget)。GitHub公開Pine v6。
repository: everget/tradingview-pinescript-indicators
revision: 8385cc421888bbf31f36407195796bc0eabafb19
path: trailing_stops/halftrend.pine
raw SHA-256: efa1915b4d0812d8126bd27c7667f9408e90aeed94988058b1b1edeaa23f4a3c

原典・出所情報・GPL-3.0全文をresearch_refs/halftrendへ保存した。
Python翻案lsr05_halftrend.pyとそのテストにもGPL-3.0の表示を付ける。
既存ファイル全体のライセンスを変更するものではない。現段階では標準ライブラリだけを使う
独立研究モジュールで、既存アプリからimport/組込みは行っていない。
将来の組込み・再配布時にも原典と翻案の利用条件を確認する。

参照URL：
https://github.com/everget/tradingview-pinescript-indicators/blob/8385cc421888bbf31f36407195796bc0eabafb19/trailing_stops/halftrend.pine
https://www.tradingview.com/script/U1SJ8ubc-HalfTrend-everget/

動画の表示インジケーターとこの版が同一であることは未確認。
TradingView公開ページの当時の版と、今回固定したGitHub版の完全一致も未確認。

## 仕様で明確にする点

- Amplitudeは高安の窓とSMAの長さ。比較候補は2/4/6/8だけに限定。
- 転換は状態を保持した高安/SMAと前足高安・終値による。単純な価格クロスではない。
- チャネル半幅はChannel Deviation × ATR(100) / 2。
- Channel Deviationは原典の転換条件へ入らない。チャネル幅を広げて転換数が変わる実装にはしない。
- 原典はATRが未計算の間、転換内部状態が変わっても公開BUY/SELL条件を満たさない。
- 初期trend=0のUPは履歴開始時の種であり、4H上昇環境が証明された意味ではない。
- 原典のalertconditionにはbarstate.isconfirmed条件がない。ORRERY入口で確定足だけを受け付ける。
- VHFは方向を持たない。SELLにマイナスVHF等の条件は作らず、方向は価格構造とHalfTrendで扱う。

TradingViewの実行モデルでは、未確定足の更新で状態が再計算/rollbackされる。
確定足だけを使うことと、後日の価格訂正・異なる履歴開始点でも値が不変なことは別。
https://www.tradingview.com/pine-script-docs/language/execution-model/

## 今回実装した範囲

```python
from lsr05_halftrend import calculate, compare_amplitudes
result = calculate(closed_bars, as_of=known_time, interval=300,
                   amplitude=2, channel_deviation=2, enabled=True)
grid = compare_amplitudes(closed_bars, as_of=known_time, interval=300)
```

calculateの初期値はenabled=False。既存戦略への追加を自動で有効にしない。
入力はclose_time/open/high/low/closeの確定OHLC、M5=300秒またはM15=900秒。
未来・未確定フラグ・重複・逆順・間隔欠損・不正OHLCは停止する。
上限1万本。週末や保守時間を暗黙に埋めたり、欠損を跨いで連続として扱わない。
4Hの既存環境分析はそのまま使い、今回のHalfTrend入力対象へは追加しない。

状態線、ATR、上下チャネル、転換内部状態、確定足BUY/SELL、成立時刻と終値を返す。
終値はサイン価格の観測値であり、その価格で約定できたことを意味しない。
ATR100本未満はINSUFFICIENT_HISTORY。内部状態/線は診断用に返すが正式サインは出さない。
ATRは最初のTR100本のSMAで初期化し、その後Wilder型RMAで更新する。
履歴開始点は状態の初期値とATRへ影響する。100本あればTradingViewと一致するとは保証しない。

compare_amplitudesは4設定を別々に計算するだけで、最良設定や勝率を選ばない。
入力ハッシュ、参照ソース版、設定、履歴開始/終了を記録する。
tradingview_parity_verified / mt5_parity_verified / nonrepainting_verified /
market_edge_verified / execution_allowedは全てfalse。

## 工程の実装状況

| 対象 | 状況 |
| --- | --- |
| 状態エンジン/確定足転換/ATRチャネル | 今回のPython研究実装 |
| Amplitude 2/4/6/8 | 計算比較まで。利益感度比較は未実施 |
| リペイント検査 | 同じ履歴への未来足追加で過去出力が不変という合成検査まで |
| 実観測の変更記録 | 既存SignalJournalを再利用する接続は未実装 |
| 03/04とのas-of照合、方向整合 | 未実装。候補時点より後のサインを採用しない設計で次工程 |
| レンジ連続転換フィルター | 未実装。停止閾値を過去成績へ合わせて作らない |
| HalfTrendトレーリング | 未実装。構造SL方式と別に比較する |
| TradingView/MT5相互照合 | 未実施。MT5 EA/インジケーターは作成していない |
| A/B/C/D/Eの同一条件収益比較 | 未実施。04の観測不足ならC/Dは評価不能 |

次は同じ開始点・OHLC・設定でのTradingView出力照合と、既存の確定サイン観測記録への接続。
外部の正解系列がない間は、手計算例とprefix検査を相互一致の証明に代用しない。
Pythonテスト成功だけで不リペイントや元動画の再現成功とは報告しない。

比較時は既存LSR-VHF03を固定したA、05追加B、04追加C、両方D、05単独Eを分離する。
Amplitude選別と出口最適化を同じ既知標本で同時に行わず、試した設定数を保存する。
HalfTrend単独Eにも入口/SL/TP/費用/停止条件の事前定義が必要で、矢印だけでは損益を算出しない。
改善しない場合に不採用にできる独立構成を維持する。
