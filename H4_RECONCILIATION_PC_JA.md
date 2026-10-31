# PCでのH4照合準備

計画作成と、明示実行専用のデモ取得アダプターを用意。実機取得は未実施。
最新ブランチのソースがあるフォルダーの通常PowerShellで次を実行する。
古い672d50のZIPにはこの追加ファイルがないため、同じコマンドを実行しない。

```powershell
& "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe" orrery_h4_reconciliation_plan.py --output h4-reconciliation-plan-01
```

新規フォルダーにrequest.jsonとSHA256付きreceipt.jsonを保存する。
19枠を重複なしで記録し、既存check_historyの上限に合わせ10分ずつ456区間へ分割。
これは取引所休場の確定や実取得成功を意味しない。空の区間を勝手に正常休場と扱わない。
既存出力への上書きは拒否。再実行時は別の新規フォルダー名を指定する。

追加した取得アダプターでは、通常Windows Python3.12・MetaTrader5パッケージ・
デモ口座の一致を毎回確認してから、既存orrery_mt5_history_check.check_historyを
各区間へ適用する。実口座なら停止。飽和・取得失敗・空履歴では成功扱いしない。
既存check_historyの同一呼出し前後の照合に加え、追加バッチは当初の口座と仕様を固定し、
途中経過と最終結果を保存する。中断後の再開は未実装。
M1照合・ブローカーH4境界・営業日程との比較も後工程。

456区間の所要時間や取得可能性は実機未測定。実行準備ができるまでは
PC不在で履歴取得が進んでいるとは報告しない。発注は無効。

## 一括取得アダプター（追加）

orrery_h4_reconciliation_batch.pyを追加。--executeなしは計画の照合だけでMT5をimportしない。
--executeを明示した場合のみ既に起動済みのWindows MT5へ接続する。
既定は先頭1区間。--max-chunksは1〜456で、指定範囲は常に先頭から。
途中再開・区間の任意飛ばし・並列取得は未実装。出力フォルダーは毎回新規にする。

```powershell
$orreryReceipt = Get-Content .\h4-reconciliation-plan-01\receipt.json -Raw | ConvertFrom-Json
& "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe" orrery_h4_reconciliation_batch.py --plan .\h4-reconciliation-plan-01\request.json --plan-sha256 $orreryReceipt.request_sha256 --output h4-intake-check-01
```

この例は計画照合のみ。実取得する際は、デモ口座・対象・範囲を確認して同じコマンドに
--execute --max-chunks 1を追加する。成功も取得範囲の完全性・収益性を意味しない。
複数区間を処理する場合はmax-chunksを明示する。全456区間の所要時間は未測定。
各区間の前後で当初のデモ口座・銘柄仕様と照合し、不一致・品質停止・空履歴・例外で即停止。
既存取得物を残し、成功区間ごとのprogressと最後のbatch_resultを別々に保存する。
口座番号やサーバー名は出力へ保存しない。失敗理由の生例外も公開しない。
空履歴は正規休場の可能性もあるため原因未確定として停止し、穴埋めや自動スキップしない。
プログラム強制終了時はbatch_resultがない可能性がある。progressだけを全件完了扱いしない。
実機接続・実取得・自動再開・M1照合は未検証/未実装。
