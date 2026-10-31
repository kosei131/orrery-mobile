# 一括DEMO検証worker — 第1実装

取得→品質確認→独立$3000口座比較を、既存の2つのCLIで直列実行する。
新規発注・口座ログイン・戦略変更・ネットワーク配信・定期実行は含まない。
実端末への導入・実データ実行はまだ行っていない。

## 今回追加したもの

- `orrery_research_worker.py`：事前設定された1回分の実行、OS所有ロック、段階別timeout、
  状態記録、保存結果の照合、最終marker。
- `orrery_research_code_manifest.py`：信頼したローカル配布物の全トップレベルPythonを
  SHA256で固定する準備コマンド。上書きせず、pinを標準出力へ表示する。
- `research_worker_settings.example.json`：disabled、費用nullの見本。
- `test_orrery_research_worker.py`：模擬MT5で既存両エンジンを通す試験と失敗系試験。

既存LSR・MT5エンジン・リスク管理のソースは変更していない。
CIには新テストモジュールだけを追加登録する。

## PC上での準備とコマンド

Windowsの同一利用者で、Python 3.12と公式MetaTrader5が導入済み、MT5がDEMOへ
ログイン済みであることが必要。別のPython MT5画面はこの実機確認中は停止する。
このチャットから利用者のPCでこれらの操作を実行できる状態にはなっていない。

1. 新しい研究ブランチの配布物を確認して展開する。コードは信頼したものを使う。
2. `research_worker_settings.example.json`をGit管理外へコピーする。
   最新の日付へ勝手に書き換えず、確認対象の短い過去期間を明示する。
   XAUUSD、USD DEMO、同一ハワイ日次区間、broker rollover除外の根拠が必要。
3. pilotの往復費用（価格/原単位）とaccountの往復費用（USD/lot）は別々に根拠付きで入力。
   slippageの単位は価格。未設定なら停止。今回は両方の往復費用0を許可しない。
   slippageは既存エンジン同様、明示的な0以上の仮定を要求し、実証済みと扱わない。
   `no_carry_interval_confirmed`は実際に確認したときだけtrueにする。
   条件が揃ったら`enabled=true`にする。
4. 以下のコードmanifestを作り、表示SHA256を別に保存する。
   `FULL_REVIEWED_COMMIT_SHA`は取得した版の40桁commitへ置換する。
   出力先フォルダーは事前に作成する。以下のLOCALAPPDATAを使うコマンドはPowerShell用。

```powershell
py -3.12 orrery_research_code_manifest.py --declared-revision FULL_REVIEWED_COMMIT_SHA --output "$env:LOCALAPPDATA\ORRERYFX\code_manifest.local.json"
```

5. 設定とmanifestの実際のパス・別途保存したSHA256を指定して起動する。
   `SETTINGS_FILE`、`MANIFEST_FILE`、`INDEPENDENTLY_RETAINED_SHA256`は実値へ置換する。

```powershell
py -3.12 orrery_research_worker.py --config SETTINGS_FILE --code-manifest MANIFEST_FILE --code-manifest-sha256 INDEPENDENTLY_RETAINED_SHA256
```

コードmanifestのrevisionは**利用者が申告した版**で、GitHub署名やcommit内容の証明ではない。
ローカルファイルのハッシュと保持pinとの一致を検査する。CRLF/LFが異なる配布物は
別のbytesとなるので、この段階では信頼して展開した当該PC上の内容を固定する。
照合失敗後にmanifestを作り直して通す運用はしない。
コード自体は開始時点で信頼済みである必要があり、この仕組みは悪意あるコードを
隔離するsandboxではない。配布署名・immutable package導入はまだ含まない。

## 出力と状態

CLIの保存rootは固定：`%LOCALAPPDATA%\ORRERYFX\research`。
同じrootでOSロックを取り、二重起動は`WORKER_UNAVAILABLE`で停止する。
Python APIの別root指定はテスト/埋込用で、別root間まで排他するものではない。
運用ではこの1つのrootだけを使う。

実行ごとに`runs/<UUID>/`を作り、設定、コードmanifest、capture、accountを保存する。
状態ファイル`status.json`は原子的に置換し、VALIDATING→CAPTURING→COMPARING→
COMPLETED_RESEARCH、またはBLOCKED_CONFIG/BLOCKED_DATA/FAILEDを記録する。
理由は固定の短いコード。口座ID・server・端末絶対パス・生の例外・子stdoutを
状態ファイルに書かない。設定ファイル自体にはterminalのローカルパスを含むため、
保存rootは本人だけのアクセス権にし、全フォルダーをGitHubへアップロードしない。

両エンジンの成功report status、capture pin、account markerと入力pin、catalog pin、
account出力3ファイルのhash、固定設定hashを照合して`job_complete.json`を最後に作る。
子の終了コード0だけでは完了にならない。品質停止はBLOCKED_DATA、タイムアウトは
FAILED/STAGE_TIMEOUT。未設定値から損益を作らず、候補ゼロの成功は候補ゼロのまま。

前回の状態が実行途中なら、次の起動でロックを取得後にINTERRUPTEDとする。
途中markerを自動修復・resumeせず、新しいUUIDで再実行する。
最終marker作成直後にプロセスが停止して状態更新できなかった場合も、保守的に
INTERRUPTEDとして手動確認を必要とする。成功が自動復元されたとは主張しない。
同じ期間の再実行は別UUIDになるが、新しい市場期間とはみなさない。
まだ期間横断の集計や自動的な重複排除は行わない。

終了コード：0=COMPLETED_RESEARCH、2=記録済みの停止/失敗、1=worker自体が起動不能。
いずれも利益の成功・実市場優位性の証明ではない。`execution_allowed=False`を維持。

## 未完了の機能

この版は一括実行core。次は完了markerの独立再監査と、個人情報を除く閲覧用要約を作る。
定期heartbeat、スマホ画面、認証サーバー、Tailscale設定、定期タスク、一括installer、
配布元の署名確認、ディスク使用上限、package/MT5版の自動記録は未実装。
現在のstatus時刻は**段階の更新時刻**で、継続的な稼働証明ではない。
ファイルhash検査と処理は原子的な端末/ファイル全体のtransactionではない。
保存rootのWindows ACLと空き容量は導入時に確認し、不要データを自動削除しない。

実Windowsのworker起動、timeout時の端末後処理、実ブローカー履歴、費用設定、
初回口座比較、スマホ閲覧は別途実機で確認する。PC上でまだ自動実行は始まっていない。
