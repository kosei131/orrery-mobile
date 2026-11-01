# 05観測履歴の保存と再起動後の再生検査

独立した研究API `lsr05_observation_store.py`。
既存のJSON読込/新規保存、worker_lock、SignalJournal、HalfTrendObserverを再利用する。
MT5接続・発注・戦略条件は変更しない。GPL-3.0表示と原典COPYINGを維持する。

```python
from lsr05_observation_store import create_store, append_snapshot, restore_store

receipt = create_store(new_private_folder)
# receiptのhead_sha256を、ストアとは別に保持する。
saved = append_snapshot(new_private_folder,
    expected_head_sha256=receipt['head_sha256'], snapshot=halftrend_snapshot,
    symbol='XAUUSD', observed_at=received_time,
    data_source='documented_feed', implementation_version='retained_revision')
# 保存成功後、新しいsaved['head_sha256']を最新の保持pinとする。
restored = restore_store(new_private_folder,
    expected_head_sha256=saved['head_sha256'])
```

## 保存構造

新規の専用フォルダーだけを作成し、既存フォルダーへ上書きしない。
初期設定store.jsonに、形式・上限・observer/SignalJournal/保存モジュールのソースhashを保存。
WindowsのCRLF/LF差はソースの改行を正規化して扱う。
これは3ファイルの照合であり、全依存関係や実行環境の署名証明ではない。

各batch-000000等へ次を保存する。

- request.json：受信したsnapshotと、観測時刻・データ元・実装版。
- result.json：既存observerが返した観測イベント。
- complete.json：前のhash、連番、入力/結果hash。最後に保存する完了marker。

head_sha256は最新完了markerのhash。空ストアではstore.jsonのhash。
別途保持した最新pinが必要で、ディレクトリーから再計算した値だけを信用しない。
新しいpinを別に保持する処理や、その保存先の権限設定は接続側の責務。
ログと保持pinの両方を改変できる侵害、ブローカーの真正性まで保証しない。

## 再起動後の確認

restore_storeは全batchを順に読み、hashと前のmarkerへの鎖を検査する。
新しいSignalJournalとHalfTrendObserverへ元入力を順に渡して再生し、
保存結果とバイト単位で一致することを確認する。
計算の内部変数をpickle等で直接復元しない。
append_snapshotも毎回この再生検査を行うため、再起動後も過去の変更検出状態を引き継ぐ。
同じsnapshotを読み直してもサイン観測件数は増えず、受信時刻の更新は再現する。
ただし保存batch数は増える。batch数を取引数/新サイン数として扱わない。

ソース版が変わった場合は同じストアとして復元しない。
移行は別の明示的工程とし、古い記録を新しい計算で上書きしない。

## 停止条件

専用フォルダーの既存worker.lockを使い、書込/読込中は単一の所有者に限定する。
保持pinが古い、batchの欠落/並べ替え/改変、予期しないファイル、結果の再生不一致、
上限超過では停止する。シンボリックリンクのroot/batch/metadata/lockも拒否する。
同時に外部プロセスがファイルを置換する攻撃全般に対するトランザクションではない。

保存途中のbatchが残った場合は、そのtailを勝手に捨てて続行しない。
復元も新規追記も停止し、成功扱いにしない。自動修復/自動tail切捨ては未実装。
各ファイルは既存のexclusive writerでflush/fsyncし、完了markerを最後に保存する。
OS/ディスクの全障害に対する完全な耐障害性を証明するものではない。

初期上限は1000batch、10万イベント、全記録64MiB、再生する入力行合計50万。
上限で停止し、古い記録を自動削除しない。
全snapshotを保存する単純な方式なので、長時間の高頻度記録では容量が増える。
差分圧縮・自動ローテーション・連続無人運転は今回未実装。

## 未検証との境界

保存成功は、観測結果を保存/再生できた意味に限る。
DISABLED/履歴なしの受信も状態記録として保存できるが、有効な売買サインとは数えない。
実際の未確定足の瞬間的変化、未観測時刻の変更、取引休止と欠損は解決しない。
nonrepainting_verified / market_edge_verified / execution_allowedはfalseのまま。
MT5からの自動snapshot取得・スマホ表示・TradingView値の照合は未接続/未実施。
今回の確認は模擬OHLCと障害注入テストで、実機の継続稼働試験ではない。

次の独立課題は、営業カレンダーで確認した休場と未知の欠損を区別して、
M15のATR100本を含む計算履歴を扱う設計/検証。未知のギャップを暗黙に通過させない。
