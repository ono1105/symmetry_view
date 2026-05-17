# Claude Handoff

このメモは、Claude に現状レビューや次ステップ相談を依頼するための短い入口です。

## まず読むもの

1. `README.md`
2. `docs/PROJECT_SPEC.md`
3. `docs/REVIEW_NOTES.md`
4. 必要に応じて `docs/ANIMATION_DESIGN.md`, `docs/JSON_EXPORT.md`, `docs/MINIMAL_VIEWER.md`

古い仕様書や過去のレビュー依頼は `docs/archive/` にあります。背景情報として参照してよいですが、現在の判断基準は `docs/PROJECT_SPEC.md` です。

## 現在の目的

結晶・分子の対称性を解析し、将来の3D表示・対称操作アニメーション・パズル化に使える共通データとビューアー基盤を作る。

現在は JSON を開く最小 GUI まで作り始めています。

```text
結晶解析
分子解析
RenderData
AtomMapping
JSON export
最小JSON表示
対称操作アニメーション
最小JSON GUI（Qtなし、PyVista native widgets）
ブラウザ操作パネル + PyVista表示（localhost API）
```

まだ主対象にしないもの:

```text
PyVistaQt埋め込みGUI
CIF/XYZをGUIから直接解析する機能
マウスによる原子選択
パズルUI
```

## Active Code

```text
crystal_viewer/
tools/
```

古いGUI/VTK実験コードは `archive/old_gui_attempt/` に隔離済みです。現行実装としては使わないでください。

## 代表確認コマンド

```bash
.venv/bin/python tools/analyze_structure.py examples/structures/jacobsite.cif
.venv/bin/python tools/analyze_molecule.py examples/water.xyz
.venv/bin/python tools/export_analysis_json.py examples/structures/f2_pd.cif --mode crystal -o exports/json/f2_pd.json
.venv/bin/python tools/view_json_pyvista.py exports/json/jacobsite.json --list-operations
.venv/bin/python tools/view_json_pyvista.py exports/json/jacobsite.json --operation 25 --animate --animation-fps 6 --animation-speed 0.5
.venv/bin/python tools/view_json_gui.py exports/json/jacobsite.json
```

## 既知の注意点

- `screw_2` などの表示ラベルが `2_?` になることがあります。内部の `kind`, `order`, `angle_deg` は取れているので、現時点では非ブロッカーです。
- 結晶解析はまだ `/home/ken/work/kouzoukaiseki/symmetry_core.py` に依存しています。
- 混合占有サイトは、現時点では最大占有率の元素を代表元素として扱います。

## Claudeへの依頼文例

```text
このプロジェクトは結晶/分子の対称性ビューアーを段階的に作り直しています。
現在の判断基準は docs/PROJECT_SPEC.md です。

README.md, docs/PROJECT_SPEC.md, docs/REVIEW_NOTES.md を読んでから、
直近の実装が「ビューアーを先に安定させ、あとでパズルを載せる」という目的からずれていないか、
バグや設計上のリスクをレビューしてください。

docs/archive/ と archive/old_gui_attempt/ は履歴・参考資料であり、現行実装の基準ではありません。
```
