# PCでのH4照合準備

今回はオフライン取得計画の作成まで。MT5接続・履歴取得は実行しない。
最新ブランチのソースがあるフォルダーの通常PowerShellで次を実行する。
古い672d50のZIPにはこの追加ファイルがないため、同じコマンドを実行しない。

```powershell
& "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe" orrery_h4_reconciliation_plan.py --output h4-reconciliation-plan-01
```

新規フォルダーにrequest.jsonとSHA256付きreceipt.jsonを保存する。
19枠を重複なしで記録し、既存check_historyの上限に合わせ10分ずつ456区間へ分割。
これは取引所休場の確定や実取得成功を意味しない。空の区間を勝手に正常休場と扱わない。
既存出力への上書きは拒否。再実行時は別の新規フォルダー名を指定する。

後続の取得アダプターでは、通常Windows Python3.12・MetaTrader5パッケージ・
デモ口座の一致を毎回確認してから、既存orrery_mt5_history_check.check_historyを
各区間へ適用する。実口座なら停止。飽和・取得失敗・空履歴では成功扱いしない。
既存check_historyは同一呼出し前後の口座/仕様を照合するが、複数呼出しをまとめる
バッチ実行側の口座固定・途中経過・再開・最終照合はまだ実装していない。
M1照合・ブローカーH4境界・営業日程との比較も後工程。

456区間の所要時間や取得可能性は実機未測定。実行準備ができるまでは
PC不在で履歴取得が進んでいるとは報告しない。発注は無効。
