# 第三者公開Bid/Ask系列の別検証

取得元: kevingtlin/Market-Data-Lab、固定revision b60bd71d0e34a42cb962daf688ff252e73f409ca。
Dukascopy由来という公開者申告。直接配信元認証/ユーザーMT5約定ではない。
2025-01の自然月全分ファイルに長い同値平坦列を確認し、損益研究へ使用しない。
更新記録の処理説明がある2026-09/10を別系列として取得。GetDataへ混合・補修しない。
9/1〜9/25 UTCと、9/26〜10/19 14:00 UTCを別集計。間の9/25は境界分離用に評価しない。
前半は旧期間とのfeed差の記述、後半はGetData窓後だが既存TradingView探索との期間重複がある。
独立未使用OOSを証明したとは呼ばない。HalfTrendの11/3固定計画には入れない。

結果計算前の条件: 既存因果的sweep→確認/VHF経路、ALL/VHF_PASS、即時/Retest60分、
固定SL6/構造SL、TP1.5R、保有120分の8モデル。新たな最適化なし。H4なしの探索。
Bidの完全M5/M15から候補を作成。両側CSVは時刻重複/逆順/不正OHLCを拒否し、
片側だけの時刻は補完しない。欠損前の決着は保持、未決着は不明。
BUYはAsk始値→Bidで出口、SELLはBid始値→Askで出口。
構造SL: BUYは確定sweepのBid low、SELLは対応Ask high。entry前の構造無効は見送り。
これは旧mid+固定spreadと同じSL式ではないため、成績を合算しない。
同一足のTP/SL両接触は主結果で曖昧としてR未確定、stop-first値は別の感度値。
未決着・欠損・無効SL・無エントリーを0R取引へ変換しない。
取引単位価格参照Rのみ。手数料/滑り/swap/口座リスク停止/証拠金未評価、口座利益率null。

## 取得・監査・モデル損益の実行結果

2026-09:各30208本、10月:各17400本、計各47608本。Bid/Askの分時刻差分0。
同月の時刻・OHLC検査と4ファイルSHA256を固定し、新品の出力へ再実行。
長い同値平坦列は9/10月で0、2025年1月で2945分（48時間超）あり、後者は不使用。
終値差の最小約0.10/中央値0.62/最大7.69価格単位。ただし同期tickのspreadではない。

### PREVIOUS_CALENDAR_OVERLAP

UTC 2026-09-01T00:00:00+00:00 ～ 2026-09-25T00:00:00+00:00

|モデル|確認母集団|取引案|決着|プラス|勝率（決着分）|平均R（決着分）|PF|未評価/見送り状態|
|---|---:|---:|---:|---:|---:|---:|---:|---|
|ALL_CONFIRMATION_FIXED_6|27|27|27|9|33.3333%|-0.16667|0.75|{}|
|ALL_CONFIRMATION_SWEEP_EXTREME|27|27|17|8|47.0588%|0.17183|1.49049|{'STRUCTURE_BREACHED_BEFORE_ENTRY': 10}|
|ALL_RETEST_FIXED_6|27|18|18|4|22.2222%|-0.44444|0.42857|{}|
|ALL_RETEST_SWEEP_EXTREME|27|18|11|4|36.3636%|-0.06727|0.86554|{'STRUCTURE_BREACHED_BEFORE_ENTRY': 7}|
|VHF_PASS_CONFIRMATION_FIXED_6|8|8|8|3|37.5%|-0.0625|0.9|{}|
|VHF_PASS_CONFIRMATION_SWEEP_EXTREME|8|8|5|3|60.0%|0.26071|2.03059|{'STRUCTURE_BREACHED_BEFORE_ENTRY': 3}|
|VHF_PASS_RETEST_FIXED_6|8|4|4|0|0.0%|-1.0|0.0|{}|
|VHF_PASS_RETEST_SWEEP_EXTREME|8|4|1|0|0.0%|-1.0|0.0|{'STRUCTURE_BREACHED_BEFORE_ENTRY': 3}|

### AFTER_GETDATA_WINDOW

UTC 2026-09-26T00:00:00+00:00 ～ 2026-10-19T14:00:00+00:00

|モデル|確認母集団|取引案|決着|プラス|勝率（決着分）|平均R（決着分）|PF|未評価/見送り状態|
|---|---:|---:|---:|---:|---:|---:|---:|---|
|ALL_CONFIRMATION_FIXED_6|11|11|11|5|45.4545%|0.13636|1.25|{}|
|ALL_CONFIRMATION_SWEEP_EXTREME|11|11|3|1|33.3333%|-0.13708|0.75453|{'STRUCTURE_BREACHED_BEFORE_ENTRY': 7, 'CENSORED_AT_SIDE_GAP': 1}|
|ALL_RETEST_FIXED_6|11|6|5|2|40.0%|0.0|1.0|{'CENSORED_AT_SIDE_GAP': 1}|
|ALL_RETEST_SWEEP_EXTREME|11|6|2|0|0.0%|-0.82561|0.0|{'STRUCTURE_BREACHED_BEFORE_ENTRY': 3, 'CENSORED_AT_SIDE_GAP': 1}|
|VHF_PASS_CONFIRMATION_FIXED_6|2|2|2|0|0.0%|-1.0|0.0|{}|
|VHF_PASS_CONFIRMATION_SWEEP_EXTREME|2|2|1|0|0.0%|-0.67531|0.0|{'STRUCTURE_BREACHED_BEFORE_ENTRY': 1}|
|VHF_PASS_RETEST_FIXED_6|2|2|2|1|50.0%|0.25|1.5|{}|
|VHF_PASS_RETEST_SWEEP_EXTREME|2|2|1|0|0.0%|-0.65122|0.0|{'STRUCTURE_BREACHED_BEFORE_ENTRY': 1}|

後半は11確認/VHF2。VHF即時固定SLは2損失、構造SLは1決着-0.67531R/構造見送り1。
VHF Retest固定SLは2決着/1プラス/+0.25Rだが、2件から採用しない。
全確認即時固定SLは11決着/5プラス/+0.13636R/PF1.25。旧期間27決着では平均-0.16667Rで不安定。
Bid側構造候補と観測Ask側のSL基準は旧mid+仮定spreadと異なる。旧成績との合算は禁止。
手数料/追加滑り/swap/証拠金/口座停止は未評価。少数決着から実収益を主張しない。

再現: 固定revisionの4CSVをROOT/bid_2026_09.csv等へ保存し、
`python orrery_paired_archive_study.py ROOT NEW_RESULT.json`。
CSVはGitHubへ再配布せず、hash/URL/監査/個別モデル結果のみ保存。

検証: 全Python1111件中1106成功・5skip・失敗0。追加10検査。
BUY Ask入口/Bid出口、SELL Ask出口、両接触を未確定、欠損前決着保持、
始値gapで-1R超損失、構造無効/片側欠損、未来構造clock拒否、無効SL、
CSV重複/平坦列、実16モデルの母集団会計を確認。固定hashでの再実行は初回と全結果一致。
原LSR/HalfTrend固定40ファイルは変更なし。独立holdout/収益性を証明しない。
