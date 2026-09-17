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

アプリの性能変更前に構築が正常終了したこと、Go・MySQL・nginx・matcherの起動、ホストとVMのコード一致を確認する。

## 計測

```sh
python3 local-benchmark/tools/run_benchmark.py baseline --runs 3
```

各回でGo・matcherを再起動して20秒待ち、60秒の公式負荷走行を行う。静的ファイル検証は省略しない。
`results/<UTC日時>-<段階>/` に生ログ、公式結果の成否・スコア、コードのコミット・差分、SQL集計、リソース情報を保存する。
失敗は `score: null` とし、ベンチが出力した数値があれば `reported_score` に別途保持する。

## グラフ再生成

```sh
uv venv local-benchmark/.venv
uv pip install --python local-benchmark/.venv/bin/python -r local-benchmark/requirements.txt
local-benchmark/.venv/bin/python local-benchmark/tools/plot_scores.py
```

`scores.csv` と `score-history.png` は生データから再生成する。
各回の点、中央値、最小最大を表示し、不採用・失敗も記録する。

## 改善の判断

最大3サイクル。SQL・HTTP・CPUの実測から一つずつ仮説を選び、3回の公式検証成功と中央値の向上を確認する。
差がばらつきと重なる場合は前後を追加測定し、確認できない変更は戻す。
最後に再起動後の動作・計測も確認する。各段階をローカルコミットに残す。

## 現在の状態

構築中。スコアは未測定。
