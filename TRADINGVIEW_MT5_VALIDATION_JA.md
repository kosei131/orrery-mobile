# TradingView過去検証とMT5デモ実践検証

優先目標：現行戦略の仮定付き損益を測り、同じ条件で改良を比較し、その後デモ実約定で照合する。
実口座は禁止。追加の有料プラン/API/データ購入は行わない。

## 今回できたこと

orrery_tradingview_study.pyは、TradingViewの標準ローソク足CSV（4H/15分/5分）を
既存LSR02/VHF03のSweep→構造確認→リテスト候補・構造SL・指定target_rへ接続する。
HalfTrend05の診断CSV取込とは別。今回の口座比較にReversal04/HalfTrend05/未定義2.6は含めない。
将来追加する際は各モジュールON/OFFを固定し、A/B/C/Dの同条件比較として検証する。

time/open/high/low/closeの列は明示的に対応付け、UNIX秒またはタイムゾーン付きISO時刻を使う。
確定前の末尾足は候補判定から除外し、OHLC不正・重複・時系列不整合は拒否する。
CSVの銘柄・提供元・通常チャートであることは呼出側の申告で、CSVから真正性を認証できない。
標準足以外（平均足/Renko等）は対象外。欠損や週末を埋めて連続足にせず、別途セッション照合へ回す。
現行リプレイは各足2000本までの連続区間に限定。6ヶ月全体のセッション対応は未完了。

受領ZIPにはorrery_tradingview_window_replay.pyによる観測連続区間別の参照再生もある。
候補状態を区間間でリセットし、共通期間以前の準備足は使わない別研究パス。
既存build_account_plansのLSR02/VHF03候補を再利用するが、連続した通常戦略の全期間検証とは異なる。
RETEST終値の仮定Entryから費用前の価格Rだけを計算し、口座利益や純期待値はNoneを維持する。
TRADINGVIEW_WINDOW_REPLAY_JA.mdに区間境界・不明結果・未統合範囲の制限を記載した。

取込結果のimport_readinessには、3時間足の期間が重なる開始・終了UTC秒と、
時間足別の全停止理由（時間の空き・2000本超過）を同時に記録する。
期間の重なりは欠損のない共通データや戦略の準備足を保証しない。
期間が重ならない入力はBLOCKED_NO_SHARED_TIME_RANGEで停止する。
各時間足のauditには連続区間数と最長連続本数も含む。週末を正常と自動認定しない。
除外した未確定末尾足までの空きは、確定履歴の欠損数に含めない。
5000本取得できても、3時間足共通で6ヶ月分あるとは限らない。

CSVだけの場合は候補計画までを作り、金額はNoneとして約定用データ不足を明示する。
Python API study(..., account_inputs=...)へ検証済み整合性のBid/Askカタログと
履歴USD評価関数、ロット仕様、費用・滑り条件を明示すれば、既存compare_catalog_accountsで
独立した$3000口座のLSR02/LSR03を比較する。ローソク足からティックを捏造しない。
銘柄・価格提供元と約定カタログのsourceラベル不一致は既存エンジンが拒否する。
ラベル一致だけで同一feedと証明するものではなく、ブローカー仕様・費用の史実性も未認証。

モデル結果に含むもの：終了残高、終了評価額、確定損益USD、未決済ポジション、
勝率、期待値R、PF、観測quote時点の最大DD、連敗数、見送り理由。
現在の研究制限：1銘柄1ポジション、計画リスク0.25%、日次損失1%、3連敗停止。
複数銘柄合算や実際の証拠金・実約定の保証はない。日跨ぎには別途carry/境界quoteの証拠が必要。
verified_profit_usdは常にNone。モデルの利益額を実口座利益や実績利益と呼ばない。

## CSV受領後の実行

TradingView公式では、上部メニューのDownload chart dataでCSVを取得する。
出力範囲はチャートに読み込んだデータに依存する。契約変更や有料化は自動で行わない。
同じ銘柄・同じ提供元・標準ローソク足の4H/15分/5分を使い、撮影日時と設定を保持する。

設定JSONの正確なキーはsymbol/data_source/chart_type/price_basis/time_format/column_map/as_of_s/strategy。
strategyのキーはbuffer/target_r/period/min_vhf/left/right/lifetime。最適値を推測で設定しない。
as_of_sは比較対象のUTC確定時点（整数UNIX秒）、data_sourceは取得元を特定するラベル。
column_mapはtime/open/high/low/closeの5キーを実CSVの列名へ対応付ける。
chart_type=STANDARD、price_basis=BID/ASK/MID/LAST/UNKNOWN、time_format=UNIX_SECONDS/ISO8601。

    python orrery_tradingview_study.py run --m5 M5.csv --m15 M15.csv --h4 H4.csv --settings settings.json --output tv-review-001
    python orrery_tradingview_study.py verify --folder tv-review-001 --receipt-sha256 <出力されたSHA256>

runは新しい出力先のみ許可し、元CSV・設定・結果・hashを保存する。
verifyは外部に保持したreceipt SHAを使い、保存入力から同じ結果になるか再計算する。
CLIは候補計画と不足データの確認まで。USD口座結果のAPI接続には上記Bid/Ask等が必要。

## 改良の比較と採否

1. 戦略版、Entry/SL/TP、コスト、対象期間、時間帯、提供元を固定して現行版を測定する。
2. 改良は1項目ずつ。調整期間と未使用期間を分け、同じ候補母集団・同じ費用で比較する。
3. 勝率だけでなくコスト控除後期待値、利益額/利益率、PF、DD、連敗、回数、未決済と欠損を報告する。
4. 改善しない案は不採用。調整した期間だけで良くなった案は採用しない。
5. 収益データがなければ未実施と書く。過去の公開XAU研究の利益額をTradingView検証結果に転用しない。

## MT5デモでの実践検証まで

既存の事前検査、order_check、安定口座context、永続候補予約を再利用する。
次に候補IDと承認する注文案を固定し、約定照合・応答不明時停止を実装する。
PC接続後、brokerがDEMOを返すこと、USD評価、XAUUSD/USDJPYの実仕様・費用、
ティック取得、SL/TPの受理を読み取りから確認する。その後に段階的な承認付きデモ発注へ進める。
未接続のまま、約定・デモ利益・利確/損切り稼働を主張しない。

## 公式参照

- https://www.tradingview.com/support/solutions/43000537255-how-to-export-chart-data/
- https://www.tradingview.com/pine-script-docs/concepts/strategies/
- https://www.mql5.com/en/docs/python_metatrader5/mt5ordersend_py
