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
  regenerate_example_assets.py examples/cif・examples/moleculesからJSON/catalogを再生成
  view_json_pyvista.py    JSONを読む最小PyVista表示

examples/
  cif/
    Halite.cif
    SiO2.cif
    ...
  molecules/
    water.xyz
    methane.xyz
    ...

exports/
  json/      共有用JSON
  gifs/      ローカル確認用GIF出力

docs/
  PROJECT_SPEC.md        現在の目的・スコープ・設計方針
  README.md              ドキュメント入口
  archive/               古い仕様書・相談メモ

archive/old_gui_attempt/
  以前のGUI/VTK実験コード。現行実装では使わない。
```

## セットアップ

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

結晶解析に使う旧 `symmetry_core.py` は `crystal_viewer/legacy/` に同梱されています。
別の実装を使う場合だけ、`SYMMETRY_VIEW_LEGACY_CORE=/path/to/symmetry_core.py` で上書きできます。

## 動作確認

結晶解析:

```bash
.venv/bin/python tools/analyze_structure.py examples/cif/Halite.cif
```

分子解析:

```bash
.venv/bin/python tools/analyze_molecule.py examples/molecules/water.xyz
```

共通描画データ:

```bash
.venv/bin/python tools/inspect_render_data.py examples/cif/Halite.cif --mode crystal
.venv/bin/python tools/inspect_render_data.py examples/molecules/methane.xyz --mode molecule
```

原子対応:

```bash
.venv/bin/python tools/inspect_atom_mapping.py examples/cif/Halite.cif --mode crystal
.venv/bin/python tools/inspect_atom_mapping.py examples/molecules/water.xyz --mode molecule
```

JSON export:

```bash
.venv/bin/python tools/export_analysis_json.py examples/cif/Halite.cif --mode crystal -o exports/json/halite.json
.venv/bin/python tools/export_analysis_json.py examples/molecules/water.xyz --mode molecule -o exports/json/water.json
.venv/bin/python tools/regenerate_example_assets.py --clean
```

最小表示:

```bash
.venv/bin/python tools/view_json_pyvista.py exports/json/halite.json
.venv/bin/python tools/view_json_pyvista.py exports/json/halite.json --list-operations
.venv/bin/python tools/view_json_pyvista.py exports/json/halite.json --operation 1 --list-elements
.venv/bin/python tools/view_json_pyvista.py exports/json/halite.json --operation 1
.venv/bin/python tools/view_json_pyvista.py exports/json/halite.json --operation 1 --show-mapping --show-displacements
.venv/bin/python tools/view_json_pyvista.py exports/json/water.json
```

簡単なGUI:

```bash
.venv/bin/python tools/view_json_gui.py exports/json/halite.json
.venv/bin/python tools/view_json_gui.py exports/json/halite.json --list-operations
.venv/bin/python tools/view_json_gui.py exports/json/halite.json --list-atoms
.venv/bin/python tools/view_json_gui.py exports/json/halite.json --operation 1
.venv/bin/python tools/view_json_gui.py exports/json/halite.json --expanded
.venv/bin/python tools/view_json_server.py exports/json/halite.json
```

通常起動はWebビューアーのみです。比較確認や旧GIF出力が必要な場合だけ
`--with-pyvista`を付けてPyVistaを同時起動します。

`tools/` ディレクトリに移動している場合:

```bash
../.venv/bin/python view_json_gui.py ../exports/json/halite.json
```

`exports/json/` は共有用のJSON本体、`exports/gifs/<structure>/` はローカル確認用のGIF出力置き場です。
WebビューアーのExportはPNGとアニメーションGIFに対応しています。

## 現在の設計方針

- 結晶解析は `frac` 座標で行い、`RenderData` で `cart` 座標へ変換する。
- 分子解析は最初から `cart` 座標で行う。
- 表示層は `RenderData` だけを見る。結晶か分子かの違いを描画側へ漏らさない。
- `AtomMapping` で、各対称操作による原子対応を保持する。
- `RenderData` と `AtomMapping` はJSON出力できる。
- JSONを入力にした最小PyVista表示を追加済み。操作一覧、操作ごとの要素絞り込み、原子対応表示、変位線表示に対応。
- 現在の目的・スコープ・仕様は `docs/PROJECT_SPEC.md` に集約。
- JSONビューア上の対称操作アニメーションを追加済み。設計は `docs/ANIMATION_DESIGN.md` に記録。
- 結晶アニメーションでは、代表原子で決めた周期像シフトを全原子に共有して、1つの対称操作として見える動きを優先する。
- GUIはQtなしのPyVista単体版から再開。CIFをGUIから直接解析する案Bは次段階で追加する。
