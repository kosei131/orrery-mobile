# インジケーター単独追加の候補群比較

## 比較条件（結果算出前に記録）

対象は既存の全確認/VHF通過、即時/Retest、固定SL/構造SLの8モデル。
GetDataの既閲覧5か月と第三者Bid/Askの2期間を分離し、24モデル×7フィルター=168比較。
シグナル・入口・SL/TP・保有時間は変更せず、同じ取引案をPASS/FAIL/UNKNOWNに分割する。
各フィルターは単独。閾値探索・組合せ・最良モデルの自動採用はしない。
期間は既閲覧で独立未使用検証ではない。多重比較で偶然の改善があり得る。

全特徴はエントリーを決める確定M5の終値時点まで。連続した直近最大300本のみ。
欠損で履歴を切り、最新確定足がentry時刻と一致しなければUNKNOWN。
EMAはその連続窓のSMA seed、MACD signalもSMA seed。プラットフォーム完全一致は未証明。

1. EMA20/50: BUYはEMA20>EMA50、SELLは逆。
2. ADX14: 25以上（強さのみ、方向は決めない）。既存diagnosticsを再利用。
3. MACD12/26/9: BUYはhistogram>0、SELLは<0。
4. 一目9/26/52: 現在価格が現在位置の雲の上(BUY)/下(SELL)。
   雲は厳密に26本前の計算値を使う研究定義。現在算出の先行spanを現在雲に流用しない。
   遅行spanを未来の価格と照合しない。外部描画とのoffset parityは未検証。
5. Bollinger20/2σ: BUY終値>上バンド、SELL終値<下バンド。標準偏差は母分散。
6. Donchian20: 最新足を除く直前20本の高値/安値を終値で突破、方向一致。
7. ATR14: 最新ATRが直前20個のATR平均より大きい（方向ではなく変動拡大）。

機会・決着・未決着/曖昧/構造見送り・履歴不足を群ごとに保持。
FAIL群の既知利益R合計=取り逃した価格利益、既知損失R絶対値=回避する価格損失の参考値。
UNKNOWN群を都合よくPASS/FAILへ入れない。口座の損失回避や純損益とは呼ばない。
GetDataの元証拠は構造見送りと履歴不足の個別clockがないため、未決着と見送りを
UNMODELED_OR_SKIPPEDへ一括記録する。元の集計理由は別保持。0R取引に変換しない。
元データ/証拠/特徴時刻/hashを固定し、baselineの個別決着と全件数の一致を検査する。

参照: TradingView公式のMACD、Ichimoku、Bollinger説明。
https://www.tradingview.com/support/solutions/43000502344-moving-average-convergence-divergence-macd-indicator/
https://www.tradingview.com/support/solutions/43000589152-ichimoku-cloud/
https://jp.tradingview.com/support/solutions/43000501840/

## 実データ評価結果

既存個別価格モデルを再利用し、入口判断時までの実確定M5から特徴を計算して再集計。
24モデルのbaseline決着数は一致。第三者系列は全baseline集計も完全一致。
7指標×24モデル=168比較は互いに独立した168回の検証という意味ではない。

### 事前に定めた全確認・即時・固定SLの3系列比較

各セルはPASS決着件数/決着分平均R。履歴UNKNOWNは別集計、完全CSV参照。

|単独フィルター|GetData5か月|Bid/Ask前半|Bid/Ask後半|
|---|---:|---:|---:|
|EMA20_50_DIRECTION|28 / -0.10714|9 / -0.44444|1 / 1.5|
|ADX14_GE25|31 / 0.12903|9 / 0.11111|4 / -0.375|
|MACD12_26_9_HISTOGRAM|79 / -0.01899|23 / -0.13043|8 / -0.0625|
|ICHIMOKU9_26_52_CURRENT_CLOUD|31 / -0.1129|7 / -0.28571|2 / 1.5|
|BB20_2_BREAKOUT|27 / -0.25926|10 / -0.25|3 / 0.66667|
|DONCHIAN20_BREAKOUT|28 / -0.375|7 / -0.28571|3 / 0.66667|
|ATR14_EXPANSION|53 / -0.15094|11 / 0.36364|5 / 0.0|

Baseline全決着平均Rは順に-0.08316/-0.16667/+0.13636R。
UNKNOWNの有無で見かけ上改善し得るため、各指標のPASS+FAILのみのevaluable baselineも別保存。
ADXは旧期間で改善傾向だが後半4決着で-0.375R。VHF+ADXは旧11決着/勝率72.73%/平均+0.81818R/PF4だが、
後半は1決着/-1Rで再現を確認できない。小標本・多数試行の良い数字を自動採用しない。
EMA/雲の方向一致は候補を大きく削る。旧VHF群のEMA通過は1決着で-1R。
BB/Donchianの後半3決着/+0.66667Rも小標本で、旧期は平均マイナス。
この定義での単独追加の結果であり、各指標全般の有効/無効を断定しない。

## 保存・再現

全168行CSV、全特徴/三群集計を含むgzip JSONとhash manifestをresearch_evidenceへ保存。
圧縮前後のhashを検査してから読む。データは既存固定CSVで、研究エンジン・原計画は変更なし。
`python orrery_indicator_ablation.py GETDATA_ROOT PAIRED_ROOT NEW_OUTPUT.json`
JSON解凍はPythonのgzip.decompress/readで可能。指標はSMA seed/最大300本の研究定義で、
外部チャート一致・実口座利益率・純期待値・DDは未確認。自動売買/採用/配備なし。

検証: 全Python1121件中1116成功・5skip・失敗0。新規10検査。
EMA seed、将来追記不変、26本前の雲、欠損リセット、平坦列の偽シグナル防止、
MACD方向、Donchian最新足除外、ATR過去平均、三群と元母集団/hashの一致を検査。
Windowsのautocrlf=true checkoutでもCSV/gzip/manifestのバイト一致を検査した。
*.csvを検査時に改行修復して通さず、対象CSVのみ.gitattributesでバイト保存に固定。
テスト成功はインジケーター採用や収益性の証明ではない。
