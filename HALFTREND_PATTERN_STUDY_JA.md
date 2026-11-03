# HalfTrendの時系列パターン研究

スクリーンショットIMG_6951.jpegを発想源に、結果算出前に以下の3候補生成経路を固定する。
画像そのものの価格/サインを履歴データとして読んだものではない。WT_Xの式は未特定で未実装。
HalfTrendは既存everget適応版、amplitude2/channel2/ATR100、確定M5のみ。
連続M5区間ごとに初期化し、休場/欠損を勝手に接続しない。

- FLIP_REFERENCE: 準備完了後のHalfTrend BUY/SELLサインを確定時に候補化する参照経路。
- PULLBACK_RESUME: 直近4足のHT方向一致＋3本前からのラインの同方向傾斜。
  ライン±0.5ATRへ接触する逆色ローソク足を観測し、その足を固定アンカーにする。
  後続6本(30分)以内にアンカー高値(BUY)/安値(SELL)を終値で更新し、ラインの順方向側で確定。
  確認時のラインからの距離は1ATR以内。アンカー極値への再接触/方向変化で失効。
- REVERSAL_CONFIRM: HTサイン時に準備し、サイン前3本の高値/安値を後続足終値で突破。
  後続6本以内、ライン順方向側、距離1ATR以内。アンカーはサイン足極値。
  初期サインと同じ足では確認成立にしない。

各経路は別集計。正式TypeA/BのH4条件を満たしたとは呼ばず、M5局所仮説として扱う。
片方の結果で逆方向へ入る戦略には転用しない。遅れて追う距離制限も1設定のみ。
各経路でSL6/アンカー構造SLを比較。TP1.5R、保有上限120分は従来と同じ。
BUYは公開Ask始値→Bid出口、SELLはBid始値→Ask出口。SELL構造SLはアンカー足Ask high。
既存paired evaluatorを再利用。両接触/欠損/無効SL/構造見送りを別保持する。
期間は第三者公開9/1〜9/25 UTCと9/26〜10/19 14:00 UTCを分離。原CSV4pinは維持。
旧研究・画像/既閲覧期間と重複するため、独立OOSではない。HalfTrend将来固定計画へ混ぜない。
新しい候補の生成数が増えても、同時保有/口座停止/費用/純利益を証明しない。
順序のある候補生成研究であり、本番採用・口座発注・配備・マージは行わない。

## 実データ計算結果

固定revisionの公開Bid/Ask4ファイルを再取得し、全hash一致。各47608本から完全M5を生成。
全ソースの候補はサイン直後307/戻り再開78/反転確認91。
評価窓外の9/25なども含む件数で、以下の期間内件数と混同しない。
未準備3470 M5観測、準備済6050観測。ATR100で早期セッションを評価できない制約がある。

|期間|経路/SL|案|決着|勝率（決着分）|平均R|PF|
|---|---|---:|---:|---:|---:|---:|
|PREVIOUS_CALENDAR_OVERLAP|FLIP_REFERENCE_FIXED_6|149|138|41.3043%|0.02693|1.04588|
|PREVIOUS_CALENDAR_OVERLAP|FLIP_REFERENCE_ANCHOR_EXTREME|149|144|40.2778%|0.00694|1.01163|
|PREVIOUS_CALENDAR_OVERLAP|PULLBACK_RESUME_FIXED_6|39|32|40.625%|0.01562|1.02632|
|PREVIOUS_CALENDAR_OVERLAP|PULLBACK_RESUME_ANCHOR_EXTREME|39|34|41.1765%|0.02941|1.05|
|PREVIOUS_CALENDAR_OVERLAP|REVERSAL_CONFIRM_FIXED_6|36|29|27.5862%|-0.31034|0.57143|
|PREVIOUS_CALENDAR_OVERLAP|REVERSAL_CONFIRM_ANCHOR_EXTREME|36|32|34.375%|-0.14062|0.78571|
|AFTER_GETDATA_WINDOW|FLIP_REFERENCE_FIXED_6|150|132|31.8182%|-0.21635|0.67643|
|AFTER_GETDATA_WINDOW|FLIP_REFERENCE_ANCHOR_EXTREME|150|145|31.7241%|-0.21037|0.69061|
|AFTER_GETDATA_WINDOW|PULLBACK_RESUME_FIXED_6|38|34|44.1176%|0.05485|1.09897|
|AFTER_GETDATA_WINDOW|PULLBACK_RESUME_ANCHOR_EXTREME|38|37|32.4324%|-0.18919|0.72|
|AFTER_GETDATA_WINDOW|REVERSAL_CONFIRM_FIXED_6|54|41|29.2683%|-0.32293|0.54345|
|AFTER_GETDATA_WINDOW|REVERSAL_CONFIRM_ANCHOR_EXTREME|54|50|20.0%|-0.5|0.375|

前半・後半とも、経路間は候補母集団が異なり、同一取引を改善した比較ではない。
サイン直後/固定SL:前半138決着+0.02693R、後半132決着-0.21635R。
戻り再開/固定SL:前半32決着+0.01562R、後半34決着+0.05485Rだが、未決着も残る。
戻り再開/構造SLの後半は37決着-0.18919R。逆方向への転用や固定SL6の自動採用はしない。
反転後確認待ちの2SL方式は両期間ともマイナス。この定義が優位とは言えない。

全ソースで戻り準備715件→アンカー無効559/距離見送り70/期限切れ4/確認78/区間末未確定4。
反転準備307件→アンカー無効90/距離見送り119/期限切れ4/確認91/区間末未確定3。
準備の失効を取引損失へ変換しない。多数の見送りはそのまま保存する。

同時保有の可能性を残すため口座リターンへ換算しない。例:後半戻り/固定SLは分時計で重なり候補7組。
既存_sequenceで決着時刻別の参考R系列を計算。未知を含む全候補DDは不明、
決着分のみのDDも口座DDではなく、同一分内順序/未決着/実リスク停止を表さない。

保存: CSV12行、全候補・発生順・状態集計・個別結果・BUY/SELL別集計をgzip JSONに保持。
`python orrery_halftrend_patterns.py ROOT NEW_OUTPUT.json` で再現。ROOTに固定4CSVを置く。
元画像の厳密再現・WT_X・H4・実手数料等は未検証。既存原計画/40ソースは無変更。

検証: 全Python1132件中1127成功・5skip・失敗0。新規11検査。
後続足の確認順、アンカー侵害の優先、追随距離、6本失効、同一flip足での確認禁止、
BUY/SELL鏡映対称性、未来追記で過去候補不変、欠損で再初期化、時刻不一致拒否、
未知結果で全候補系列を不明維持、保存hash/全12モデルの母集団会計を検査。
元の将来HalfTrend固定計画と40コードのhash検査も全体テストで成功。
