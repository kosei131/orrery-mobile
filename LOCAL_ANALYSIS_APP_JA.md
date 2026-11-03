# ORRERY FX 個人用ローカル分析アプリ

## 起動

このチェックアウト全体を使う。dashboard単体配布では分析モジュールが不足する。
通常のWindows Python 3.12環境では、フォルダー内で次を実行する。

```powershell
py -3.12 mt5_local_dashboard.py --test-data
```

表示された `http://127.0.0.1:8765/#...` を同じPCのブラウザーで開く。
test-dataは模擬口座の表示確認専用で、価格・分析・接続成功を装わない。
このPCのCodex同梱Pythonでは次で起動できる。

```powershell
& 'C:\Users\sanna\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' mt5_local_dashboard.py --test-data
```

実デモ読取は、MetaTrader5 Pythonモジュールを利用できる環境で、利用者が
ログイン済みDEMO端末の絶対パスを確認して指定する。口座ログインAPIは呼ばない。

```powershell
py -3.12 mt5_local_dashboard.py --terminal-path 'C:\Program Files\MetaTrader 5\terminal64.exe'
```

パスは例。デモ口座の確認なしに実行しない。REAL/CONTESTはデータ読取前に拒否する。
終了はCtrl+C。tokenは起動ごとに変わる。同じPCでもURLを知る利用者が読めるため共有しない。

## 統合した画面

既存画面の残高・評価額・証拠金・建玉・Bid/Ask・M5/M15/H4確定足に、
lsr02_snapshot_overlay / orrery_indicator_diagnosticsを同一snapshotから接続した。
選択時間足の重要価格帯をチャートと数値で示し、ADX14・ATR14・EMA20/50を表示する。
支持<確定足終値<抵抗が成立する場合だけBUY/SELLの構造SL/TP参考シナリオと費用前RRを示す。
これは確定したLSR02/VHF03エントリーでも、成行約定価格でもない。
古い・欠損・不正な系列に参考値を出さない。取得失敗時は表示を消す。
純期待値、口座合計SLリスクは根拠不足のため未検証。RRを期待値へ読み替えない。

## 認証・アクセスと今後のiPhone設計

現段階はloopback限定、起動ごとのbearer token、Host/Originチェック、no-store、
外部通信禁止CSPを維持する。恒久的なユーザーアカウント認証は未実装。
API境界は読み取りsnapshotのみで、注文endpointを持たない。

iPhone対応時は、このHTTPを外部公開せず、別のHTTPS認証gatewayを設ける。
所有者1名のallowlist、パスキー等のログイン、短命セッション、失効、CSRF防御、
アクセス監査とデータ最小化を実装してから公開する。MT5資格情報はPC内に保持する。
閲覧権限と将来の承認権限は分離し、閲覧セッションに注文権限を与えない。
将来の注文案は候補ID、戦略版、時刻、数量、SL/TP、最大損失、費用仮定、
有効期限を固定し、本人の最終承認後にも口座・価格・リスク・重複を再検査する。
既存の承認・予約研究モジュールの再利用は別工程。現在は承認ボタンも送信経路も追加しない。

## 検証・不足

- Python: dashboard HTTP認証、安全性/チャート/価格/overlay/新規統合、期間ゲート・指標・バリア・費用を合わせた52件成功。
  ソケット制限で停止したHTTP検査は許可された制限外実行で再検証した。
- Node: pollingテスト成功。Chromeで実HTMLに模擬応答を与え、390px幅の描画、
  価格帯線、SL/TPと未知期待値、時間足切替、古い/模擬データのチャート消去を確認。
- CI workflowに新規統合テストを追加。ローカル変更は未pushで、新版のリモートCIは未実行。
- 前回取得HEAD af93769 のCIは成功。既存全体discoveryのWindows環境問題は前回レポート参照。
- このPythonにMetaTrader5モジュールなし。端末ファイルの存在だけを確認し、接続していない。
  実DEMO接続・実配信・現在口座の種類は未確認。
- 6〜12か月の同条件戦略バックテストは未完了。取得済み179,662本の公開M1履歴と
  14工程の再現結果はRESEARCH_RESUME_2026-11-01_JA.md参照。
  不足期間、同一feed Bid/Ask、手数料・滑り・セッション監査、真の未使用期間が必要。
