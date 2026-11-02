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

## Work再監査（2026-11-01 ハワイ）

PR #7 HEAD 7fd50f9 とPR #6/#1の最新CI成功を再取得して確認。
PC操作なしで、クラウドに残っていた公開元CSVのSHA256が上記と一致することを確認し、
既存集約CSVと元M1を再照合して履歴研究を再実行した。PCの最新状態を操作・確認したものではない。

今回の事前課題は「H4が欠ける枠を、元M1の部分観測・無観測・取得端に区別できるか」。
既存orrery_xau_h4_m1_completenessの分類処理を副作用のない関数へ切り出し、
M1 gap inventoryで再利用。全UTC H4枠を検査し、取得端を内部欠損から分離する。
元CSVのhashを保存し、処理前後の変更と1年超の範囲を拒否する。
既存history_appのm1_gap_inventory経路に自動で含まれ、CIも公開CSVに対しこの監査を実行・保存する。

実測: M1 179,662本・175空白、観測間の未観測分スロット84,955。
これは休場時間を含む可能性があり、全てを提供元欠損とは呼ばない。
H4内部649完全枠、161部分観測枠、292無観測枠。取得端2枠は別記。
元M1照合: M5 35,893、M15 11,942、H4 649の全親足に不一致0。
同じ固定条件・131連続区間でLSR02/VHF03とも候補0。期待値・利益率・PF・DDはnull。
HalfTrend05/Reversal04はこの比較へ未統合で、戦略全体の検証完了ではない。
既存の14件の仮定付き研究とは合算しない。未使用期間評価でもない。

境界の完全枠、部分観測、無観測、取得端、過大な時間範囲の回帰検査を追加。
全Python 990件中985成功・5 skip。失敗0。詳細はh4_source_reaudit.json。
監査改善として保存するが、セッション連結・戦略採用は保留。
次は出典と適用期間を固定したセッション証拠を既存calendar照合へ接続し、
正常休場でも部分足の意味を確認してから独立研究する。補間・停止条件変更・発注なし。

## 週次時刻仮説による空白の分解（Work継続研究）

事前課題: 175空白のうち、既存の週次時刻仮説でも説明できない部分を抽出する。
orrery_xau_session_coverage.weekly_open を再利用し、空白の各未観測M1を分類する。
既存の週次定義を再取得した事実や正式カレンダーとは扱わず、EXISTING_UNVERIFIEDと表示。
新規の休場時刻の推測、価格補間、H4連結、戦略閾値の変更は行わない。

同じ元CSV hash a587597bbf88c2d868a00a4e0019cd705cee6ca4f20b0485d6b745f19fcc8225:
- 全未観測84,955分 = 週次休場候補83,130分 + 週次OPENだが無観測1,825分。
- 休場候補のみ104区間、OPEN無観測のみ44区間、両者混在27区間。
- 未観測70,370分は参照週次資料の公表時刻2026-08-22T20:59:35Zより前。
  この仮説を当時から既知だった条件・未使用期間の証拠として利用しない。
- 休場候補は休場の証明ではなく、OPEN無観測も欠損か未記載例外かは不明。

元M1 inventoryと履歴アプリの既存経路に分類を保存。CIの既存監査JSONにも含まれる。
週次境界、週末、公表時刻、混在、説明不能、件数不一致、重複/過大区間を検査。
Python全994件中989成功・5skip・失敗0。価格/戦略/注文経路は変更せず、損益は再評価していない。
証拠: research_evidence/local-history-20261101/weekly_gap_partition.json。
監査として保存。H4連続性の回復・戦略採用は保留。
次工程はOPEN無観測1,825分の区間を同一提供元の休日・セッション変更証拠と照合すること。

## 元M1に固定した週次セッションH4の別集約

事前課題: 既存週次仮説で、OHLCを補完せずH4の利用可能な連続区間が増えるか。
新規のsession_review APIと --session-review-dir オプションを履歴研究に追加。
元CSVと正規化M1の全時刻・全OHLCをDecimalで1行ずつ完全照合し、件数・hash変更を拒否。
既存orrery_xau_session_coverage.crosscheckとaggregateを再利用。別の新規ディレクトリーへ
未認証H4と監査JSONを保存し、通常compare/snapshotへの自動入力・基準足の差替えは行わない。
休場時刻に実際の観測があれば、既存通りセッション足の出力を止める。

