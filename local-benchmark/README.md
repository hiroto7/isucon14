# ISUCON14 ローカル計測・改善

## 条件

Ubuntu 24.04 ARM64 / Multipass / 2 vCPU / 4 GiB RAM / 25 GiB disk。
Goアプリと公式ベンチマーカーを同じVMで動かす。本大会の構成とは異なり、点数はこの環境内で比較する。
構築対象はGo・matcher・payment mockのみ。不要な言語ランタイムのビルドを省略する。
公式コードと構築設定のコミットは `environment.json` に記録する。

## 再構築

```sh
multipass launch 24.04 --name isucon14 --cpus 2 --memory 4G --disk 25G --cloud-init local-benchmark/isucon14-clean.cfg
multipass exec isucon14 -- cloud-init status --wait
```

アプリの性能変更前に構築が正常終了したこと、Go・MySQL・nginx・matcherの起動、ホストとVMのコード一致を確認する。`python3 local-benchmark/tools/deploy.py` で公式Go/SQLを配備・照合する。計測前に `tools/guest-run.sh` を `/home/isucon/guest-run.sh`、`tools/diagnostics.conf` を `/etc/nginx/conf.d/diagnostics.conf` に配置し、nginx設定をテストしてreloadする。

## 計測

```sh
python3 local-benchmark/tools/run_benchmark.py rebuilt-baseline --runs 3
```

各回でGo・matcherを再起動して20秒待ち、60秒の公式負荷走行を行う。静的ファイル検証は省略しない。
`results/<UTC日時>-<段階>/` に生ログ、公式結果の成否・スコア、コードのコミット・差分、SQL集計、リソース情報を保存する。
失敗は `score: null` とし、ベンチが出力した数値があれば `reported_score` に別途保持する。Multipassの一時的な接続失敗は最大3回再試行し、準備失敗は公式ベンチ未実行の失敗として記録して次の試行へ進む。

## グラフ再生成

```sh
uv venv local-benchmark/.venv
uv pip install --python local-benchmark/.venv/bin/python -r local-benchmark/requirements.txt
local-benchmark/.venv/bin/python local-benchmark/tools/plot_scores.py
```

`scores.csv` と `score-history.png` は生データから再生成する。
各回の点、中央値、最小最大を表示し、不採用・失敗も記録する。

## 過去の不採用候補: InnoDBログ同期

`candidates/innodb-flush-log-at-trx-commit-2.cnf` は試験用設定です。現VMでは次の手順で一時設定ファイルを置き、動的変数を切り替えてから公式ベンチを3回実行します。MySQL自体は再起動せず、通常のアプリ再起動と待機条件を保ちます。

```sh
multipass transfer local-benchmark/candidates/innodb-flush-log-at-trx-commit-2.cnf isucon14:/tmp/local-benchmark.cnf
multipass exec isucon14 -- sudo install -o root -g root -m 0644 /tmp/local-benchmark.cnf /etc/mysql/mysql.conf.d/99-local-benchmark.cnf
multipass exec isucon14 -- sudo mysql -e "SET GLOBAL innodb_flush_log_at_trx_commit = 2"
local-benchmark/.venv/bin/python local-benchmark/tools/run_benchmark.py flush-log-2 --runs 3
```

測定ログには各回の前後で `innodb_flush_log_at_trx_commit`、`innodb_buffer_pool_size`、`sync_binlog` を保存します。設定の採否は3回の公式検証と中央値で決め、再起動後にも結果を確認します。

## 改善の判断

最大3サイクル。SQL・HTTP・CPUの実測から一つずつ仮説を選び、3回の公式検証成功と中央値の向上を確認する。
差がばらつきと重なる場合は前後を追加測定し、確認できない変更は戻す。
最後に再起動後の動作・計測も確認する。各段階をローカルコミットに残す。

## 現在の状態

旧VMのMySQL同期候補は不採用。PCクラッシュ後のqcow2破損によりVMを再構築した。新VMの初期3回は中央値4,754、Go接続再利用候補は中央値5,267、ride_statusesインデックス候補は中央値7,271。再起動後の公式検証も成功。詳細は `REPORT.md`。

再構築後の初期3回はすべて成功し、スコア4,754・4,612・4,977、中央値4,754。候補との比較はこの中央値を基準にする。

採用状態はGoの `SetMaxIdleConns(64)` と `ride_statuses(ride_id, created_at)` インデックス。初期中央値4,754からインデックス採用後中央値7,271へ改善。全測定と再起動後検証は `REPORT.md` を参照。

採用状態を再測定する場合は以下を実行する。公式ベンチはVM内の `/home/isucon/bench` を使う。

```sh
local-benchmark/.venv/bin/python local-benchmark/tools/run_benchmark.py restart-check --runs 1
local-benchmark/.venv/bin/python local-benchmark/tools/plot_scores.py
```

## 継続的な診断設定

`tools/pprof.service.conf` を `/etc/systemd/system/isuride-go.service.d/pprof.conf`、`tools/mysql-profile.cnf` を `/etc/mysql/mysql.conf.d/99-profile.cnf` に置く。pprofはVM内の127.0.0.1:6060のみで待ち受け、MySQL slow query logは50ms閾値で常時有効にする。`/var/lib/mysql/isucon14-slow.log` とCPUプロファイルを定期的にホストへ保全する。この設定はベンチ負荷に影響するため、変更前に `profiled-baseline` の公式ベンチ3回を基準にし、それ以前の段階とスコアを直接比較しない。
