# フォルダー移動不要の履歴確認起動

固定版44fe7cbの必要Pythonファイル21個を、既存コードとは別の
`%LOCALAPPDATA%\ORRERYFX\history-check-source\<新規UUID>` に取得する。
全ファイルのSHA-256と構文を検査してから、既存の履歴確認入口を起動する。
口座番号・パスワード入力、pipインストール、常駐、共有、売買は行わない。
現在のWindows Python3.12 / MetaTrader5パッケージと起動済みデモ端末が必要。

以下のPowerShellブロックは作業フォルダーに関係なく使用できる。
起動スクリプトもSHA-256一致を確認する。ブランチ更新で内容が変わった場合は
停止するため、その場合は検証済みの新しい起動指示を使用する。

```powershell
& {
  $ErrorActionPreference = 'Stop'
  $orreryBoot = Join-Path $env:TEMP ('orrery-history-' + [guid]::NewGuid().ToString('N') + '.py')
  Invoke-WebRequest -UseBasicParsing -Uri 'https://raw.githubusercontent.com/kosei131/orrery-mobile/fix/fx-safety-verification/orrery_history_bootstrap.py' -OutFile $orreryBoot
  if ((Get-FileHash -LiteralPath $orreryBoot -Algorithm SHA256).Hash.ToLowerInvariant() -ne 'f1bc55aa8b43f354a024520f38f069e0cb16ad823e5eeeb3040c348db7500f6e') { throw 'Source hash mismatch. Stopped.' }
  py -3.12 $orreryBoot
  if ($LASTEXITCODE -ne 0) { throw 'History check stopped. No successful backtest is assumed.' }
}
```

ダウンロードは1ファイル最大2MiB、HTTPS接続は30秒タイムアウト指定。
履歴確認の子プロセスは120秒で停止する。取得前の21ファイルダウンロードは
その120秒に含まれないため、全体の所要時間を2分以内とは保証しない。
ネットワークの停止、ハッシュ不一致、構文不正で起動しない。
既存ZIP・ユーザーファイルを上書きしない。失敗フォルダーを自動再利用しない。
ダウンロード中断時の部分ファイルは残り得る。

`py -3.12 <起動スクリプトのパス> --verify-only` は取得/検証だけを行い、
MT5へ接続しない。ソースの固定と照合であり、ブローカー履歴の真正性や完全性を
保証するものではない。実機の履歴取得・バックテスト・スマホ閲覧は別工程。

データと品質結果はORRERY_MT5_HISTORY_CHECK_JA.md記載のローカルフォルダーへ保存。
起動スクリプト側には費用仮定や戦略パラメーターを追加しない。