元CSV hash a587597bbf88c2d868a00a4e0019cd705cee6ca4f20b0485d6b745f19fcc8225。
179,662行の正規化OHLC/時刻一致。通常H4 649本・最長5本から、週次仮説H4 779本・
最長31本へ。追加130本は日次休場を含む実観測の部分セッション足で、240分足とは別の意味。
12本以上の連続区間22、該当終点396。未説明OPEN 1,825分は除外したまま、不完全枠39。
通常LSR02/VHF03の固定条件比較は候補0のまま。新セッション足で戦略比較は未実行。
Reversal/HalfTrend未統合、費用・利益率・PF・DD・未使用評価は未確認。

提供元資料の再確認（2026-11-02T06:01:14Z、ハワイ11/1）:
- https://getdata.finance/coverage/xauusd : 週次UTC時刻と資料生成時刻を検索取得結果で確認。
  直接アクセスはHTTP530。検索結果の報告末日は9/11で、手元CSV末日9/25とは異なる。
- https://www.getdata.finance/documentation : 通常休場・休日等を除く説明はあるが、
  今回の4/2〜3・7/3等を確定できる具体的な例外区間は見つからなかった。
- https://www.getdata.finance/data-sources : broker CFD価格であり他社・取引所と同一とは限らない。
資料の一般的説明を対象日の休場証明に転用せず、他社の休日表で元データを正当化しない。
資料hashや同一feedの真正性は未認証。公表前期間を事前既知として扱わない。

テスト: 正常な部分セッション、改変価格、行欠落、休場中の実観測、既存出力保護の5件追加。
全Python999件中994成功・5skip・失敗0。CIに実公開CSVからの統合再計算を追加。
証拠: research_evidence/local-history-20261101/session_rebuild_diagnostic.json。
継続性拡張の研究基盤として保存。セッションH4の戦略採用は保留。
次は8/22の資料公表後に限定し、週次仮説の完全区間でLSR/VHFを別研究比較する。
これは既閲覧期間の記述的研究であり、未使用検証とは呼ばない。

再実行（既存出力と別の新規パスを指定）:
```powershell
python orrery_history_app.py --bars research_artifacts_20261101/public_xau_bars --source research_artifacts_20261101/xauusd_public_m1.csv --output research_with_sessions_new.json --session-review-dir session_diagnostic_new
```

## 公表後の同条件LSR02/VHF03比較

事前仮説: 価格を補間せず、既存週次ルールの部分セッションH4を加えることで
方向判定可能な区間と候補が増えるか。費用後の改善を予め仮定しない。
orrery_history_session_study.pyを追加し、元CSV hash・全M1照合・基準足照合を通してから
既存compare/_one_window/_summaryを再利用。buffer0.1、TP2R、VHF14/0.4、pivot1/1、
lifetime6000秒の1条件だけ実行し、結果を見た再調整なし。2.6の定義を変更しない。

資料の公表2026-08-22T20:59:35Zを切り上げ、2026-08-23T00:00Z〜9/25T20:00Zに限定。
両H4方式に同一M5/M15入力を渡しhash一致を記録。開始前のH4/M15 warmupなし。
UTC完全足124本/最長5本に対し、未認証週次H4は132本/最長18本。
どちらも25独立区間で欠損リセット。ただしH4による再生可能範囲が違い、
M5再生本数は5,952対6,120。同一の有効観測本数による比較とは呼ばない。
各H4方式のLSR02とVHF03は同じ候補集合から事前VHF値で分ける。

|H4方式|LSR02候補|VHF03候補|価格参照結果|
|---|---:|---:|---|
|UTC完全足のみ|0|0|不明|
|週次部分足・未認証|1|0|1損失、-1R|

唯一の候補: 9/2 09:10UTC SELL、終値参照4318.54、構造SL4331.68、TP4292.26。
11:40UTCにSL先着のM5 OHLC参照。H4 DOWN、VHF約0.26565/FALLINGで除外。
スイープ極値4331.58+buffer0.1がSL、TPは2Rの固定比較仮説。
失敗理由の因果証明ではない。VHFが1損失を除外しただけで改善とは判断しない。
この1件のgross平均R=-1、PF=0、退出時点の参照DD=1R。口座DD・利益率・純期待値は不明。
VHFの0候補を利益0・無損失とは扱わない。既閲覧期間なので未使用評価ではない。
Reversal04/HalfTrend05/LSR01独立経路/未定義2.6を含む全戦略検証ではない。

