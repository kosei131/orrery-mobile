# ローカル分析アプリのGitHub引継ぎ

基点: research/mt5-candidate-history-probe の af93769001ada0cd19c08d8d64532294453824c6。
GitHubからfetchし、既存HEADと一致することを確認して新しい研究ブランチを作成した。
既存ブランチの上書き・本番マージは行わない。

## 実行環境

作業フォルダー:
`C:\Users\sanna\OneDrive\Desktop\orrery-mobile-672d50f1cda96de31c1a761fb66c90c2d50e4858\research-resume-checkout`

Python 3.12.14:
`C:\Users\sanna\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe`

Git 2.53.0.windows.3:
`C:\Users\sanna\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\git\cmd\git.exe`

上記Python/Gitは既存の同梱実行ファイル。追加インストールなし。
未コミット変更と取得済みCSVを、元チェックアウトと同階層の
`handoff-backup-20261101` にコピーして保護した（.gitと__pycache__を除く）。

## 引き継ぐものとローカルに保持するもの

分析コード、起動スクリプト、追加テスト、CIへのテスト登録、手順書を保存する。
research_evidence/local-history-20261101 のJSONは公開履歴のhashと監査・比較結果。
口座情報・MT5資格情報・一時アクセストークンを含めない。

生CSV、集約CSV、作業ログはローカルの research_artifacts_20261101 に保持し、Git対象から除外。
従って新規cloneだけでは実公開履歴画面は起動しない。
このPCでは既存CSVが残っており START_HISTORY_RESEARCH.cmd で起動できる。
模擬画面だけなら `python mt5_local_dashboard.py --test-data` で起動可能。

## 別PCでの公開履歴の再現

Python 3.12とPowerShellがある環境で、チェックアウトのルートから実行する。
下記は新しいフォルダーに対して一度だけ実行し、既存データを上書きしない。
ダウンロードは利用者が明示実行する無料の公開CSV取得だけで、MT5に接続しない。

```powershell
New-Item -ItemType Directory research_artifacts_20261101 -ErrorAction Stop
Invoke-WebRequest 'https://raw.githubusercontent.com/getdata-finance/xauusd-1m-ohlcv-metals-historical-data/main/XAUUSD_1m.csv' -OutFile research_artifacts_20261101/xauusd_public_m1.csv
Get-FileHash research_artifacts_20261101/xauusd_public_m1.csv -Algorithm SHA256
```

当時のSHA256は a587597bbf88c2d868a00a4e0019cd705cee6ca4f20b0485d6b745f19fcc8225。
提供元の更新でhashが異なる場合、当時の結果の再現とは扱わず、別の研究runで監査する。
当時と同じファイルを確保した場合:

```powershell
python orrery_public_xau_to_bars.py research_artifacts_20261101/xauusd_public_m1.csv --out research_artifacts_20261101/public_xau_bars
python orrery_history_app.py --bars research_artifacts_20261101/public_xau_bars --source research_artifacts_20261101/xauusd_public_m1.csv --output research_artifacts_20261101/lsr02_vhf03_crosschecked_history.json
python mt5_local_dashboard.py --history-dir research_artifacts_20261101/public_xau_bars --research-results research_artifacts_20261101/lsr02_vhf03_crosschecked_history.json
```

## 検証範囲

全体単体テスト、認証HTTP、安全ゲート、Chrome描画・polling、実CSVと実ローカルサーバーの
ブラウザー検査を再実行してからコミットする。環境前提のskipは成功に数えない。
実MT5接続・注文・費用込み優位性・未使用期間評価は未検証のまま。
候補0件を勝率0%や損失0と読み替えない。詳細は HISTORY_RESEARCH_VERIFICATION_JA.md。
