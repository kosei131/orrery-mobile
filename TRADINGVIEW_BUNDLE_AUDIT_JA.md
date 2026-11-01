# TradingView受領ZIPの取込監査

orrery_tradingview_bundle_audit.pyは、PCで保存したOANDA:XAUUSDの
5m.csv / 15m.csv / 4h.csv、対応する3つの_time_gaps.csv、manifest.json、README.txtを
持つZIPを読み取り、計算前のデータ整合性を検査する。ZIPを展開・実行しない。

    python orrery_tradingview_bundle_audit.py received.zip --output input-audit.json

出力は新規ファイルのみ許可。元ZIPを変更しない。ZIPと足CSVのSHA256を記録する。
重複名・予期しないメンバー・暗号化・過大サイズは拒否。
足CSVは列名、整数UNIX秒とISO UTC秒の一致、確定時刻、昇順・重複、有限OHLCVを検査する。
空行は本数から除外し、除外した行数を明示する。manifestの件数・期間も実CSVと照合する。
gap CSVやREADMEの記述だけで価格品質を認証せず、営業日カレンダーともみなさない。

5m→15m、15m→4h、5m→4hについて、親足の公称区間を下位足が完全に覆う場合だけ
DecimalでOHLCを比較する。外側期間と下位足不足は未検証として別々に数える。
ファイル全体の重複期間と、3時間足共通期間の両方を出力する。
一部の一致をもって全期間が整合したとは扱わない。
公称4時間以外の時刻差も検出するが、DST・短縮セッション・誤記のどれかと断定しない。
価格差は元データと集計値の両方を残し、修復・補間・差し替えをしない。

常にcandidate_replay_allowed=False、execution_allowed=False、actual_profit_usd=None。
銘柄名・出所は申告の照合であり、TradingViewサーバーからの応答認証ではない。
今回の機能は通常足の真正性、セッションの正確な境界、Bid/Ask、履歴USD評価や費用を証明しない。
既存のorrery_tradingview_studyの連続性・2000本制限を緩めるものではない。
LSR02/VHF03の再生、HalfTrend/Reversal/未定義2.6統合、6か月検証、損益計算は別工程。
既存構造SL、リスク制限、日次境界、発注禁止は変更しない。

10件の合成テストで、3時間足一致、妥当なOHLC同士の不一致、下位足不足、
2形式の時刻矛盾、非有限価格、申告件数/銘柄相違、ZIP異常、未確定足、空行、
非公称H4時刻差、原本不変と出力上書き拒否を検査する。
実データの取込監査と模擬検査を、収益性の証明やブローカー約定確認とは呼ばない。