新規6テスト: 同一H4時の実エンジン一致、資料公表前warmup排除、欠損の維持、
不正時刻/OHLC拒否、元CSVpin不一致の出力拒否、入力不変。
全Python1005件中1000成功・5skip・失敗0。CIにも実CSV比較を追加。
証拠: research_evidence/local-history-20261101/paired_session_strategy_comparison.json。
この結果は研究上の候補生成の成立確認に留まり、戦略の採用は保留。
SL/TP変更・ロット引上げ・注文・本番反映なし。口座リスク制限は変更せず、このgross参照計算には未適用。

再現:
```powershell
python orrery_history_session_study.py --source research_artifacts_20261101/xauusd_public_m1.csv --bars research_artifacts_20261101/public_xau_bars --source-sha256 a587597bbf88c2d868a00a4e0019cd705cee6ca4f20b0485d6b745f19fcc8225 --output-dir paired_session_new
```
次は25区間の構造→スイープ→確認→リテストの候補生成経路を診断し、
候補1件の主因が観測範囲かルールの希少性かを分ける。条件を緩めて勝ちを作らない。

## 候補生成の停止段階を実エンジンから計数

事前課題: 同じ期間で候補が1件になる原因を、H4ゲート・開始・確認・リテストに分解する。
lsr02_replay.replayに任意の空diagnostics辞書を追加。既存の分岐を通る際に件数だけを記録し、
売買条件・SL/TP・停止条件・戻り値traceは変更しない。regime/永続halt併用診断は未対応として拒否。
別の推定ロジックで候補理由を再現せず、既存の実分岐を使用する。
同じ状態の反復trace行は新規候補に数えず、失効元状態も記録する。
paired研究の25区間ごとに集計し、H4状態合計=M5本数、スイープ理由合計=イベント数を照合。
既存の粗い公開M1研究のfunnel報告とは対象戦略・期間が異なるため合算しない。

8/23〜9/25 UTC・同じ元CSV・同じ固定条件の実測:

|項目|UTC完全足|未認証週次部分足|
|---|---:|---:|
|再生M5終値|5,952|6,120|
|H4未取得|1,175|1,010|
|H4 RANGE判定|4,777|4,965|
|H4 DOWN判定|0|145|
|観測M5終値と同時刻のM15 sweepイベント|201|203|
|H4未取得/古いによる見送り|40|35|
|H4 RANGEによる見送り|159|158|
|H4方向不一致|0|3|
|同時複数sweep|2|2|
|既存候補処理中|0|1|
|SWEEP開始|0|4|
|CONFIRM|0|1|
|RETEST|0|1|

週次版の4開始から3件はSWEEP段階で失効、1件はRETEST後に失効。
全失効理由は期限1/SL接触3であり、候補失効4件を損失取引4件とは呼ばない。
唯一の参照取引は前回通り-1R。候補・参照結果・VHF群・集計は前回証拠JSONと完全一致。
主な観測上の制約は193/203 sweepがH4未取得またはRANGE判定で開始されないこと。
これはH4条件を外せば利益が出る証明でも、全RANGEが実市場のレンジだった証明でもない。
欠損によるリセット、少ないH4文脈、実際の構造条件の寄与を現段階では分離できない。

新規5テストとペア比較への統合検査を追加。BUY/SELLのtrace不変、レンジ・未取得、
失効の重複排除、非空辞書拒否を確認。全Python1,010件中1,005成功・5skip・失敗0。
最初の全体実行で旧bootstrapの固定hashと現在ファイルを混同したテストが失敗したため、
当時のlsr02_replayをhash確認済みの固定fixtureへ保存してテスト入力を修正。
製品の固定REVISION/PINS・ダウンロード検証は変更/緩和していない。
証拠: research_evidence/local-history-20261101/decision_funnel_diagnostics.json。
候補条件緩和や指標追加は採用せず保留。純利益・口座DD・未使用性能は未確認。
次はH4のリセット後本数と方向判定を照合し、必要文脈を満たせる時間帯を測定する。

## H4 RANGEの確定構造不足と非方向構造の分離

事前課題: RANGEのうち、既存ルールに必要な確定HIGH2組/LOW2組がない場合と、
組数はあるが直近の高低両方の切上げ/切下げが揃わない場合を区別する。
新たな閾値は置かず、replayがその時点で使用したdetectの確定pivotを診断に再利用。
参照H4本数の分布と理由×本数、M15 sweep時のH4理由も保存する。
H4/M15の公表前warmup、欠損越し連結、判定ルール変更は行わない。

