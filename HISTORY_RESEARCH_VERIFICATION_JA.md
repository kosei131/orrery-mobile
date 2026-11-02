# 履歴研究アプリの実装・検証（2026-11-01 ハワイ）

## 起動する

`research-resume-checkout` 内の **START_HISTORY_RESEARCH.cmd** をダブルクリックする。
このPCのCodex同梱Pythonを使い、なければWindowsのPython 3.12ランチャーを使う。
コンソールに出た専用URLを同じPCのブラウザーで開く。終了はCtrl+C。
同じポート8765の別プロセスがある場合は、使っていた画面のプロセスを終了してから起動する。

PowerShellから直接起動する場合（このフォルダーで実行）:

```powershell
& 'C:\Users\sanna\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' mt5_local_dashboard.py --history-dir research_artifacts_20261101/public_xau_bars --research-results research_artifacts_20261101/lsr02_vhf03_crosschecked_history.json
```

MT5モジュールも端末も不要。取得済みの公開OHLCを読む研究画面であり、現在価格ではない。
履歴は起動時に読み込む。データを変更した場合は再起動する。
口座情報は不明、発注経路なし。元フォルダー・既存未コミット変更を保持した。
ブランチは research/mt5-candidate-history-probe。本番へマージしていない。

## 前回の失敗6件の分類

初回968件の失敗は、今回の画面統合前の取得HEADで観測していた。
今回の変更による本番機能の回帰や、戦略本体の既存不具合はこの6件からは確認されなかった。

|対象|原因|安全な対応|
|---|---|---|
|test_mt5_local_dashboard のクラス準備|実行環境のローカルソケット制限|サーバーの安全制御を変更せずHTTPテストを再実行し成功|
|test_mt5_probe_verify のsymlink拒否|Windows WinError1314（リンク作成権限なし）|このエラーだけ理由付きskip。他のOSErrorは引き続き失敗|
|test_orrery_history_bootstrap のWindows実ダウンロード|pyランチャーなし|py前提の実統合1件だけskip。模擬pin検証は継続|
|test_windows_launcher の2件|py/curl前提不足|必要実行ファイルがない場合のみskip|
|test_research_session_windows のPython起動1件|pyなしでCMD終了9009、期待2と不一致|当該テストだけpy前提を明示。設定欠落時に起動しないテストは継続|

製品の認証・DEMO拒否・symlink拒否を弱めていない。
skipは未検証でありWindows実機機能の成功には数えない。

## 取得データと集約監査

元CSV SHA256: a587597bbf88c2d868a00a4e0019cd705cee6ca4f20b0485d6b745f19fcc8225

179,662本、2026-03-26 02:28〜2026-09-25 20:44 UTC。OHLC整合、重複0、非分単位0。
1分超の空白175箇所、最大3,279分。UTC21時台の観測は0本。
月別・UTC時間別件数は新しいJSONに保存した。休場・休日・提供元の欠損の認証は未完了。

|時間足|完全足|不完全足の除外|集約系列の空白|最長連続本数|
|---|---:|---:|---:|---:|
|M5|35,893|62|139|276|
|M15|11,942|48|134|92|
|H4|649|163|130|5|

全48,484親足について、元CSVの構成M1が全て存在し、始値・高値・安値・終値が一致することを再照合。
不一致0、欠損補間なし。UTC固定グリッドなので日次休場を含むH4は不完全足として除外される。
これを連続した6か月分のH4やブローカーのセッション足とは呼ばない。
M5/M15は3月26日02:30〜9月25日20:45、H4は3月26日04:00〜9月25日20:00 UTC。

## 同じ履歴でのLSR02/VHF03比較

既存 `_aligned_windows` / `_one_window` / `_summary` と既存戦略を再利用。
buffer=0.1、TP=2R、VHF period=14、閾値0.4、pivot left/right=1、lifetime=6000秒。
結果を見る前に固定して1条件を実行し、結果による調整なし。
両戦略は同一131連続区間で比較し、空白で状態をリセットする。

**LSR02 0候補、VHF03 0候補。勝率、利益R、PF、最大DD、純期待値は不明。**
H4は最長5本で、131区間末の既存構造検出は全てRANGE。
このデータ・連続性規則で方向条件を満たす候補が得られないことを確認した。
前回の別条件による14件の仮定付き研究と合算・同一戦略扱いしない。
費用、ティック内TP/SL先着、未使用評価の証明はなく、優位性や損失ゼロを主張しない。

結果: research_artifacts_20261101/lsr02_vhf03_crosschecked_history.json。
データhash、期間・時刻監査、集約照合、固定パラメーター、全区間、両集計を保存した。
アプリ起動時に保存結果とCSVのhash一致を確認してから表示する。

## 画面とテスト

既存の認証付きloopbackサーバーへ明示的な公開履歴モードを追加。
PUBLIC HISTORY / NOT CURRENTを表示し、DEMO口座への接続成功と混同しない。
ローソク足、ATR/ADX/EMA、支持抵抗、参考構造SL/TPとRR、WAIT理由、リスク不明、戦略集計を統合。
参考SL/TPは終値と確定済みpivotによるシナリオであり、成立したエントリー候補ではない。
H4の指標に必要な本数がない場合は未知のまま表示する。

実サーバーを起動し、実CSVをChromeで描画、3時間足切替、指標・理由・集計・不明口座値を検査した。
verify_history_chart.cjsがこの経路の再現検査。追加のHTTP/安全性/単体・描画・polling検査も成功。
最終の全体Python結果は research_artifacts_20261101/full_tests_final.txt に保存。
最終984件中979件成功・5件理由付きskip・失敗0件（80.175秒）。
CI workflowに新規履歴・統合テストを追加。未pushなので今回変更のリモートCIは未実行。

## 未完成

同一feedの不足期間、Bid/Ask、手数料・滑り・持越し費用、セッションカレンダー、
セッション対応H4の認証、真の未使用期間が必要。次の検証課題はセッション境界の整合。
現在の結果を改善するためにH4の欠損を埋めたり、既存方向条件を外したりしない。
実DEMO接続、恒久ユーザー認証、iPhone、実注文は未実装・未検証のまま。
実口座接続・発注・追加有料サービス利用なし。

## 次回実履歴検証：M1欠損区間の自動監査

`orrery_history_app.py` の既存研究実行時、元M1 CSVを直接読み取って `m1_gap_inventory` を結果JSONへ保存する。
`gap_count`・`missing_minute_slots`・各区間の前後UTC時刻・週末跨ぎの候補を記録する。週末跨ぎは**休場の証明ではない**。市場休場カレンダーとブローカー取引セッションが確認されるまで `session_reason=UNVERIFIED` を保持する。価格補間、H4の自動連結、勝率・純利益の改善主張、注文処理は行わない。

取得済みの元CSVはPCに保存したまま、結果JSONのみローカルに作る。既存の研究を同じ入力で再実行すると監査が追加される（出力先は新規ファイルに指定する）。このコミット自体ではPC保管の実CSVを再計算していない。
