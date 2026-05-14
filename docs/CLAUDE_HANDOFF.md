# Claude Handoff

このメモは、Claude に現状レビューや次ステップ相談を依頼するための共有用入口です。

## まず読んでほしい順番

1. `README.md`
2. `docs/CURRENT_STATUS.md`
3. `docs/REVIEW_NOTES.md`
4. 必要に応じて `docs/specs/codex_final_spec_crystal_symmetry_viewer.md`

## 現在の目的

結晶・分子の対称性を解析し、将来の3D表示・対称操作アニメーション・パズル化に使える共通データを作る。

GUI/3D表示は一度失敗したので、現在は段階的に作り直している。

現在の有効スコープ:

```text
1. 結晶解析
2. 分子解析
3. RenderData 変換
4. AtomMapping
5. JSON export
6. 最小JSON表示
7. アニメーション設計
```

まだやらないもの:

```text
GUI
アニメーション再生
パズルUI
```

最小3D表示だけは `tools/view_json_pyvista.py` として追加済み。GUI/Qt埋め込みではなく、JSONを読むPyVista単体ツール。

## Active Code

```text
crystal_viewer/
  analysis_models.py      dataclass定義
  structure_analysis.py   CIF/結晶解析
  molecule_analysis.py    分子点群解析
  render_data.py          結晶/分子解析結果 -> 共通描画データ
  atom_mapping.py         各対称操作の原子対応
  json_export.py          RenderData + AtomMapping のJSON化

tools/
  analyze_structure.py
  analyze_molecule.py
  inspect_render_data.py
  inspect_atom_mapping.py
  export_analysis_json.py
  view_json_pyvista.py
```

古いGUI/VTK実験コードは `archive/old_gui_attempt/` に隔離済み。現行実装としては使わない。

## 動作確認コマンド

```bash
.venv/bin/python tools/analyze_structure.py 'F2 Pd.cif'
.venv/bin/python tools/analyze_molecule.py examples/water.xyz
.venv/bin/python tools/analyze_molecule.py examples/methane.xyz
.venv/bin/python tools/inspect_render_data.py 'F2 Pd.cif' --mode crystal
.venv/bin/python tools/inspect_render_data.py examples/methane.xyz --mode molecule
.venv/bin/python tools/inspect_atom_mapping.py 'F2 Pd.cif' --mode crystal
.venv/bin/python tools/inspect_atom_mapping.py examples/water.xyz --mode molecule
.venv/bin/python tools/inspect_atom_mapping.py examples/methane.xyz --mode molecule
.venv/bin/python tools/export_analysis_json.py 'F2 Pd.cif' --mode crystal -o exports/f2_pd.json
.venv/bin/python tools/export_analysis_json.py examples/water.xyz --mode molecule -o exports/water.json
.venv/bin/python tools/view_json_pyvista.py exports/f2_pd.json
.venv/bin/python tools/view_json_pyvista.py exports/f2_pd.json --list-operations
.venv/bin/python tools/view_json_pyvista.py exports/f2_pd.json --operation 1
.venv/bin/python tools/view_json_pyvista.py exports/f2_pd.json --operation 1 --show-mapping --show-displacements
.venv/bin/python tools/view_json_pyvista.py exports/water.json
.venv/bin/python tools/view_json_pyvista.py exports/water.json --operation 0 --show-mapping --show-displacements
```

確認済みの代表結果:

```text
F2 Pd.cif:
  space group: 198 P2_13
  operations: 12
  axes: 24
  AtomMapping complete: True

water.xyz:
  point group: C2v
  operations: 4
  axes: 1
  planes: 2
  AtomMapping complete: True

methane.xyz:
  point group: Td
  operations: 24
  axes: 10
  planes: 6
  AtomMapping complete: True
```

## 設計の要点

結晶:

```text
CIF -> pymatgen Structure -> spglib W,t -> legacy symmetry_core.py -> StructureAnalysisResult
```

分子:

```text
Molecule -> pymatgen PointGroupAnalyzer -> MoleculeAnalysisResult
```

共通化:

```text
StructureAnalysisResult / MoleculeAnalysisResult
  -> RenderData
  -> 将来の表示層
```

原子対応:

```text
StructureAnalysisResult / MoleculeAnalysisResult
  -> AtomMappingSet
  -> 将来のアニメーション・パズル判定
```

## 既知課題

### 1. スクリュー軸ラベルが `2_?`

`F2 Pd.cif` で screw_2 が `2_?` と表示される。

原因:

```text
legacy symmetry_core.py の operation_international_symbol() に axis element を渡していない
```

ロジック上は `kind='screw_2'`, `order=2` が取れているので、アニメーションやパズルには致命的ではない。
UI表示前に直すか、当面 `kind` ベースで表示する方針でもよい。

### 2. 結晶解析が外部 legacy core に依存

```python
DEFAULT_LEGACY_CORE = Path("/home/ken/work/kouzoukaiseki/symmetry_core.py")
```

現環境では動くが、将来的には `crystal_viewer/` 内へ取り込むか、正式な依存として扱う必要がある。

### 3. JSON出力

解決済み。`crystal_viewer/json_export.py` と `tools/export_analysis_json.py` を追加済み。

## Claudeに相談したいこと

1. ~~`RenderData` と `AtomMapping` のデータ構造は十分か~~ → 十分（`REVIEW_NOTES.md` Q1参照）
2. ~~`AtomMappingEntry` の `animation_frac` / `transformed_cart` の持ち方~~ → 妥当、命名注意点あり（Q2参照）
3. ~~JSON export~~ → 実装済み・動作確認済み（`REVIEW_NOTES.md` JSON exportレビュー参照）
4. ~~JSON export のスキーマは最小3D表示に十分か~~ → 十分（Q1参照）
5. legacy `symmetry_core.py` をいつ取り込むべきか → 急がなくてよい（Q4参照）
6. スクリュー軸ラベル `2_?` 問題 → 表示層まで保留でよい（Q5参照）
7. ~~最小PyVista表示プロトタイプの実装レビュー~~ → 操作一覧、操作絞り込み、mapping表示、変位線表示まで実装済み
8. ~~最初のアニメーション設計レビュー~~ → 操作別dispatcherを最初から作り、線形補間は短期デバッグ用に限定。`RenderOperationData.angle_deg` を追加する方針
9. **次の相談**: `docs/ANIMATION_DESIGN.md` の方針で `tools/view_json_pyvista.py --animate` を実装してよいか。特に screw 操作の「arc + residual-to-target correction」の扱いが妥当か

## Claudeへの依頼文例

```text
このプロジェクトは結晶/分子の対称性ビューアーを段階的に作り直しています。
GUIはまだ作らず、現時点では解析層・RenderData・AtomMapping・JSON export・最小PyVista表示まで実装済みです。

まず README.md, docs/CURRENT_STATUS.md, docs/REVIEW_NOTES.md, docs/CLAUDE_HANDOFF.md, docs/ANIMATION_DESIGN.md を読んでください。
そのうえで、次に tools/view_json_pyvista.py に `--animate` を実装する前提で、
アニメーション設計に問題がないかレビューしてください。

archive/old_gui_attempt/ は古い失敗コードなので、現行実装としては使わないでください。
```
