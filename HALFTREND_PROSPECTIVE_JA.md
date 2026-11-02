# HalfTrendの事前固定・追加期間研究

目的は「確定M5 RETEST時のHalfTrend方向一致群が、同じLSR02候補全体より
費用前の価格参照結果を改善するか」を別期間で調べること。1設定のみを固定し、
方向不一致/初期化不足/VHF03も全件報告する。逆方向売買や条件最適化はしない。

## 固定計画

`research_evidence/local-history-20261101/halftrend_prospective_plan_20261102.json`

SHA256: `580ec6b919f6da6e9adb8b0973f89f3af2112000dce56ca559899bd10803c434`

対象はUTC 2026-11-03 00:00〜2026-12-01 00:00（HST 11/2 14:00〜11/30 14:00）。
これは28日の予備研究であり、6か月検証を置き換えない。期間到来前の結果は作らない。
LSR02/VHF03の既存設定、HalfTrend amplitude2/channel2/ATR100、SL/TPと
連続窓ごとの初期化を維持。2R参照は2.6の定義ではない。
ローカルPython依存をASTで再帰的にたどり、実装40ファイルのhashを固定した。
GitHubのcommit記録が外部の固定時刻証拠となる。JSON中の自己申告時刻だけで
事前登録や未閲覧を証明したとは扱わない。

## 追加データが得られた場合

受領形式は既存TradingView監査の8ファイルZIP。
OANDA:XAUUSD via TradingView MCP、標準4H/15m/5m、UTC、確定足と
manifest内の件数/時刻をそろえる。評価共通期間が上記範囲内にあるものを指定する。
以前の文脈足を含めても既存studyは共通期間以前へwarmupしない。
出典ZIPの真正性・セッション/欠損の完全性は別途必要。

```
python orrery_halftrend_holdout.py --plan research_evidence/local-history-20261101/halftrend_prospective_plan_20261102.json --plan-sha256 580ec6b919f6da6e9adb8b0973f89f3af2112000dce56ca559899bd10803c434 --zip NEW.zip --zip-sha256 NEW_ZIP_SHA256 --output NEW_RESULT.json
```

新しい出力先だけに保存する。計画/ZIP pin不一致、コード/設定変更、既存探索ZIP、
共通期間の範囲外、未来cutoffを拒否。検証器内で転送/ダウンロード/PC接続はしない。
コードを修正した場合、旧計画を黙って再利用しない。新仮説と別の将来期間を再固定する。

入力が期間の一部だけならpartial_period=true。端点が一致しても完全なセッション収録とは
限らずcomplete_session_coverage_verifiedはfalse。複数の結果は自動合算しない。
重複期間や重複候補を含むZIPの結果を単純合算してはならない。
既存audit/replayのZIPサイズ/行数/計算量制限は維持し、今回6か月一括再生には拡張しない。

出力は探索時の全群集計と追加期間の全群集計を並べて保持。
時間的適格性は未閲覧の独立性証明ではないためindependent_holdout_verified=false。
費用/BidAsk/スワップ・履歴USD評価/口座停止条件の適用は未完で、
純期待値・口座利益率/DD・実損益はnull。Reversal04/LSR01独立経路/2.6は未評価のまま。
採用判定は常にHOLD_NO_AUTOMATIC_ADOPTION。取引数が増えても自動採用しない。

## 今回の結果

追加期間データは未取得。既存ZIPを投入して拒否を実測し、readiness JSONへ保存。
候補数を0とせずnullで記録した。模擬検査は1970年の人工OHLCを使用し、実損益に転用しない。
Python全1,055件中1,050成功・5skip・失敗0。新規8テスト。
ユーザーPC/MT5の操作、注文、課金、マージ、配備は実施していない。
