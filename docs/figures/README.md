# 報告書の図版

`docs/REPORT_OUTLINE.md`「図表リスト」に対応するスクリーンショット。
**手で撮ったものではない**。`tools/capture_report_figures.py` が実際のビューアーを
headless Chromium で操作して保存する。撮り直しは次のコマンドでできる。

```bash
.venv/bin/python -m pip install -r requirements-dev.txt   # playwright が要る
.venv/bin/python tools/capture_report_figures.py          # 全部
.venv/bin/python tools/capture_report_figures.py --only puzzle
```

画像は 1440×960 の画面を 2 倍解像度（実寸 2880×1920）で撮っている。

## 図表リストとの対応

| # | 図 | ファイル | 備考 |
|---|---|---|---|
| 1 | アーキテクチャ図 | （未作成） | 作図。スクリーンショットではない |
| 2 | 対称操作の種類一覧 | `fig02a_analysis_benzene.png`<br>`fig02b_operation_list_molecule.png`<br>`fig02c_analysis_halite.png`<br>`fig02d_operation_list_crystal.png` | 分子は `C2/C3/C6/E/i/S6/σ`、結晶は `1/2/3/4/2₁/4₂/-1/-3/-4/g/m/t`。この記号の列がそのまま一覧図になる |
| 3 | 操作アニメの連続コマ | `fig03_anim_before.png`<br>`fig03_anim_mid.png`<br>`fig03_anim_after.png` | ベンゼンの C6。軸方向から 25° 傾けた視点 |
| 4 | パズル画面の各部 | `fig04_puzzle_layout.png` | 番号は後付け。`fig04a_quiz_select.png` はクイズ選択画面 |
| 5 | 回転軸クイズ | `fig05_axis_question.png` / `fig05_axis_answer.png` | ベンゼン |
| 6 | 操作あてクイズ | `fig06_operation_normal_*.png`（普通・ベンゼン）<br>`fig06b_operation_hard_*.png`（難しい・halite） | 難しいは並進成分まで答える |
| 7 | 合成クイズ | `fig07_composition_question.png` / `fig07_composition_answer.png` | ベンゼン |
| 8 | 移り先クイズ | `fig08_mapping_question.png` / `fig08_mapping_answer.png` | メタン |
| 9 | 対称要素の表示 | `fig09a_element_axis.png`（軸）<br>`fig09_element_plane.png`（面）<br>`fig09_element_center.png`（中心）<br>`fig09_element_improper.png`（S6＝軸＋面）<br>`fig09_element_glide.png`（映進矢印）<br>`fig09_element_screw.png`（らせん軸） | 映進矢印は halite の一般映進 `g`。`fig09a_element_axis_edge_on.png` は既定カメラでの見え方 |
| 10 | テスト実行結果 | `fig10_test_output.txt` | 255 件 OK |

## 撮り直しは「通し確認」も兼ねている

`open_example()` は**読み込めたことを /api/state で確認してから**次へ進む。
以前は `.operation-row` が出るのを待つだけだったが、この行は前の構造のものが
残っているので何も保証していなかった。実際そのせいで、
**ベンゼンのつもりでメタンの操作一覧を撮っていた**ことに気づけず、
図が静かに間違ったまま保存されうる状態だった（2026-08-15 に修正）。

## 撮るときに引っかかった点

図を撮り直すときのために残しておく。

- **ベンゼンは既定カメラだと真横から見える**。環が潰れて回転がほとんど動いて見えないので、
  「軸方向から見る」で軸を正面にしてから 25° 傾けている（`view_along_axis()`）。
- **映進矢印が出るのは一般映進 `g` だけ**。`a` / `b` / `c` / `n` は ITC 記号が並進成分を
  表すので矢印を描かない。最初の映進を選ぶと矢印の無い図になる（`first_drawn_glide()`）。
- **答えはサーバーから取れない**。設計どおり正解はクライアントに渡らないので、
  取得スクリプトは当てずっぽうで答えて正解した回を採用する。移り先クイズをベンゼン
  （12原子）でやると 40 ラウンドでも当たらなかったため、メタンに変えた。
- **移り先クイズの青いリングと C2 軸の線が近い色**。`fig08_mapping_answer.png` で確認できる。
  既知の限界（`docs/REVIEW_NOTES.md` 末尾）で、図としてはリングが3本重なって見分けられる。
