# PCでの操作をまとめる一括セッション

追加した`START_RESEARCH_SESSION.cmd`から、既存worker、実行記録receiptの保存、再監査、
要約JSON保存をまとめて行う。既存worker・監査・MT5・戦略・リスクの処理は変更しない。
利用者のPCを遠隔操作したり、この更新を自動導入したりするものではない。

## 最初に一度だけ必要な準備

1. 新しい研究ブランチのファイルを信頼した配布元から取得・展開する。
   Windows Python 3.12と公式MetaTrader5が必要。既存のDEMO口座を開く。
2. Git管理外の本人専用フォルダーへworker設定を保存する。
   期間、source、費用単位、根拠、rollover除外などは既存手順どおり。
   未設定を0で埋めない。費用0の動作確認モードは追加していない。
3. 新しいコード全体に対して、既存manifest準備コマンドでcode manifestを固定し、
   表示SHA256を別に保持する。過去実行のmanifest/pinは書き換えない。
4. `%LOCALAPPDATA%\ORRERYFX\research\settings`を作成する。
   `research_session_settings.example.json`をそこへ`session.local.json`としてコピーし、
   次の3項目を手元で入力する。すべて実際の値が必要で、見本はそのままでは動かない。

| 設定 | 内容 |
| --- | --- |
| worker_settings_path | 完成したworker設定JSONの絶対パス |
| code_manifest_path | 確認したcode manifestの絶対パス |
| code_manifest_sha256 | 別途保持した64桁SHA256 |

設定JSONでWindowsパスのバックスラッシュは`\\`と記述する。
本人のパス・実行記録・鍵ファイルをGitHubへアップロードしない。
LOCALAPPDATA側のWindowsアクセス権も本人に限定する。

## 以後の実行

展開フォルダーの`START_RESEARCH_SESSION.cmd`をダブルクリックする。
`py -3.12`を使用し、既存のprivate session設定を読む。設定がなければ案内して停止。
ブラウザーやTailscaleを起動せず、外部へ送信しない。

順序は、既存workerの一括検証→返されたreceiptを新規保存→既存再監査→要約保存。
設定・品質・口座条件の不足やエラーを成功へ置換しない。
画面の[DONE]はモデル研究結果が保存できた意味で、収益性や実約定の証明ではない。

コマンド起動する場合：

```powershell
py -3.12 orrery_research_session.py --config "$env:LOCALAPPDATA\ORRERYFX\research\settings\session.local.json"
```

## 出力と失敗時

固定の`%LOCALAPPDATA%\ORRERYFX\research`配下に保存する：

- `runs/<run-id>/`：既存workerが保存する取得・比較結果。
- `sessions/<session-id>/session_status.json`：この一括処理の段階とrun-id。
- 同フォルダーの`receipt.json`：workerが返した記録を、監査前に新規保存。
- `summary.json`：再監査後の許可項目だけの要約。監査停止ならaccounts=null。
- `session_complete.json`：監査成功・保存hash照合後だけに書く完了marker。

workerが停止した場合は`WORKER_STOPPED`で、停止理由はreceiptの固定コードを参照する。
receiptを得られない例外・保存不整合は`SESSION_FAILED`。再監査不成立は`AUDIT_BLOCKED`。
完了markerがない処理を完了扱いしない。途中終了では状態が途中のまま残る場合があり、
自動resumeや成功復元をしない。再実行では別UUIDを作り、上書きしない。
終了コード0=完了、2=記録済み停止、1=一括処理を起動不能。

receiptはworkerの戻り値を、その信頼した完了時点に同じPC上の別フォルダーへ固定するもの。
外部署名・別媒体backupではない。両方のファイルを書き換えられたPC侵害まで保証しない。
receiptとsummaryのSHA256をセッションの状態と完了markerに記録し、標準出力にも返す。
元のrunから後日receiptを捏造し直す機能はない。

検証データはコード配下へ保存しない。CLIでは保存rootが固定で、Python APIもコード内の
runtime指定を拒否する。既存workerの同時実行ロックを再利用する。
新しいセッションが同じ過去期間を検証しても、新しい市場観測として合算しない。

## 閲覧との接続

保存後、既存viewerへ`runs/<run-id>`と`sessions/<session-id>/receipt.json`を指定できる。
画面の自動起動、最新runへの自動切替、Tailscale公開、policy変更、定期実行は行わない。
これはPC操作を減らす一括起動で、利用者のPCですでに処理が走っている意味ではない。

## 検証範囲

模擬DEMOの既存workerから実archive/account/監査を通し、費用未設定、timeout、監査停止、
receipt保存前後の改変、重複実行の非上書き、コード配下保存拒否、未設定templateを検査。
Windows CIでは実CMDとPython 3.12で、空白付きパス・設定不足時の停止・失敗終了コードを
検査する。実MT5 IPCや実市場収益を検証するWindows試験ではない。

PCから離れている間の開発・試験として追加したもので、実端末の初回実行、
費用根拠の設定、Tailscale本人ログインとiPhone接続はまだ利用者側で必要である。
