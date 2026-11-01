# 本人のiPhoneへ接続する準備 — 任意のServe専用入口

追加したもの：`orrery_research_tailnet.py`、無効な設定見本、端末制限policy見本、模擬HTTP試験。
既存worker、MT5/LSR戦略、口座リスク、既存8765/8766サーバーは変更していない。
実行済み・実iPhone接続済み・利用者PCへの導入済みではない。

## 接続の形

本人iPhoneのTailscale → PCのTailscale Serve HTTPS:443 → PC内127.0.0.1:8767。
Serve専用入口がHost・HTTPS Origin・本人LoginNameのhashを確認してから、既存の
再監査・専用鍵付き閲覧APIへ渡す。旧画面の防御設定を直接緩める変更はない。
既存の8766は起動しなくてもよい。8767の新入口が同じ保存結果を起動時に再監査する。

公式Serveはtailnet内の接続に利用者identity headerを追加し、クライアントが送った
同名headerを除去する。Funnelやtagged deviceではこの本人headerは利用できない[1]。
そのためそれらをこの入口へ通す設定は採用しない。
ネットワーク内の他人を含めた共有を許可しない。iPhone限定は別途policyで指定する。

この入口は127.0.0.1のみで待ち受ける。localhost上の悪意あるプロセスはheaderを
偽装できるため、PC侵害まで防ぐものではない。ownerのhashは暗号化や匿名化ではない。
HTTPS証明書・ネットワーク認証はServeが担当し、このPython自体はTLSサーバーではない。
本人headerを確認しても、APIには別途従来の専用閲覧鍵が必要。

## PC・iPhone側の初回操作

1. Windows/iPhoneへ公式Tailscaleを導入し、同じ本人アカウントでログインする。
   本人認証・MFA・OS許可は利用者が行う。GitHubやこのチャットへ認証情報を送らない。
2. 管理画面でPC・iPhoneの登録を確認する。PCの完全な`machine.tailnet.ts.net`名、
   両端末のTailscale IPv4を手元で確認する。LANの192.168系IPとは別物。
3. 既存policyとServe設定を確認する。PowerShellでTailscaleの実際のCLIパスを使う：

```powershell
& 'C:\Program Files\Tailscale\tailscale.exe' serve status
```

既存の443番ServeやFunnelがあれば、この手順で上書きせず先に用途を確認する。
同じ端末を他サービスで使用している場合、以下のpolicy見本で全体を置換しない。

4. `research_tailnet_policy.example.json`をGit管理外へコピーし、hostsの2つのIPを
   実値へ置換する。これは専用の本人tailnet向けの候補で、本人iPhone→PC TCP443のみ。
   8765/8766/8767へネットワークから直接接続する許可は追加しない。
   管理画面で既存policyを保存してから候補全体をレビューし、policyテストを実行する。
   **このファイルを既存allow-allへ追記するだけでは制限にならない。** ACL/grantsの
   他の広い許可も確認する。既存サービスがあるtailnetでは影響を確認してから個別調整する。
   別端末から443へのdeny試験も追加できる場合は追加し、実機で拒否を確認する。
   実policyの保存・変更をこのチャットから自動実行はしない。[2][3]
5. `research_tailnet_settings.example.json`を本人専用のローカルフォルダーへコピーする。
   `public_host`へPCの完全なDNS名のみを小文字で入力（https://や末尾スラッシュなし）。
   `allowed_login_sha256`は実際のTailscale LoginNameのSHA256。
   表示名を推測して代用しない。ASCII LoginNameのみ対応、不明なら実行を止める。
   以下を実行すると入力を伏せたままhashだけを取得できる：

```powershell
py -3.12 -c "import getpass,hashlib; print(hashlib.sha256(getpass.getpass('Tailscale LoginName: ').encode('ascii')).hexdigest())"
```

6. 条件を確認して設定の`enabled=true`へ変更する。既存workerを実データで実行し、
   runと別途保持したreceiptを準備する。費用未設定を0で埋めない。
   今回の新しいPythonファイルを含める配布物の確認・コードmanifest更新も必要。
   過去実行のpinは新しい版に合わせて書き換えない。
7. 新入口を起動する。大文字は実際のパスへ置換する：

```powershell
py -3.12 orrery_research_tailnet.py --run RUN_UUID_DIRECTORY --receipt RECEIPT_FILE --token-file PRIVATE_KEY_FILE --config PRIVATE_TAILNET_SETTINGS_JSON
```

鍵ファイルは以前のviewerと同じものを使える。親フォルダーを用意しWindowsのアクセス権を
本人に限定する。設定が不正なら起動しない。直接localhost:8767を開いたときの403は、
Serveの本人headerがないための正常な拒否。

8. 別のPowerShellで、初回は前面でServeを開始する。必要なHTTPS許可画面を本人が確認する。

```powershell
& 'C:\Program Files\Tailscale\tailscale.exe' serve --https=443 http://127.0.0.1:8767
```

一般公開のFunnelコマンドは使わない。ファイル/フォルダー配信にも切り替えない。
Serveの実際のHost転送が設定したDNS名と一致しない場合は拒否する。Hostを無条件許可へ
変更せず実機で転送仕様を確認する。公式公開ソースのTCP proxyでは入力Hostを保持する実装を確認した[5]。
導入した実バージョンでの接続試験はまだ行っていない。

9. iPhoneでTailscale接続をONにし、Safariで`https://実際のPC完全DNS名`を開く。
   専用閲覧鍵を入力する。鍵をチャットやGitHubへ送らない。
   Wi-Fiと携帯回線で、鍵あり/なし、Tailscale OFF、別人・別端末拒否を確認する。
   未確認なら接続成功と報告しない。

## 停止・復元

Serveだけを止めるコマンド（全サービスのresetは使わない）：

```powershell
& 'C:\Program Files\Tailscale\tailscale.exe' serve --https=443 off
```

新入口のPowerShellでCtrl+C。必要なら保存した旧policyへ管理画面で復元する。
初回手順では`--bg`を指定しない。公式には`--bg`で再起動後もServeが再開するため、
継続公開を意図せず有効にしない[4]。Serveを止めてもworkerやMT5は別のプロセスである。
PC再起動/ログオフ後の再開、定期タスク、heartbeatはまだ導入していない。

## 検証の位置づけ

テストは、模擬DEMOで作った保存結果と模擬Serve headerを使う実HTTP通信。
本人確認と閲覧鍵の両方、Host/Origin拒否、別人・欠けたidentityの拒否、未設定停止、
loopback bind、任意ファイル参照拒否を確認する。Tailscaleの実ネットワーク、TLS証明書、
管理policyの適用、iPhone実機、利用者PCの導入は未確認。

このコードはTailscaleの導入・サインイン・policy変更・Serve起動を自動では行わない。
まずPC上の一括実データ検証とローカルviewerを成功させ、その後この手順で実機接続する。
これまでと同じ固定snapshotで、再表示しても新しい検証や現在のworker状態を取得しない。
本番発注・デモ発注・リアル口座接続は追加していない。

## 一次資料（2026-10-28確認）

[1] https://tailscale.com/docs/features/tailscale-serve

[2] https://tailscale.com/docs/reference/examples/acls

[3] https://tailscale.com/docs/reference/syntax/policy-file

[4] https://tailscale.com/docs/reference/tailscale-cli/serve

[5] https://github.com/tailscale/tailscale/blob/main/ipn/ipnlocal/serve.go

確認したsource blob SHA：2093d75949473ed0135c7f1249615a4b64424fe6。
これは調査時の公開ソースで、利用者のインストール済み版の証明ではない。
