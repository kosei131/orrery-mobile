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

## 明示的な複数ZIPレビュー（任意・独立窓研究）

`orrery_halftrend_holdout_batch.py`は保存結果JSONの数字を足さず、指定した元ZIPを
同一の固定計画で再検証する。既存の単体runが自動合算される変更ではない。
元ZIP SHA256、共通評価期間の重複、候補ID重複を拒否。内容が同じでZIPの
READMEだけ異なる再梱包も、共通期間が重なれば再生前に拒否する。
境界は半開区間として扱い、前の終了時刻＝次の開始時刻の隣接を許可。

最大8 ZIP、1個16MiB、合計32MiB。既存の各ZIP監査/計算量制限も維持。
manifestは`[{"zip_path":"NEW_A.zip","zip_sha256":"..."}, ...]`形式で、
manifest自体もSHA256で固定して指定する。

```
python orrery_halftrend_holdout_batch.py --manifest bundles.json --manifest-sha256 MANIFEST_SHA256 --plan research_evidence/local-history-20261101/halftrend_prospective_plan_20261102.json --plan-sha256 580ec6b919f6da6e9adb8b0973f89f3af2112000dce56ca559899bd10803c434 --output NEW_BATCH.json
```

既存LSR02/VHF03/HalfTrend studyを各ZIPで再実行し、候補を並べて既存_summaryと
lsr03_learning_rollup._sequenceで全群を集計。群の事後選別はしない。
ZIP順を入れ替えても時系列に正規化する。ZIP境界では指標/候補状態を持ち越さない。
分割方法で境界付近の候補が変わり得るため、連続一括再生と同等とは主張しない。
未決着を別ZIPの後続足で決着させず、人工的な連結や価格補間もしない。

unsubmitted_common_span_gapsは計画のうち提出された共通期間の外側にある時間。
市場休場・データ欠損の確定ではない。submitted_common_span_secondsも実足の
観測秒数ではなく区間の長さで、内部の穴や正常休場を含み得る。
partial_period=falseでもセッション完全性を証明しない。欠損/費用/未使用独立性の
検証フラグはfalse、純期待値/利益率/口座DD/実損益はnullを維持する。
原計画40ファイルと計画hashは不変。新しい集約器自身のコードhashも出力する。
HalfTrendは比較対象に含むが採用保留、Reversal04/LSR01独立経路/2.6は未評価。

今回は追加実CSV未取得。検査は人工OHLCと人工損失/未決着の入力を使う模擬検査で、
これを新期間の取引件数や利益として報告しない。
取得が必要なのは上記将来期間の同一OANDA提供元の確定4H/15m/5mと、
別工程の口座比較には同一feed整合性を確認できるBid/Ask・仕様・費用・履歴USD評価。
ユーザーPC/MT5にこの環境から接続したことはない。