同じ8/23〜9/25 UTC・元CSV hash・固定条件でのM5判断時点数:

|H4文脈|UTC完全足|未認証週次部分足|
|---|---:|---:|
|H4未取得|1,175|1,010|
|確定HIGH/LOWの組数不足|4,777|4,412|
|組数はあるが方向条件不成立|0|553|
|下降構造成立|0|145|

週次版の組数不足4,412件中4,177件はH4文脈1〜4本、残り235件は5〜7本。
本数とpivot組数は別物で、長い単調/横ばい系列でもpivot組数が不足し得る。
組数不足を必ずデータ欠損が原因だと断定しない。既存ルールのRANGEを市場の真のレンジと呼ばない。
これらはM5の判断時点数で、独立したH4標本が6,120件ある意味ではない。

週次版203 sweepイベント時のH4文脈は未取得35/組数不足142/非方向構造18/下降8。
この文脈別集計は、前回のゲート理由集計とは階層が異なる。同時複数sweepを含み、
前回HTF_RANGE158件との不一致は計数ミスではない。
各文脈/本数/理由×本数の合計=M5判断時点、sweep時文脈の合計=sweep数を機械照合。
前回の候補・VHF群・損益集計と既存診断カウンター全てが不変であることも照合。
参照結果はLSR02の1件-1R、VHF03候補0のまま。純損益・口座DD・未使用性能は不明。
HalfTrend/Reversalを含む全戦略の検証完了ではない。

新規3テストと既存flat診断への検査追加: 短い文脈、確定した混在構造、成立する方向を区別。
全Python1,013件中1,008成功・5skip・失敗0。
証拠: research_evidence/local-history-20261101/h4_context_diagnostics.json。
診断改善として保存。データ不足を解消するために方向条件を緩める採用は保留。
次は、休場と区別できないH4中断を元M1の未説明OPEN区間に対応付け、
長い文脈を壊す少数区間を同一feedの証拠取得対象として優先順位付けする。

## H4中断と元M1の具体的な証拠取得対象

事前課題: 文脈を分断する少数の未説明OPEN区間を、元データの時刻へ対応付ける。
orrery_h4_gap_requests.pyを追加。正規化M1・生成H4・カレンダーを別々のファイルhashで固定し、
既存calendar_minutes/load/_groupsを再利用。期待OPEN M1が全てある枠とH4有無が矛盾すれば停止。
週次休場のみの枠にOHLCを作らない。対象は同じ公表後8/23〜9/25 UTC。

週次H4の連続群間に21中断。うち週次CLOSED H4枠を含まない17中断を、
M1または例外資料の証拠確認対象として優先順位付け。17区間の未説明OPENは計61分。
残り4中断は週次休場枠を含むため、単純な追加quote取得で連結する対象にはしない。
範囲内の未説明OPENを含むH4欠落は22枠。21中断の数とは定義が異なる。
先頭側の8/23 20時H4枠（未説明OPEN1分）は研究境界として別記し、先行文脈があると仮定しない。

優先順位は「週次休場枠を含まない→前後の観測済み連続H4本数の合計が多い→未説明分が少ない」。
価格結果・勝敗をランキングに使用せず、復元後の利益・候補数は推定しない。

|確認すべきM1 UTC区間（終了排他）|直前の連続H4|直後の連続H4|
|---|---:|---:|
|9/2 22:00〜22:01|18|5|
|8/25 22:00〜22:01|11|5|
|8/27 22:00〜22:01|5|6|
|9/3 22:00〜22:01|5|6|
|9/10 22:00〜22:01|5|6|

前後本数は現状の観測量であり、これを足せば構造がそのまま連結できるという主張ではない。
未観測1分でも、通常の無更新、提供元欠損、取引時間例外のいずれかは未認証。
他社Bid/Askで元提供元の欠損を埋めず、同一feedの当該時刻または正式な例外証拠が必要。

既存paired研究へ統合し、CIの比較JSONにも対象区間を保存。候補・損益集計は前回と完全一致。
元CSV a587597bbf88c2d868a00a4e0019cd705cee6ca4f20b0485d6b745f19fcc8225、
H4 f20d05e6d43212c71906b3e10ef7a5a49a55871ceebd675c947fee41f97226c9を使用。
7テスト追加: 単一分、休場、研究境界、pin/公表時刻、H4欠落矛盾、順位、混在休場。
全Python1,020件中1,015成功・5skip・失敗0。実データ取得やPC/MT5アクセスは未実行。
証拠: research_evidence/local-history-20261101/h4_interruption_evidence_requests.json。
候補取得計画として保存し、価格補間・戦略採用・発注は保留。次は最上位区間の
同一提供元のM1/更新イベントまたは無更新・セッション例外の証拠を確認する。

