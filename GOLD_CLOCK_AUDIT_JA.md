# XAUUSD セッション時計の監査

Dukascopyの公表セッションはNY現地18:00〜翌17:00、毎日17:00〜18:00休止。
現在資料であり、過去の全営業日・例外を認証したものではない。夏時間はIANA
America/New_Yorkを使用する。2025年3月のDukascopy通知でもXAU/USDへの夏時間適用を確認。
https://wiki.dukascopy.com/en/manuals/jforex4-desktop/trading-sessions
https://www.dukascopy.com/europe/english/about/ournews/daylight-saving-time-2025-in-the-us
US祝日の短縮取引は別途照合が必要。
https://www.dukascopy.com/swiss/english/forex/forex-trading-accounts/link/

| 品質監査済みペアの診断 | 2025年Q4 | 2026年1月〜10月19日14:00 UTC |
|---|---:|---:|
| 営業時間内観測 | 89,091分 | 282,761分 |
| 営業時間内未観測 | 1,929分 | 3,799分 |
| 公表休場枠の未観測 | 41,460分 | 133,320分 |
| H1厳密連続の最長 | 23本 | 23本 |
| 間の全分が休場なら継承するH1最長 | 961本 | 825本 |
| 同継承条件でのH4最長 | 5本 | 5本 |
| 全予定営業分を観測した部分UTC H4 | 73枠 | 234枠 |

H1の毎日リセットは営業時計で改善できる。一方、毎日休場を含むUTC H4には3時間等の
実際の営業時間が含まれるため、完全4時間足を省略して繋ぐと営業時間内の価格も飛ばす。
今回H4が継承できない理由はこの部分足の欠落。部分足を含む別集約は別定義として評価する必要がある。

株式等の祝日カレンダーをXAUの全履歴に自動適用しない。欠損と短縮営業の認証は未完。
本変更はカバレッジ診断。戦略損益は再評価しておらず、勝率・利益率の改善値は未算出。
原本のSHA256は既存の読込器で照合済み。価格補間は行わない。

再現は `python orrery_gold_clock_audit.py ARCHIVE_2026 ARCHIVE_2025_Q4 NEW_OUTPUT.json`。
証拠は `research_evidence/local-history-20261101/gold_clock_audit_summary.json`。
