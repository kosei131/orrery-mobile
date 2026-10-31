# 検証結果の再監査と閲覧用要約 — オフライン実装

`orrery_research_summary.py`は、完了した一括workerの保存結果を、別途保持したworker出力
（receipt）に照合し、個人情報を含めない許可項目の要約を新しいJSONへ出力する。
既存worker・LSR戦略・リスク管理・MT5コードは変更していない。
スマホ画面、ネットワークサーバー、Tailscale、定期実行はまだ導入していない。
利用者のPCへ自動配布・導入したわけではない。

## 実行前提

receiptはworkerが正常完了時に標準出力へ出すJSONを、その時点でrunフォルダーとは
別の場所へ保存したもの。run_idと4つのpin（設定、コードmanifest、capture、account）を
照合基準にする。後からrunフォルダーを読み直して都合のよいreceiptを作らない。
ローカルで双方を書き換えられた場合の認証や、ブローカーの真正性を保証しない。
既存workerはreceiptの自動保管先を作らないため、手元で保存が必要。

PowerShellでの例。既存workerの各引数は実際の値を指定し、receiptには新しい保存名を使う：

```powershell
py -3.12 orrery_research_worker.py --config SETTINGS_FILE --code-manifest MANIFEST_FILE --code-manifest-sha256 RETAINED_CODE_PIN | Set-Content -Encoding utf8 RECEIPT_FILE
```

UTF-8とUTF-8 BOM付きreceiptに対応する。旧PowerShellの`>`が生成しうるUTF-16は対象外。
worker停止・失敗のreceiptから完了要約は作らない。
既存の版に新しいPythonを追加するとコードinventoryが変わるため、実行時は信頼した
新しい配布物全体を確認し、新しいコードmanifestを保持する。過去実行の古いpinを
新しいコードに合わせて変更しない。過去結果の監査は保存済みmanifestを参照する。

## 再監査

```powershell
py -3.12 orrery_research_summary.py --run RUN_UUID_DIRECTORY --receipt RECEIPT_FILE --output NEW_SUMMARY_JSON
```

保存先の親ディレクトリーは事前に用意し、新規ファイル名を指定する。
runは`%LOCALAPPDATA%\ORRERYFX\research\runs\<UUID>`。
出力はrunフォルダー外のローカル要約専用フォルダーを推奨する。
既存の要約や生データは上書きしない。runフォルダー全体を公開しない。

確認内容：

- receiptとstatus・job_completeのUUID、COMPLETED_RESEARCH、4つのpin、研究専用Falseフラグ。
- 保存された設定とコードmanifestのhash・申告revision。コードが実行されたことの証明ではない。
- capture marker・固定名3ファイルのhash、capture/stage/account設定とworker固定設定の一致。
- account markerの入力capture/catalog pin・出力3ファイルのhash・評価の前提とFalseフラグ。
- sequence・M5入力hash、候補期間、数量仕様、明示費用・SL/TP条件の一致。
- 実際のティックarchive/catalogを読み直し、既存の全期間品質監査を再実行。
- 保存済み確定取引台帳から勝敗・平均R・PF・純損益を再集計し、保存済み統計と照合。
- 長い読み込み後に主要pinと完了状態を再確認。ファイル全体の原子的snapshotではない。

MT5への接続や注文はしない。ブローカー損益計算、SL/TP約定、口座DDの再シミュレーション
は行わない。価格履歴の真正性、歴史的仕様、費用やrollover除外の主張は未認証。
損益・DDは既存モデルの記録値で、今回の監査を市場利益の証明へ読み替えない。

## 出力

成功時：`audit_status=CONSISTENT_RESEARCH_ARTIFACTS`。
2方式CONFIRMATION/RETESTを独立口座として表示するためのJSONで、2口座の損益を合算しない。
候補母数、方式ごとの見送り件数、確定取引数、勝敗、平均R、PF、残高・評価額の変化、
サンプル時点の最大DD、未決済0/1件、日次/連敗停止の記録を含む。
勝率は0〜1の`win_rate_fraction`。取引ゼロなら勝率・平均R・PFはnullのまま。
PFの分母となる損失がゼロの場合も既存集計と同じnullで、無限の優位性とはしない。
未決済を勝ちへ変換しない。recorded_stage_updated_at_utcは段階の記録時刻でheartbeatではない。

許可した数値・固定状態・検証済み形式のUUID/時刻/revisionだけを新規構築する。
口座番号、server、Windowsパス、ログ、例外、自由記述source/caveat、ポジションID、
アカウントscope hash、設定内の端末パスをそのまま転送しない。
`pnl_recomputed=false`、`worker_liveness_verified=false`、`code_execution_attested=false`と
既存の実注文/市場優位性/6か月完了/歴史的仕様/費用確認のFalseを保持する。

監査不成立時：`AUDIT_BLOCKED`、`accounts=null`。損益を0で補完せず、エラー詳細やパスも
出力しない。CLI終了0は要約成功、2は監査停止の要約を保存、1は読み書き/引数等で保存不能。
監査成功の古い要約を現在の稼働状態と誤認しない。公開サーバーは後工程。

## テストと次工程

模擬DEMOで既存capture→archive→account→workerの経路を作り、receipt照合、
欠けた完了marker、FAILED状態、hash/生tickの変更、コードpin不一致、費用・安全フラグ・
勝率の不正、非有限値、自由記述の個人情報除外、未決済の保持、UTF-8 BOM、上書き拒否を検査。
保存台帳の損失と利益を両方含む再集計例も確認する。実市場成績のテストではない。

次はこの要約を読む認証付きローカル閲覧APIとスマホ画面。
実機への初回導入・根拠ある費用設定・worker実行は引き続き必要である。
