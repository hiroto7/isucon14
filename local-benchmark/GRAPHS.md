# 全試行と最高値更新のグラフ

`results/*/result.json` を正本として、`tools/plot_complete_history.py` がすべての記録を読み、`started_at`（UTC）と試行ディレクトリ名の順に並べます。特定の段階を固定したリストで選別しません。新しい結果を保存して同じコマンドを実行すれば、両方のグラフに自動で反映されます。元の計測記録は変更しません。

## 再生成

リポジトリのルート `~/dev/isucon14` から実行します。既存のPython仮想環境にmatplotlibが入っています。

```sh
local-benchmark/.venv/bin/python local-benchmark/tools/plot_complete_history.py
```

Python 3とmatplotlibがあれば別の環境でも実行できます。

```sh
python3 -m venv /tmp/isucon14-graphs-venv
/tmp/isucon14-graphs-venv/bin/python -m pip install matplotlib
/tmp/isucon14-graphs-venv/bin/python local-benchmark/tools/plot_complete_history.py
```

保存先や入力を変える場合は以下の引数を使います。

```sh
local-benchmark/.venv/bin/python local-benchmark/tools/plot_complete_history.py \
  --results-dir local-benchmark/results \
  --stages-file local-benchmark/stages.json \
  --output-dir /tmp/isucon14-graphs
```

## 全試行

- `score-all-trials.png`、`score-all-trials.svg`: 最初の公式Goコードの計測から現在まで、全試行を実行順で1枚に表示します。
- `all-trials.csv`: 各点の試行番号、日時、段階、採否、成否、スコア、コミット、差分ハッシュ。
- 横軸は時刻間隔ではなく試行番号です。日付の区切りは日本時間で表示します。同じ段階の複数測定もそれぞれ独立した点です。
- 青は成功、橙は成功した不採用候補、赤い×は失敗・中止。失敗・中止は数値スコアを持たず、0点とは別の帯に表示します。失敗の前後では線を切ります。
- 失敗したベンチが報告した点数は `reported_score` に残っていても、グラフの数値スコアに使いません。準備失敗・配備失敗も省略しません。
- 初期VMの最初の3回（5,104、1,951、3,549点）も含めます。再構築後の基準中央値4,754点から始めるグラフではありません。

## 最高値更新のみ

- `score-record-highs.png`、`score-record-highs.svg`: 全試行から最高値を厳密に更新した成功試行だけを抜き取ります。
- `record-highs.csv`: 抜き取った試行の一覧。元の試行番号を保持します。
- 条件は `status == "passed"`、有限の数値スコアが存在し、その点より前のすべての有効スコアより **大きい** こと。同点、下落、失敗・中止を除外します。
- 最初の有効試行を最初の最高値とします。
- 採用・不採用は抽出条件にしません。不採用候補でも有効な最高値なら含め、橙で表示します。例えば70,317点の所要時間マッチング候補と87,854点の利用者通知キャッシュ候補も入ります。
- 横軸は抜き取り後の更新順で、下段の `#` が元の全試行グラフの番号です。個々のスコアを表示します。

## 確認済みのデータ範囲

2026-10-07時点では全109試行、成功98件、失敗・中止11件、最高値更新32件です。最初の有効値は5,104点、最後の最高値は116,260点。

以前の `score-history.png` は段階ごとにまとめた表示であり、今回の全試行時系列グラフとは異なります。保存済みの全試行を確認したい場合は `score-all-trials.png` を使ってください。全履歴にはVM再構築、設定変更、別日の測定、不採用候補も含まれ、同一条件での統制実験とは異なります。数値はローカルARM64・単一VMでの公式ベンチ結果です。