## 最新提供元版による未観測分の再確認

事前課題: 上位未観測時刻が最新公開版で追加/改訂されているか、価格混合なしで確認する。
2026-11-02T08:20:20.815998Z（ハワイ11/1）に提供元mainのHEADをAPIで取得し、
固定commit adcd99e7e0abee51e9a5eef123935e68a8d8aa30 のCSVを新規パスへ取得した。
commit時刻は9/26 02:33:14UTC。最新であることは今回のHEAD取得時点に限る。
取得元は次の不変URL:
https://raw.githubusercontent.com/getdata-finance/xauusd-1m-ohlcv-metals-historical-data/adcd99e7e0abee51e9a5eef123935e68a8d8aa30/XAUUSD_1m.csv

15,205,326 bytes、SHA256 a587597bbf88c2d868a00a4e0019cd705cee6ca4f20b0485d6b745f19fcc8225。
元CSVと全バイト一致、179,662行。観測重複部のOHLC改訂0、行追加0/削除0。
前回17区間の確認対象61分は全て未観測のままで、9/2 22:00の原因は未解決。

orrery_m1_revision_compare.pyを追加。元/候補/対象計画のhash、提供元の固定commit URL、
UTC分単位、時刻一意性、有限OHLC/volume、対象の重複と元で既観測でないことを検査。
対象分の追加と既存重複部のOHLC/volume改訂、行削除を分離する。
行追加が見つかっても、その元quoteや補修方法を認証したことにはならず、自動統合しない。
このモジュール自体はネット接続・上書き・補間・注文を行わない。

提供元公開資料 https://www.getdata.finance/documentation を検索取得で再確認。
一般的な休場除外と補修方法の説明はあるが、当該分の無更新/欠損/例外を証明する
個別レコードは確認できなかった。直接取得はHTTP530。
FXCMの公開Candle/Tick資料も確認したが、公開列挙にXAUUSDはなく、別銘柄URLを推測して取得しない。
資料: https://github.com/fxcm/MarketData/blob/master/CandleData/README.md
https://github.com/fxcm/MarketData/blob/master/TickData/README.md
他社データや一般的な開場時刻で元提供元の欠損を埋めない。

6テスト追加: 同一版、対象行追加、重複価格改訂、既存行消失、pin/URL/対象拒否、不正CSV。
全Python1,026件中1,021成功・5skip・失敗0。CIに単体検査を登録。
証拠: research_evidence/local-history-20261101/latest_provider_revision_check.json。
新しい実相場成績は計算せず、前回参照1件-1R/純利益不明を維持。
HalfTrend/Reversalを含む全戦略の検証完了ではない。修復/戦略採用は保留。
この公開版からの欠損原因確定は証拠不足のため停止。次は別の無料一次配信元を
独立研究系列として利用できるか確認し、元系列を補修する目的では混合しない。
PC/MT5への接続、問い合わせ送信、購入、発注、本番マージ/配備は行っていない。

## 独立Dukascopy系列の少量取得経路

事前課題: GetDataと混合せず、別の一次提供元でBid/Askを独立検査できるか。
既存orrery_duka_source_probe.pyを再利用し、匿名の1時間公開archiveだけを扱う。
公式の履歴export資料でBid/Ask提供を確認。一括S3資料はRequester Paysのため利用しない。
https://www.dukascopy.com/api/data/get/historical-data-export
https://www.dukascopy.com/wiki/en/development/data-export/

取得試行: 2026-11-02T08:35:04.806197Z（ハワイ11/1）、XAUUSDの9/2 12時UTCの1時間。
https://datafeed.dukascopy.com/datafeed/XAUUSD/2026/08/02/12h_ticks.bi5
1要求がHTTP429で停止。生データ未取得、実ティック数・価格倍率・配信品質は未確認。
429が提供元か中継側かは特定していない。再試行、代理経路、課金経路を使って回避しない。
旧receiptのfetched_at_utcは開始clockだったため、証拠JSONではrequest_started_at_utcと明記。
既存端末/MT5の接続ではない。GetDataの欠損補修にも使用していない。

