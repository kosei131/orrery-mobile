# HalfTrend 05 外部出力照合の準備

2026-10-29（ハワイ）。研究API。今回のテスト入力は合成データであり、実TradingView/MT5出力ではない。
既存の計算・観測・リスク・戦略・発注設定を変更しない。実データの数値一致は未確認。

## 用途

`lsr05_reference_compare.compare_reference` は同じ開始点、全OHLC、設定、銘柄、
データ元、任意カレンダーを固定してローカル計算を再実行し、外部から受領した出力全行を比較する。
非表示の先行履歴を計算した後の表示窓だけを比較対象へ渡さない。
開始点が異なる場合、計算状態とATRの種が異なるためコンテキスト不一致として停止する。
外部プラットフォームの内部履歴が同じだったことは入力ラベルだけでは証明できない。

返却する差分は状態、ライン、ATR、上下チャネル、サイン、準備状態。
時刻は厳密一致で、都合のよい時間ずらし、直近値の補完、内側結合による欠損の除外をしない。
欠落行・余剰行・値の差を別集計する。全件数を数え、差分例は100件まで。
比較前に指定する価格の絶対許容差は0〜0.01。価格以外へは適用しない。
相対誤差を使わず、高い価格水準による許容差の拡大を避ける。
実照合時は出力桁数・銘柄の価格単位から許容差を事前に固定し、差を消すために調整しない。
ATR未計算のnullと0は異なる値として扱う。

## 受領する正規化JSONの形式

schema_version=1。必須キーは次の通り。

- platform: TRADINGVIEW または MT5
- implementation_label: 使用実装・版の説明
- implementation_sha256: 実際に使用した参照コードのハッシュ
- source_sha256: 今回固定したeverget原典のSHA-256
- symbol: XAUUSD または USDJPY
- data_source: ブローカー・フィードを識別する説明
- captured_at: エクスポートを取得したUTC Unix秒。最後の確定足以降、照合時刻以前
- interval / amplitude / channel_deviation: 300または900 / 2,4,6,8 / 設定値
- calendar_sha256: 通常モードはnull。任意カレンダーモードは使用証拠のcanonical JSON SHA
- bars: 計算開始から終わりまでの確定OHLC全件。close_time/open/high/low/close
- rows: 同期間の全出力。at/state/line/atr/atr_high/atr_low/signal/ready

時刻は足の開始時刻ではなくUTCの終了時刻。stateはUP/DOWN、signalはBUY/SELL/null、
readyは真偽値、未計算ATRとチャネルはnull。価格・時刻に真偽値、NaN、無限大は使えない。
全件が準備済みになる前の履歴も含める。上限1万本。

`reference_sha256` は受領したJSONをcanonical化したSHAであり、生CSV等のバイトハッシュではない。
受領時に別途保持したpinを `expected_reference_sha256` へ渡す。
評価時に同じデータからpinを作るだけでは、過去に受領した内容の置換を検出できない。
元エクスポート、元コード、変換規則、取得時刻の資料も別途保持して検査する必要がある。
本APIはファイル保存、CSV変換、Pineコード実行、MT5への接続を行わない。

```python
from lsr05_reference_compare import compare_reference
report = compare_reference(
    closed_bars, received_reference,
    expected_reference_sha256=retained_reference_pin,
    symbol='XAUUSD', data_source='documented_feed', as_of=comparison_time,
    interval=900, amplitude=2, channel_deviation=2,
    absolute_tolerance=0.000001,
)
```

任意カレンダー利用時はcalculateと同じcalendar_evidenceとexpected_calendar_sha256を渡す。
カレンダー違いを無視して比較しない。営業中欠損等でローカル計算が停止した場合も評価を進めない。

## 結果と限界

- BLOCKED_REFERENCE_CONTEXT: 銘柄、設定、元データ、原典版等が違うか、履歴不足/時間監査で停止。
- REFERENCE_MISMATCH: 欠落・余剰・値の不一致あり。空の外部出力も一致扱いしない。
- REFERENCE_SAMPLE_MATCHED_NOT_VERIFIED: 指定全期間の値が一致しただけ。

platformやコードハッシュは受領側の申告情報であり、本APIは真正性を認証しない。
一致してもindependent_reference_verified / tradingview_parity_verified / mt5_parity_verified /
nonrepainting_verified / market_edge_verified / execution_allowedはすべてfalse。
実外部出力を受領し出所と履歴を検証する工程、リアルタイム観測、実コスト付き損益比較が別途必要。

テストの一致用fixtureはローカル計算結果から作った合成入力で、検査器自体の動作確認専用。
外部基準との一致や独立した正解系列として報告しない。
