# Crystal Symmetry Viewer

結晶・分子の対称性を解析し、将来の3D表示・アニメーション・パズル化に渡せる共通データへ変換するためのプロジェクトです。

現在はGUIを作り直す前段階として、解析レイヤーと `RenderData` レイヤーだけを有効コードとして整理しています。

## 現在のフォルダ構成

```text
crystal_viewer/
  analysis_models.py      解析結果とRenderData用のdataclass
  structure_analysis.py   CIF/結晶解析
  molecule_analysis.py    分子点群解析
  render_data.py          結晶/分子解析結果 -> 共通描画データ
  atom_mapping.py         対称操作ごとの原子対応

tools/
  analyze_structure.py    結晶解析CLI
  analyze_molecule.py     分子解析CLI
  inspect_render_data.py  RenderData確認CLI
  inspect_atom_mapping.py AtomMapping確認CLI
  export_analysis_json.py JSON export CLI
  view_json_pyvista.py    JSONを読む最小PyVista表示

examples/
  structures/
    f2_pd.cif
    jacobsite.cif
    mg2v2o7.cif
  water.xyz
  methane.xyz

exports/
  f2_pd.json
  jacobsite.json
  mg2v2o7.json
  water.json

docs/specs/
  仕様書・設計メモ

archive/old_gui_attempt/
  以前のGUI/VTK実験コード。現行実装では使わない。
```

## セットアップ

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 動作確認

結晶解析:

```bash
.venv/bin/python tools/analyze_structure.py examples/structures/f2_pd.cif
```

分子解析:

```bash
.venv/bin/python tools/analyze_molecule.py examples/water.xyz
```

共通描画データ:

```bash
.venv/bin/python tools/inspect_render_data.py examples/structures/f2_pd.cif --mode crystal
.venv/bin/python tools/inspect_render_data.py examples/methane.xyz --mode molecule
```

原子対応:

```bash
.venv/bin/python tools/inspect_atom_mapping.py examples/structures/f2_pd.cif --mode crystal
.venv/bin/python tools/inspect_atom_mapping.py examples/water.xyz --mode molecule
```

JSON export:

```bash
.venv/bin/python tools/export_analysis_json.py examples/structures/f2_pd.cif --mode crystal -o exports/f2_pd.json
.venv/bin/python tools/export_analysis_json.py examples/structures/jacobsite.cif --mode crystal -o exports/jacobsite.json
.venv/bin/python tools/export_analysis_json.py examples/structures/mg2v2o7.cif --mode crystal -o exports/mg2v2o7.json
.venv/bin/python tools/export_analysis_json.py examples/water.xyz --mode molecule -o exports/water.json
```

最小表示:

```bash
.venv/bin/python tools/view_json_pyvista.py exports/f2_pd.json
.venv/bin/python tools/view_json_pyvista.py exports/f2_pd.json --list-operations
.venv/bin/python tools/view_json_pyvista.py exports/f2_pd.json --operation 1 --list-elements
.venv/bin/python tools/view_json_pyvista.py exports/f2_pd.json --operation 1
.venv/bin/python tools/view_json_pyvista.py exports/f2_pd.json --operation 1 --show-mapping --show-displacements
.venv/bin/python tools/view_json_pyvista.py exports/f2_pd.json --operation 1 --element-index 0 --animate --animation-scope representative --animation-fps 6 --animation-output exports/checks/f2_pd_op1_rep.gif
.venv/bin/python tools/view_json_pyvista.py exports/f2_pd.json --operation 1 --element-index 0 --animate --animation-scope all --representative-atom 0 --animation-fps 6 --animation-output exports/checks/f2_pd_op1_all.gif
.venv/bin/python tools/view_json_pyvista.py exports/jacobsite.json --operation 26 --element-index 0 --animate --animation-fps 6 --animation-output exports/checks/jacobsite_op26_glide.gif
.venv/bin/python tools/view_json_pyvista.py exports/water.json
```

`exports/` 直下は共有用のJSON本体だけを置き、確認用のGIF/PNGは `exports/checks/` に置く方針です。

## 現在の設計方針

- 結晶解析は `frac` 座標で行い、`RenderData` で `cart` 座標へ変換する。
- 分子解析は最初から `cart` 座標で行う。
- 表示層は `RenderData` だけを見る。結晶か分子かの違いを描画側へ漏らさない。
- `AtomMapping` で、各対称操作による原子対応を保持する。
- `RenderData` と `AtomMapping` はJSON出力できる。
- JSONを入力にした最小PyVista表示を追加済み。操作一覧、操作ごとの要素絞り込み、原子対応表示、変位線表示に対応。
- 仕様書との現在の整合性は `docs/SPEC_ALIGNMENT.md` に記録。
- JSONビューア上の対称操作アニメーションを追加済み。設計は `docs/ANIMATION_DESIGN.md` に記録。
- 結晶アニメーションでは、代表原子で決めた周期像シフトを全原子に共有して、1つの対称操作として見える動きを優先する。
- GUI/Qt埋め込みはまだ再実装しない。