- execution_allowed=false。実口座接続・デモ注文・有料サービス使用なし。

## 保存済みTradingView HalfTrend研究の別枠表示

公開M1履歴のチャートとは別ソースであることを明記した保存済み研究枠を追加。
既存の`--history-dir`起動に以下を追加する（同じローカルPCのみ、外部公開なし）。

```
--halftrend-report research_evidence/local-history-20261101/tradingview_halftrend_cohorts.json --halftrend-report-sha256 REPORT_SHA256
```

REPORT_SHA256は表示したいJSONファイル自体のSHA256。Python例:
`python -c "from pathlib import Path;from hashlib import sha256;print(sha256(Path('research_evidence/local-history-20261101/tradingview_halftrend_cohorts.json').read_bytes()).hexdigest())"`

既存`--research-results`は公開M1履歴と一致する結果専用のまま。
新枠は入力JSONのhash・研究限定フラグと候補から再計算した全群集計を検査し、
出典ZIP hash・対象UTC期間・候補/TP/SL/未決着/同一足曖昧を表示する。
このhashは内容固定であり、提供元真正性やTradingView指標一致の証明ではない。
MT5接続/模擬口座モードには付加できず、チャート上へ注文案を投影しない。
費用/BidAsk・独立未使用期間・口座損益/DD未検証、Reversal04未評価、
LSR01独立経路/2.6未比較とHalfTrend採用保留を明記。
オプション未指定時は未読込、通信失敗時は前の表示を消す。
既存PCへの更新/起動やiPhone接続はこの変更では実施していない。

## 保存済みConfirmation / Retest探索の別枠表示（2026-11-02 HST）

既存の履歴モード起動に次を追加する。

```
--entry-report research_evidence/local-history-20261101/entry_opportunity_reaudit_20261102.json --entry-report-sha256 REPORT_SHA256
```

REPORT_SHA256は当該JSONのSHA256を別途確認して指定する。hashは内容固定であり、
元データの真正性や元計算の再実行を証明しない。4モデル全てを保持し、確認母集団＝
取引案＋非エントリー、取引案＝決着＋未評価、未評価＝構造見送り＋履歴不足、
決着＝出口理由合計と勝率の分母を照合してから表示する。
固定SL6/構造SLを別表示し、timeout評価、Retest期限切れも残す。
H4なし・既閲覧公開OHLCの探索であり、正式LSR02/HalfTrendへ合算しない。
口座収益・純期待値は不明、採用保留。MT5/模擬モードへの付加は起動時に拒否する。
390pxブラウザー検査をCIに追加。今回のクラウド環境にはChromium本体がなく、
ローカル描画検査は未実行。PC更新・公開・注文は実施しない。

## 固定期間の取得状況（2026-11-02 HST）

公開履歴モードにHalfTrend固定期間の状況欄を追加。追加の起動引数は不要。
固定計画と40ソースのhashを照合し、snapshot取得時の時計で開始前/期間中/終了を更新する。
UTCとHSTの期間、経過カレンダー秒、確定足cutoffの上限、各足始値の時刻上限を表示。
各上限は時刻の不等式であり、実際に存在する足やfeedの配信格子を意味しない。
H4を推測したUTC格子へ丸めず、DST・休場・実足の完全性は未確認とする。

この欄は新期間の入力を受領・評価する機能ではなく、状態は常に
NO_PROSPECTIVE_INPUT_ATTACHED。新ZIP受領後は既存holdout/batchで別途検証する。
候補数や期待値を0に置かない。期日到来や終了だけで取得完了・評価完了とはしない。
本セッションのTradingView/OANDAプラグイン検索には該当候補なし。別feedへの置換なし。
時間境界・タイムゾーン同値・入力なし・履歴snapshot非破壊の6検査を追加。
390pxブラウザーで状況欄と横はみ出しを確認する検査もCIへ追加。
固定計画・40ソース・売買条件・認証境界は変更しない。

今回の全Python検査は1084件中1079成功・5skip・失敗0。
固定計画のhash検査も成功。JavaScript構文検査成功。ローカルChromium本体はなく、
新しい描画検査の実行結果は今回の研究コミットに対応するCIを参照する。
