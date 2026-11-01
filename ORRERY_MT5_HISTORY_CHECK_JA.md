# MT5デモ履歴の短時間取得確認

手数料・スリッページを仮定せず、直近10分のBid/Askを取得・保存する独立入口。
既存の戦略・pilot・発注設定は変更しない。収益計算は実施しない。

Windowsでこの追加ファイルを含む版を展開し、そのフォルダーのPowerShellから実行する。
以前のZIPにはこのファイルがないため、以前の版で実行しても動かない。

```powershell
py -3.12 orrery_mt5_history_check.py
```

起動済みMT5のデモ口座を確認し、現在UTCの2分前を終点として10分間を要求する。
実口座・取得失敗・空データ・上限到達・口座/銘柄仕様変更は停止する。
土日・休場中も空データを成功に変えず、別期間へ自動置換しない。
initializeの接続待ちは30秒指定だが、履歴取得自体の強制タイムアウトは未実装。

保存先は `%LOCALAPPDATA%\ORRERYFX\history-checks\<新規UUID>`。
既存のread_ticks / save_tick_archive / verify_tick_archiveを再利用し、
request.json、archiveのティック・監査結果、最後にhistory_check.jsonを保存する。
口座番号・サーバー名・パスワードは保存しない。個人用ローカルファイルであり、
スマホ同期・遠隔操作・定期実行・Windows ACL設定は行わない。

requestには取得/監査関連6ファイルのバイトSHA-256を記録する。
receiptにはrequestとarchiveのピンを記録する。署名・全依存関係の実行証明ではない。
receiptがないフォルダーは未完了。品質BLOCKEDは証拠を保存して終了コード2、
その他の例外は詳細や個人情報を表示せず終了コード1。

診断閾値はスプレッド100 points、価格更新間隔60秒。売買許可閾値ではない。
銘柄/時刻の実際のスプレッドによりBLOCKEDとなり得る。
セッションカレンダー未確認のため、休場と欠損は確定分類しない。
HISTORY_SAVED_REVIEW_REQUIRED（終了コード0）でも完全性・backtest_readyはfalse。
取得成功は6か月履歴の確保、鮮度保証、取引コストの確認や利益の証明を意味しない。

この入口のWindows MT5実機実行は未確認。自動テストは模擬MT5のみ。
