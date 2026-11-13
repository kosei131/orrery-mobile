# ORRERY FX 再開監査（ハワイ 2026-11-01）

## 環境と継承

元フォルダーは `orrery-mobile-672d50f1cda96de31c1a761fb66c90c2d50e4858`。
`.git` と AUTONOMOUS_FX_DEV_JA.md は存在せず、ブランチ・未コミット差分の確定は不可能。
元ファイルを変更せず、`research-resume-checkout` に研究ブランチを新規cloneした。
取得HEADは `af93769001ada0cd19c08d8d64532294453824c6`。
clone直後はクリーン。既存の自律研究手順書と候補履歴取得・返却照合の説明を読んだ。
PR #6 はopen/draft、baseは research/tradingview-upload-audit。
今回の変更はローカルの新規研究成果のみ。push・merge・配備は実施していない。

## 実取得した公開履歴

既存CIと同じ無料公開CSVを取得した。
出典: https://raw.githubusercontent.com/getdata-finance/xauusd-1m-ohlcv-metals-historical-data/main/XAUUSD_1m.csv

- SHA256: `a587597bbf88c2d868a00a4e0019cd705cee6ca4f20b0485d6b745f19fcc8225`
- M1: 179,662本、2026-03-26 02:28〜2026-09-25 20:44 UTC。
- OHLC検査成功、明示UTCを変換器で確認。重複0、非分単位時刻0。
- 1分超の空白175箇所、最大3,279分。休場と欠損の区別は未認証。
- 完全なM1だけからM5/M15/H4を集約。不完全足は除外、補間なし。
- 公開提供者の価格。ブローカー固有Bid/Ask、約定、歴史的仕様は未確認。
- 要求対象2026-04-28〜10-28のうち149,500本。9月25日以降がないため6か月完了=false。

成果物は `research_artifacts_20261101/`。audit.json、public_xau_bars/report.json、
public_xau_six_month_coverage.jsonを参照。日付範囲だけで完全履歴とは扱わない。

## 今回再実行した既存研究

`reproduce_public_research.py` で既存の14工程を実行、全工程終了0。
コードhashと終了コードを replay_receipt.json、各標準出力を個別logへ保存した。
既存実装・固定パラメーターを変更せず、結果を見て条件を選び直していない。

参考値: 固定SL6、TP2R、仮定スプレッド0.6の既存M1モデルは14件、5勝9敗、
勝率35.71%、合計1.88333R、平均0.13452R、モデル残高DD1.025%。
これらは仮定付き候補の再現値であり、費用込み口座成績や戦略採用根拠ではない。
モデル内の+13.89 USDを実利益と報告しない。
手数料・滑り・持越し費用は未校正、含み損を含む最大DDも未証明。
OHLC内のTP/SL先着順は実ティックで確定していない。
確認直後/リテスト比較も再現したが、期間・TP条件が異なる集計を上記14件と合算しない。

7月1日の既存期間分割は記述的比較に限る。VHF閾値0.50は全体閲覧後のため、
分割後も未使用評価とは呼べない。ADX/EMA/ATRの単体検査は実施したが、
今回の公開履歴について全戦略の同条件純損益比較を完了したとは報告しない。

## 検証とCI

- GitHubの取得HEAD: Actions run 41377236028 が completed/success。
  https://github.com/kosei131/orrery-mobile/actions/runs/41377236028
- ローカル全Python discovery: 968件、failure 3、error 3。
  dashboardのソケット制限、symlink作成のWinError1314、py/curl前提のlauncherが障害。
  個別assertionにはlauncherの期待終了コード不一致もある。全成功とは扱わない。
- 期間ゲート・指標・バリア・費用・候補履歴・M1取込/集約の対象43件は成功。
- test_fx.cjs成功。実MT5、実ブラウザー、Windowsランチャーの動作保証ではない。
- 今回のローカル新規成果に対するリモートCIは未実行。

## 次に必要な工程

判定は BLOCKED（完全履歴・純損益・未使用評価）。注文は一切実施しない。
次の優先工程は不足期間を含む同一feedの長期履歴と、出所・UTC・セッション・
Bid/Ask/費用の証拠を新規保存して監査すること。MT5の端末・口座を自動探索して接続しない。
新規データを閲覧する前に、戦略版、Entry/SL/TP、費用シナリオ、学習/評価境界、
境界を跨ぐ取引の除外、試行数、採否基準を固定する。
既に閲覧済みの期間を未使用として再利用しない。

`execution_allowed=false`、`automatic_orders=false`、`actual_profit_usd=null`。
追加有料サービス・実口座接続・デモ発注なし。