改修: 明示UTC/過去の1時間/銘柄を確認し、新規フォルダーのみへ保存。
リダイレクト禁止、匿名固定URL、圧縮30MB/展開40MB・LZMAメモリ64MiBを上限化。
単一ストリーム終端・20byte framing、時刻順/時間範囲、ask>=bid>0、有限非負volumeを検査。
同時刻tickは保持し重複clockを数える。価格倍率を推測してドル損益へ換算しない。
失敗receiptに架空tick_countや成功を入れず、エラー型/HTTP状態だけを保存。
モジュール自身にS3/認証/課金/インストール/注文処理はない。

9テスト追加: record順序、価格/volume/clock、展開上限、不完全/連結ストリーム、
転送拒否、模擬成功、HTTP失敗、既存出力保持、不正時刻。
全Python1,035件中1,030成功・5skip・失敗0。実取得成功とは区別する。
証拠: research_evidence/local-history-20261101/duka_independent_source_probe.json。
取得未完のため独立データによる戦略比較は未実行。既存の純損益・口座DDは不明のまま。
この経路の実取得は429で保留。次は無料web exportの利用条件と出力仕様を確認するか、
別一次提供元のUSDJPY少量履歴を独立に取得できるか調べる。追加課金・権限緩和はしない。

## FXCM取得保留と受領済みTradingViewでのHalfTrend比較

FXCM公式CandleData資料でUSDJPY/m1の公開URL方式を確認し、2026年36週を1要求だけ試行。
https://github.com/fxcm/MarketData/blob/master/CandleData/README.md
2026-11-02T08:44:12.376789Z（ハワイ11/1）、次のURLはHTTP403で停止した。
https://candledata.fxcorporate.com/m1/USDJPY/2026/36.csv.gz
提供元と中継側のどちらの制限か、対象年週のデータがあるかは未確認。生データ未取得。
別経路/認証/権限緩和で回避せず、証拠をfxcm_usdjpy_source_attempt.jsonへ保存。

新データ不足で停止したため、次の未完研究へ進めた。事前仮説は
「確定RETEST時のM5 HalfTrend方向が候補側と一致する条件で価格参照結果が改善するか」。
既存lsr05_halftrend.calculateを再利用し、amplitude2/channel2/ATR100の1設定を固定。
既存LSR02/VHF03候補・SL/TP・参照約定・欠損リセットは変更せず、その同じ候補を分類。
各連続窓のM5で初期化し、入口の完全一致clockの行だけ使用。未来行や次のsignalを取らない。
ATRが準備できない候補はNOT_READYに残し、反対signalや損失として扱わない。
外部TV版HalfTrendとの一致/非リペイントは未証明。Reversal04用の外部signalをHalfTrendで代用しない。

入力: 受領済みORRERY_FX_XAUUSD_CSV ZIP、OANDA:XAUUSD、共通10/6〜10/30 UTC、
ZIP SHA256 60c9f24963138f9c3d5673627662c964e523dc00a0bdb86936737566fce7a32b。
18独立窓、M5 4,968本の基準再生。4候補・既存SL/TP/各参照結果が前回v2証拠と完全一致。

|群|候補|TP参照|SL参照|未決着|
|---|---:|---:|---:|---:|
|LSR02全体|4|2|1|1|
|HalfTrend方向一致|2|0|1|1|
|HalfTrend方向不一致|1|1|0|0|
|HalfTrend準備不足|1|1|0|0|

この小標本では方向一致だけ残す案を採用する根拠はない。
方向一致群の決着済みgross平均は-1Rだが、未決着があるため全候補合計R・口座DD・利益率は不明。
反対群が1勝だったことから逆張りを採用せず、利益/勝率向上も主張しない。
VHF03は従来通り2候補（1TP/1未決着）。別の公開M1研究1件-1Rとは合算しない。
Reversal04は外部観測未提供としてNOT_EVALUATED、LSR01独立経路と未定義2.6も未比較。
HalfTrendの候補群比較を含めたが、全戦略・費用込み成績・未使用期間検証の完了ではない。

新規orrery_tradingview_halftrend_study.pyと6テストを追加。未来行不使用、初期化不足、
一致/不一致で元plan維持、欠落clock、重複clock、ZIPpin/評価範囲を検査。
全Python1,041件中1,036成功・5skip・失敗0。CI登録済み。
証拠: research_evidence/local-history-20261101/tradingview_halftrend_cohorts.json。
戦略採用・SL/TP変更・発注・本番反映なし。次は未決着と少数標本を保持したまま、
同じ設定の再現・追加期間検証へ引き継ぐ。勝者群だけで条件を選び直さない。
