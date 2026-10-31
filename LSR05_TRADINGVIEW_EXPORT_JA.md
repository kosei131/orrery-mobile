# TradingView HalfTrend 05 診断用CSVと一括照合

2026-10-29（ハワイ）。アカウント連携・自動受信・発注は実装していない。
今回追加したPineはTradingViewで未コンパイル。テストは合成CSVと原典保持の静的検査だけ。
実TradingView CSVは未受領、実数値一致・動画との同一性・収益性は未検証。

## 公式資料から確認した方法

TradingView公式FAQは、Pineのplot値がCSVへ出力され、plotタイトルが列名になると説明している。
Data Windowだけへ出すplotも利用できる。公式ヘルプではチャート上部のメニューから
Download chart data…を選択し、読み込んだチャートデータを出力する手順が説明されている。
本手順ではCSVの表示用時刻列を推測せず、診断plotのtime/time_closeをミリ秒で取得する。

- https://www.tradingview.com/pine-script-docs/faq/indicators/
- https://www.tradingview.com/support/solutions/43000537255-how-to-export-chart-data/
- https://www.tradingview.com/pine-script-docs/concepts/time/
- https://www.tradingview.com/pine-script-docs/concepts/bar-states/
- https://www.tradingview.com/pine-script-docs/faq/techniques/

契約プラン、利用端末、CSV出力メニューの利用可否はユーザーの環境で未確認。
この工程のための有料契約やプラン変更は行わない。

## 取得する際の手順

1. Superchartsで対象フィードのXAUUSDまたはUSDJPYを開き、通常のローソク足でM5またはM15にする。
   平均足、Renko等は使用しない。銘柄の提供元も記録する。MT5と同じ価格だとは仮定しない。
2. `lsr05_tradingview_export.pine` をPine Editorへ貼り付け、保存してチャートへ追加する。
   初回にコンパイルが通るか実機確認が必要。エラー時はその内容を確認して修正する。
   この作業で公開投稿やアラート作成は不要。既存戦略・アラート設定を置き換えない。
3. Amplitudeを2/4/6/8の事前選択値、Channel Deviationを比較する値にする。
   使用コード、銘柄/フィード、時間足、入力設定、取得UTC時刻を控える。
4. Download chart data…から指標データを含むCSVを取得し、生ファイルのSHA-256を別途保持する。
   診断列INDEXの先頭が0で、以後連番である全計算履歴が必要。表示窓だけの切出しは拒否する。
   1万本を超える確定足も現APIでは拒否する。先頭を削ったりINDEXを振り直して通さない。
5. `lsr05_tradingview_import.example.json` をコピーし、未記入値と実際のCSV列名を設定する。
   生CSVと設定JSONの2つのpinを保持し、次のrunを実行する。

Pineの原典はresearch_refs/halftrendの固定版。計算部分は保持し、indicator宣言の名称/表示精度と
末尾の診断plotだけを変更したGPL-3.0翻案。原典の著作権・ライセンスは保持する。
診断plotは計算状態、ATR、チャネル、サイン、準備状態、bar_index、開始/終了時刻、
確定状態、標準チャート区分、時間足、Amplitude、Deviation、OHLC、形式版を出す。
コードを作成したことと、TradingViewで実行できたことは区別する。

## 設定JSONで明示する項目

- script_sha256: 同梱診断PineのLF正規化SHA-256。例には現在版を記入済み。
  実際に貼り付けた内容が同じか確認する。hashや診断列だけで外部実行は認証できない。
- captured_at: CSVを取得したUTC Unix秒。PCのローカル時刻文字列やミリ秒は使わない。
- missing_token: ATR未計算セルの表記を空文字、NaN、n/aのどれか1つで明示。
  選んだ表記だけをnullへ変換する。数値の0はnullへ変換しない。
- column_map: 診断20項目から実際のCSV列名への一対一対応。名前の接頭辞や言語差を推測しない。
- settings: 既存照合APIの全設定。data_source、as_of等のnullを実値で埋める。
  as_ofは照合時刻でcaptured_at以降。使用するAmplitude等はCSVの診断値と一致させる。
  休場が含まれるなら指定営業カレンダー証拠と保持pinが必要。週末等を自動推測して埋めない。

例ファイルのnullは未記入として停止させるためのもの。例をそのまま実データへ使えない。
通常モードのcalendar_evidenceとexpected_calendar_sha256だけはnullのままにする。
CSV・設定JSON各8MiB以内、列数128以内、確定足1万本以内。

## 一括実行と再検証

SHAの大文字プレースホルダーを実際の小文字64桁へ置き換える。
事前に固定した許容差を、不一致を隠すために大きくしない。

```powershell
py -3.12 lsr05_tradingview_csv.py run --csv .\export.csv --csv-sha256 CSV_RAW_SHA --config .\import.json --config-sha256 IMPORT_RAW_SHA --output .\halftrend-tv-001
```

CSV列の変換後、既存lsr05_reference_reviewへ接続して照合まで実行する。
新規フォルダーにsource.csv/import.json、生データから生成したbars.json/reference.json/settings.json、
comparisonサブフォルダーと最終complete.jsonを保存する。既存ケースは上書きしない。
出力のRECEIPT_SHA256を別途保持する。コード・Pine・設定・CSVを変更した場合は別ケースを作る。
途中失敗で残ったフォルダーを成功扱いしたり、自動修復・再開しない。

```powershell
py -3.12 lsr05_tradingview_csv.py verify --run .\halftrend-tv-001 --receipt-sha256 RETAINED_RECEIPT_SHA
```

verifyは保存CSVを再変換し、生成した入力との一致、診断コード版、nested照合のreceiptを確認し、
HalfTrend計算と全行比較も再実行する。保存結果を読むだけで成功にはしない。
元のCSV/設定ファイルを移動してもケース内コピーで検証できる。

## 失敗と未確定足の扱い

- 先頭INDEXが0でない、連番でない、重複列、必要列不足、桁不正は停止。
- 設定不一致、非標準チャート、部分足、重複/逆順、未来の確定足は停止。
- 末尾の未確定足1本だけは正式入力から除外し、除外本数・終了時刻を別記録する。
  元CSVは全行保存する。途中の未確定足、複数の未確定足、未確定足の後の行は停止。
- 古いサインへ取得時刻を遡らせない。captured_atは取得時刻であり、過去のリアルタイム観測時刻ではない。
- 不一致も有効な研究結果として保存する。終了コード0=当該サンプル一致、2=不一致/コンテキスト停止、
  1=不正入力・pin違い・実行失敗。どの終了コードも取引許可を意味しない。

同じCSVのOHLCでPythonとPine出力を比較する工程であり、MT5とのフィード一致の検査ではない。
すべての外部認証・Pineコンパイル確認・収益性・発注許可のフラグをfalseのまま維持する。
今回のテストのPine値部分はPython計算から作った合成fixtureで、独立した外部基準ではない。
実Pineのコンパイル、実CSVの列名・欠損表現・数値精度、エクスポート全履歴の取得可否は実機確認が必要。
