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
  water.xyz
  methane.xyz

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
.venv/bin/python tools/analyze_structure.py 'F2 Pd.cif'
```

分子解析:

```bash
.venv/bin/python tools/analyze_molecule.py examples/water.xyz
```

共通描画データ:

```bash
.venv/bin/python tools/inspect_render_data.py 'F2 Pd.cif' --mode crystal
.venv/bin/python tools/inspect_render_data.py examples/methane.xyz --mode molecule
```

原子対応:

```bash
.venv/bin/python tools/inspect_atom_mapping.py 'F2 Pd.cif' --mode crystal
.venv/bin/python tools/inspect_atom_mapping.py examples/water.xyz --mode molecule
```

JSON export:

```bash
.venv/bin/python tools/export_analysis_json.py 'F2 Pd.cif' --mode crystal -o exports/f2_pd.json
.venv/bin/python tools/export_analysis_json.py examples/water.xyz --mode molecule -o exports/water.json
```

最小表示:

```bash
.venv/bin/python tools/view_json_pyvista.py exports/f2_pd.json
.venv/bin/python tools/view_json_pyvista.py exports/f2_pd.json --list-operations
.venv/bin/python tools/view_json_pyvista.py exports/f2_pd.json --operation 1
.venv/bin/python tools/view_json_pyvista.py exports/f2_pd.json --operation 1 --show-mapping --show-displacements
.venv/bin/python tools/view_json_pyvista.py exports/water.json
```

## 現在の設計方針

- 結晶解析は `frac` 座標で行い、`RenderData` で `cart` 座標へ変換する。
- 分子解析は最初から `cart` 座標で行う。
- 表示層は `RenderData` だけを見る。結晶か分子かの違いを描画側へ漏らさない。
- `AtomMapping` で、各対称操作による原子対応を保持する。
- `RenderData` と `AtomMapping` はJSON出力できる。
- JSONを入力にした最小PyVista表示を追加済み。操作一覧、操作ごとの要素絞り込み、原子対応表示、変位線表示に対応。
- 次の実装対象はJSONビューア上の対称操作アニメーション。設計は `docs/ANIMATION_DESIGN.md` に記録。
- GUI/Qt埋め込みはまだ再実装しない。
