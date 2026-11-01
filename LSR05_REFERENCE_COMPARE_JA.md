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


## ファイルからの一括照合と保存

`lsr05_reference_review.py` を追加した。受領済み正規化JSONのファイル入力専用で、
TradingViewアカウント連携やWebhook受信は行わない。Pine/MT5の実エクスポートはまだ未受領。
CSVを自動推測して変換しない。プラットフォーム固有の変換・全計算履歴の取得は別工程。

入力はbars.json、reference.json、settings.jsonの3つ。
settingsにはschema_version=1とcompare_referenceの次の全引数を保存する。
symbol / data_source / as_of / interval / amplitude / channel_deviation /
absolute_tolerance / calendar_evidence / expected_calendar_sha256。
通常モードでは後ろ2つをnullにする。未記入の設定は既定値で埋めず停止する。
入力はUTF-8 JSON、各8MiB以内。重複キー、NaN、無限大を拒否する。

入力ファイル受領時に、各ファイルの**生バイトSHA-256**を別途控える。
Windows PowerShellでは `Get-FileHash -Algorithm SHA256 -LiteralPath .\reference.json` 等で確認し、
出力を小文字にする。reference_sha256関数のcanonical JSON hashとは別なので混用しない。
照合時に3つの生バイトpinを明示し、後から置換された入力を拒否する。
これは受領以降の変更検出であり、受領した資料の出所の真正性を証明しない。

次のコマンドは入力準備後に使う形式例。大文字のSHA部分を実際の小文字64桁へ置き換え、
未作成の保存フォルダーを指定する。コードは対象の最新コミットを展開した場所で実行する。

```powershell
py -3.12 lsr05_reference_review.py run --bars .\bars.json --bars-sha256 BARS_RAW_SHA --reference .\reference.json --reference-raw-sha256 REFERENCE_RAW_SHA --settings .\settings.json --settings-sha256 SETTINGS_RAW_SHA --output .\halftrend-review-001
```

保存内容は入力3ファイルの生バイトコピー、result.json、最後に書くcomplete.json。
入力と結果のサイズ/hash、主要7モジュールのLF正規化コードhash、判定状態を記録する。
入力ファイルの絶対パスは保存しない。秘密・口座情報を入力に含めない。
標準出力にもパスやOHLC等を出さず、状態とRECEIPT_SHA256を表示する。
このreceiptのpinを別途保管する。既存フォルダーは上書きせず、途中失敗も自動再開しない。

```powershell
py -3.12 lsr05_reference_review.py verify --run .\halftrend-review-001 --receipt-sha256 RETAINED_RECEIPT_SHA
```

verifyは全ファイルを再読込し、pin・構成・コード版を検査してローカル計算と全行照合を再実行する。
保存した結果の読取りだけで成功にはしない。元の入力3ファイルを移動しても、保存コピーから再検証できる。
コードが変わった場合は停止するため、当時のコード・pin・元エクスポートも保持する。
コードhashは実行環境や外部プラットフォームでの実行の証明ではない。

終了コード：0=当該サンプルの値が一致、2=有効な不一致/コンテキスト停止を保存または再検証、
1=不正入力・pin違い・保存不全・コード変更等で実行失敗。0でも外部一致の正式認証や取引許可はない。
失敗した出力フォルダーは削除や補修を自動で行わず、別の新規名で再実行する。
同時利用者からの悪意あるファイル差替えを防ぐOS隔離を提供する機能ではなく、専用ローカル研究用途。

診断用PineからのCSV取込・一括照合手順を追加した（LSR05_TRADINGVIEW_EXPORT_JA.md）。実プラットフォームでのコンパイル・CSV受領は未確認。
