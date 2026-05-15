# コードレビューメモ（Codex向け共有）

Claude によるレビュー結果をまとめています。
実装の判断材料として参照してください。

---

## 動作確認済み（全て正常）

以下のツールが正常に動作することを確認しました。

```bash
.venv/bin/python tools/analyze_molecule.py examples/water.xyz     # C2v
.venv/bin/python tools/analyze_molecule.py examples/methane.xyz   # Td
.venv/bin/python tools/analyze_structure.py 'F2 Pd.cif'           # P2_13, 12 ops, 24 axes
.venv/bin/python tools/inspect_render_data.py 'F2 Pd.cif' --mode crystal
.venv/bin/python tools/inspect_render_data.py examples/methane.xyz --mode molecule
.venv/bin/python tools/inspect_atom_mapping.py 'F2 Pd.cif' --mode crystal
.venv/bin/python tools/inspect_atom_mapping.py examples/water.xyz --mode molecule
.venv/bin/python tools/export_analysis_json.py 'F2 Pd.cif' --mode crystal -o exports/f2_pd.json
.venv/bin/python tools/export_analysis_json.py examples/water.xyz --mode molecule -o exports/water.json
```

---

## 問題点

### 問題1: スクリュー軸の国際記号が `2_?` になる（軽微）

**場所:** `crystal_viewer/structure_analysis.py` の `convert_operation()` 関数

**内容:**
`core.operation_international_symbol(op)` を呼ぶとき `element`（軸情報）を渡していない。
legacy core 側では `element` がないと `screw_symbol_from_axis()` を呼ばず、
`f"{order}_?"` にフォールバックする。

`F2 Pd.cif`（P2₁3）で確認:

```
  1:         2_?  screw_2   ...  # 正しくは 2_1
```

**原因:**
`convert_operation` がオペレーション変換を行う時点では、
axis 情報（`merged["axes"]`）はまだ変換されていない。
2パスが必要になる構造になっている。

**修正案（2択）:**

案A. 二段階処理：先に操作を「仮変換」し、axes 変換後に symbol だけ再計算する。

案B. `SymmetryOperationInfo` の `international_symbol` をアニメーション・表示に
使う場面では、代わりに `kind`（例: `screw_2`）と `order` から組み立てる。
`2_?` を UI に出すのは避け、`kind` ベースで表示する。

UI 表示が目的なら案B が手軽です。
アニメーション・パズルのロジックには `kind` と `order` の方が確実です。

---

### 問題2: 外部パスへのハードコード（既知）

**場所:** `crystal_viewer/structure_analysis.py:24`

```python
DEFAULT_LEGACY_CORE = Path("/home/ken/work/kouzoukaiseki/symmetry_core.py")
```

この機械では `/home/ken/work/kouzoukaiseki/symmetry_core.py` が存在するので動作する。
他の環境では `AnalysisError` になる。

意図的に `kouzoukaiseki` プロジェクトと連携している設計と思われるので、
変更するかどうかは判断が必要です。

---

## 設計上の観察・提案

### AtomMapping の設計について

AtomMapping は `crystal_viewer/atom_mapping.py` に実装済み。
仕様書（Stage 2）のアニメーション要件から逆算すると、`AtomMapping` に必要な情報は以下：

```python
# 1操作あたりのマッピング
AtomMapping:
    operation_index: int
    # atom i が atom mapping[i] に移動する（整数インデックス）
    # 移動先が元の原子と一致しない場合は置換が起きる
    atom_to_atom: tuple[int, ...]
    # 各原子の移動後のfrac座標（変換後、最近接周期像に丸める前）
    transformed_frac: tuple[np.ndarray, ...]
```

`frac' = W @ frac + t` で計算した座標を、結晶内の全原子と照合すれば
`atom_to_atom` は作れます。照合には周期境界（最近接像）を考慮する必要があります。

実装では `OperationAtomMapping.atom_to_atom` と各 `AtomMappingEntry` に
`transformed_cart` / `transformed_frac` / `animation_frac` を持たせています。
結晶では周期境界込み、分子では直交座標距離で同種原子を照合します。

### `render_data.py` の `operation_group_label` について

現在のラベル生成:

```python
# 例: "2_?x3, 3" のような文字列になる
parts = [f"{symbol}x{count}" if count > 1 else symbol for symbol, count in sorted(counts.items())]
```

スクリュー軸の `2_?` 問題が解消されれば、このラベルも自動的に改善されます。

---

## 整理の評価

今回の Codex による整理（archive への移動・README 追加・docs/ 構成）は適切です。
`requirements.txt` から VTK/Qt を外した判断も、現フェーズに合っています。

active なコードは `crystal_viewer/` と `tools/` だけに絞られています。
`AtomMapping` と JSON export は実装済みなので、次は最小表示プロトタイプに進める状態です。

---

## AtomMapping 実装のレビュー（`CLAUDE_HANDOFF.md` の質問への回答）

### Q1. RenderData + AtomMapping の構造は将来の表示・アニメーション・パズル化に十分か

**結論: 十分。** 以下を確認しました。

| 用途 | 必要なデータ | 現在の状態 |
|------|------------|-----------|
| 3D表示 | 原子・軸・面・中心・単位胞の座標 | `RenderData` に揃っている ✓ |
| 回転アニメーション | 各原子の移動先座標（最近接周期像）+ 回転軸 | `animation_frac` + `RenderData.axes` 経由で取得可能 ✓ |
| 置換確認（パズル） | 操作後の `atom_to_atom` マッピング | `OperationAtomMapping.atom_to_atom` ✓ |

アニメーションで回転軸を引くには `operation_index` → `RenderData.operations` → `RenderData.axes.operation_indices` を辿る間接参照が必要ですが、データは揃っています。

### Q2. `AtomMappingEntry` の `animation_frac` / `transformed_cart` の持ち方は妥当か

**ほぼ妥当。命名に1点注意あり。**

結晶モードでの `transformed_cart` は実際には `animation_frac @ lattice`（最近接周期像のCartesian）であり、
`transformed_frac @ lattice` ではありません。

```python
# atom_mapping.py:138
transformed_cart=animation_frac @ lattice,  # ← 最近接像のCartesian（raw変換ではない）
```

名前から「rawの変換後座標」を期待すると混乱します。
rawが必要なら `transformed_frac @ lattice` で計算できます。
**アニメーション用途には現在の実装で正しいです。** ただし将来コードが増えたとき混乱しやすいため、コメントを1行入れておくと安全です。

分子モードでは `transformed_cart` はそのまま `rotation @ cart + translation`（raw）なので意味が一致しています。

### Q3. 次は JSON export か 最小3D表示か

**JSON export を先に推奨します。**

理由：
- `RenderData` と `AtomMapping` のデータが正しいかを、3D環境なしで検証できる
- Codex・Claude 間でレビューしやすくなる（`CLAUDE_HANDOFF.md` でも言及あり）
- 将来の表示層が VTK か PyVista かブラウザ（WebGL）かに関わらず使える

JSON export があれば、次ステップで「JSON を読む最小表示」というアーキテクチャも選べます。

**対応済み:** `crystal_viewer/json_export.py` と `tools/export_analysis_json.py` を追加。
詳細は `docs/JSON_EXPORT.md` を参照。

### Q4. legacy `symmetry_core.py` をいつ取り込むべきか

**現時点では急がなくてよい。** この環境で動いており、今のスコープ（解析層・RenderData・AtomMapping）には影響しません。

取り込むタイミングの目安：
- 他の環境で動かしたいとき（ポータビリティが必要になったとき）
- JSON export が完成して、crystal 解析全体をテストしたいとき

`DEFAULT_LEGACY_CORE` はデフォルト値なので、環境変数や CLI 引数で上書きできる仕組みを足すだけでも当面は十分です。

### Q5. スクリュー軸ラベル `2_?` 問題は今直すべきか

**表示層まで保留でよい。**

`kind='screw_2'`, `order=2` は正確に取れているため、アニメーションやパズル判定には影響しません。
UI 実装時に `kind` + `order` から表示文字列を組み立てる関数を作るタイミングで直すのが自然です。

---

## JSON export 実装レビュー

`crystal_viewer/json_export.py` と `tools/export_analysis_json.py` の実装を確認しました。

### 動作確認

```bash
.venv/bin/python tools/export_analysis_json.py 'F2 Pd.cif' --mode crystal -o exports/f2_pd.json
.venv/bin/python tools/export_analysis_json.py examples/water.xyz --mode molecule -o exports/water.json
```

両ファイルとも valid JSON であることを確認しました（`python -m json.tool` で検証済み）。
stdout 出力モードも正常動作しています。

### `to_jsonable()` の実装について

`value.__dict__` を使った dataclass の変換は、frozen dataclass（Python 3.7+）で正常動作します。
フィールド定義順が保持されるため、出力 JSON の順序も安定しています。

```python
if is_dataclass(value):
    return {key: to_jsonable(item) for key, item in value.__dict__.items()}
```

`is_dataclass()` はクラス型にも True を返しますが、この関数はインスタンスにしか呼ばれないため問題なし。

### `transformed_cart` の命名と JSON_EXPORT.md

レビューで指摘した「結晶モードの `transformed_cart` は `animation_frac @ lattice`（最近接像）であり raw 変換ではない」という点が、
`docs/JSON_EXPORT.md` に正確に記載されていることを確認しました。

```
`transformed_cart` is computed from that animation image for crystals.
For molecule mappings, `transformed_cart` is the raw transformed Cartesian coordinate.
```

### ルートの `claude_handoff.md` / `review_notes.md` について

プロジェクトルートにある同名ファイルは `docs/` 内の本体へのポインタファイルです（数行のみ）。
本体は `docs/CLAUDE_HANDOFF.md` / `docs/REVIEW_NOTES.md` です。

---

## 最小 PyVista ビューアーレビュー（`tools/view_json_pyvista.py`）

### スクリーンショット確認

`exports/water_view.png` と `exports/f2_pd_op1_view.png` で目視確認しました。

**water（C2v）:**
- O（赤）と H×2（白）が正しい位置に表示されている ✓
- C2軸（緑のライン）が O 原子を通り正しい方向に表示されている ✓
- 2枚の鏡映面のうち、1枚は水平な青いクワッドとして見える ✓
- もう1枚はほぼエッジオン（C2軸に垂直な面を側面から見た状態）で細い線として見える ✓（3D的に正しい）

**PdF2（P2_13、operation 1: screw_2）:**
- Pd（青灰）と F（黄緑）が単位胞内に正しく配置されている ✓
- `--operation 1` フィルタで screw_2 に対応する軸 4 本が表示されている ✓
- 単位胞（白いボックス）が正しく描画されている ✓
- タイトルに `1: 2_? screw_2` と表示されており、既知のラベル問題が確認できる

### コードレビュー

設計として「JSON のみを読む、解析コードに依存しない」という分離が守られています ✓

**`filter_by_operation()`** が `operation_index in element["operation_indices"]` でフィルタリングする実装は正しいです。

**`requirements.txt`** に `pyvista>=0.43` が追加されています ✓

**軽微な観察点:**

- **面の大きさ**: `plane_scale = max(span * 0.28, 0.5)` で固定スケール。細長い結晶や大きな分子では視認しにくくなる可能性があります。致命的ではない。
- **軸の長さ**: `axis_length = max(span * 0.75, 1.0)` はシーン全体をカバーする長さで適切。
- **`_bootstrap.py` 不使用**: JSON のみを読むため `crystal_viewer` への依存がなく、正しい設計です ✓

---

## ビューアー拡張レビュー（`--show-displacements` 他）

### 追加された機能

`view_json_pyvista.py` に4つのオプションが追加されました。

| オプション | 内容 |
|-----------|------|
| `--list-operations` | 操作一覧を表示して終了（mapping 状態も表示） |
| `--show-mapping` | `--operation` で選択した操作の atom_to_atom を表示 |
| `--show-displacements` | 変位ライン（source → transformed_cart）を描画 |

### スクリーンショット確認

**water operation 0 (C2 rotation_2):**
- O 原子（赤）は変位なし（C2 軸上にあるため）。金色ラインなし ✓
- H×2（白）が互いに入れ替わる。両者を結ぶ金色ラインが描画されている ✓

**PdF2 operation 1 (screw_2):**
- 各原子から対称等価位置へ金色のチューブで結ばれている ✓
- 単位胞外へ出る変位（`animation_frac` 最近接像に基づく）も正しく描画されている ✓

### コードレビュー

**`add_displacements()`**
- `entry["transformed_cart"]` を終点として使用しており、結晶（最近接像）・分子（raw変換）ともに正しい ✓
- `norm < 1e-9` で静止原子をスキップする処理が入っている ✓
- `pv.Line().tube()` パターンは PyVista の正しい使い方 ✓
- 終点に小球マーカーを追加しており視認性がよい ✓

**`--show-displacements` 単体使用時**（`--operation` なし）の挙動：
`selected_mapping()` が `None` を返し、`"No atom mapping found. Use --operation with --show-displacements."` と表示して続行します。エラーにならず表示自体は出るため、使いやすい設計です ✓

### 次ステップ（CURRENT_STATUS.md より）

アニメーションプロトタイプ。方針：
1. まず線形補間で動作確認
2. その後、回転は円弧補間、鏡映・反転は線形補間に切り替え（仕様書通り）

データは `AtomMappingEntry.transformed_cart` と `RenderData.axes` に揃っているので、アニメーション実装に必要な材料はほぼあります。

---

## アニメーション設計レビュー（`CLAUDE_HANDOFF.md` 質問8への回答）

仕様書 `docs/specs/codex_final_spec_crystal_symmetry_viewer.md` Section 16 を参照しながら確認しました。

### Q. この順番（線形補間 → 円弧補間）で進めるのが妥当か

妥当です。ただし仕様書 Section 16.3 は「**最初から**」円弧補間を実装するよう明記しています。
線形補間はデバッグ用として一時的なものと位置づけ、すぐに切り替えることを前提にしてください。

実装上の推奨: 最初から操作別の分岐骨格だけ作り、`arc_interpolate` を最初は線形の仮実装にしておく。

```python
def interpolate(s, entry, operation, axes_by_op):
    kind = operation["kind"]
    if kind.startswith(("rotation_", "screw_")):
        return arc_interpolate(s, ...)  # 最初は linear でもよい
    else:
        return (1 - s) * start + s * end
```

### Q. `transformed_cart` をアニメーション終点として使う設計で問題ないか

問題ありません。

- 結晶: `animation_frac @ lattice`（最近接周期像）→ 正しい終点 ✓
- 分子: `rotation @ cart + translation`（raw）→ 正しい終点 ✓

円弧補間でも `transformed_cart` を終点チェックとして使えます（Rodrigues 公式の結果と一致するはず）。

### Q. 周期境界の `animation_frac` 最近接像の考え方でよいか

正しく、仕様書 Section 16.2 と完全に一致しています ✓

アニメーション終了時に `wrapped_frac` へ戻す処理（Section 16.2 末尾の注記）は GUI 実装時に必要になりますが、今の PyVista 単体ツールでは不要です。

### Q. JSON schema に追加しておくべき情報はあるか

**`angle_deg` を `RenderOperationData` に追加することを推奨します。**

現在 `RenderOperationData` には `kind` と `order` のみ。円弧補間で回転角の大きさが必要になります。

- `order=2` → 角度 180°、`order=3` → 120° と計算できますが、
- `SymmetryOperationInfo.angle_deg` はすでに計算済み（符号なし絶対値）なので、そのまま渡す方が確実。

```python
# render_data.py の RenderOperationData に追加
angle_deg: float | None  # rotation/screw のとき設定、それ以外 None
```

回転方向（符号）は viewer 側で start/end 座標と軸の外積から決定します。

パズル化に必要なもの（`atom_to_atom`、`operation_indices`）は現在の schema で揃っています ✓

### Q. 仕様書とのズレとして気になる点

1点のみ：

**補間方式**（Section 16.3）: 仕様書は回転・らせん軸の円弧補間を「最初から」実装するよう指定しています。
現在の `CURRENT_STATUS.md` の「まず線形」はそれとやや異なります。
Codex に伝える際は「線形は一時的、すぐに arc へ切り替える前提」と明示してください。

それ以外は仕様書との整合性は取れています：
- 最近接周期像: Section 16.2 と一致 ✓
- `RenderData` の座標変換: Section 11 と一致 ✓
- `operation_indices` の保持: Section 4.4 の要件を満たす ✓

---

## コード最適化レビュー（2026-05-15）

### 最適化内容

#### `crystal_viewer/atom_mapping.py`

- `choose_nearest_periodic_image` のトリプルネストループを NumPy ベクトル化に置き換え
- 27 シフトを `_PERIODIC_SHIFTS` としてモジュールレベルで事前計算（import 時に一度だけ生成）
- `np.einsum("ij,ij->i", disp, disp)` で全候補の二乗距離を一括計算

#### `crystal_viewer/render_data.py`

- `render_data_from_crystal`：`symbols` dict をループ前に一度だけ構築するよう変更
  - 変更前：`axis_label()`/`plane_label()`/`center_label()` が呼ばれるたびに dict を再生成
  - 変更後：`symbols = {op.index: op.international_symbol for op in result.operations}` を一度だけ作り、`operation_group_label(..., symbols)` に渡す
- `render_data_from_molecule`：同様に `symbols` dict を一度だけ構築
- `bounds_points()` の二重呼び出しを廃止。`bpoints` を一度計算して `bmin`/`bmax` 両方に使う
- 分子用ヘルパー関数の引数を `result: MoleculeAnalysisResult` → `symbols: dict[int, str]` に変更し、呼び出し元でビルド済み dict を渡す設計に統一
- デッドコードの削除：`axis_label`、`plane_label`、`center_label`、`molecular_axis_label`、`molecular_plane_label`、`molecular_center_label` の 6 関数を削除（いずれも `operation_group_label` の薄いラッパーで、最適化後に未使用になった）

### 動作確認

```bash
.venv/bin/python -m py_compile crystal_viewer/render_data.py crystal_viewer/atom_mapping.py  # OK
.venv/bin/python tools/export_analysis_json.py examples/water.xyz --mode molecule -o exports/water.json
.venv/bin/python tools/export_analysis_json.py 'F2 Pd.cif' --mode crystal -o exports/f2_pd.json
.venv/bin/python tools/view_json_pyvista.py exports/water.json --list-operations   # 4 operations, all mapping=ok
.venv/bin/python tools/view_json_pyvista.py exports/f2_pd.json --list-operations   # 12 operations, all mapping=ok
```

全て正常。`angle_deg` も正しく出力されている（water C2 → 180°、f2_pd rotation_3 → 120°）。

### 仕様書との整合性

変更後も全て仕様書に準拠：

- `operation_group_label` のロジックは変更なし ✓
- `bounds_min`/`bounds_max` の計算結果は変更なし ✓
- `render_data_from_crystal` / `render_data_from_molecule` の出力 schema は変更なし ✓
- `RenderData` の全フィールドが正しく埋まっていることを `--list-operations` 出力で確認 ✓

---

## アニメーションレビュー（`tools/view_json_pyvista.py`）（2026-05-15）

### 動作確認

```bash
.venv/bin/python tools/view_json_pyvista.py exports/water.json --operation 0 --animate --animation-output exports/water_op0_animation.gif
.venv/bin/python tools/view_json_pyvista.py exports/f2_pd.json --operation 1 --animate --animation-output exports/f2_pd_op1_animation.gif
```

両 GIF とも正常生成（water: 465 KB、f2_pd: 707 KB）。

### ロジックテスト（全パス OK）

以下を確認:

- `evaluate_path(path, 1.0) == entry["transformed_cart"]` — water op0/op1、f2_pd op1/op4 の全原子（誤差 < 1e-6）
- `evaluate_path(path, 0.0) == start` — rotation / screw / mirror / glide / inversion 全タイプ
- sequential パスの s=0.5 境界での連続性（diff < 1e-3）
- フォールバック: 軸なし→ linear、平面なし→ linear、中心なし→ linear
- `s` のクリッピング: s<0 → 0、s>1 → 1 に補正される

### 正常な部分

| 項目 | 評価 |
|------|------|
| `build_operation_path` の種別分岐順序 | `screw` が `rotation` より先に評価される ✓ |
| `signed_angle_to_target` の符号決定 | +/-angle を試して target に近い方を選ぶ ✓ |
| screw 分解（回転→平行移動） | `ANIMATION_DESIGN.md` Section「Screw operations」通り ✓ |
| glide 分解（鏡映→平行移動） | 仕様通り ✓ |
| improper 分岐（rotoinversion/rotoreflection） | 設計上適切 ✓ |
| GIF 出力パス | `open_gif` → `write_frame` ループ → `close` の順序が正しい ✓ |
| residual 補正 | 各パスで `target - 純変換先` を保存し、`s` に比例して加算することで終点が必ず `transformed_cart` になる ✓ |

### バグ（1件）: インタラクティブアニメーションが視覚的に機能しない → **修正済み**

Claude が指摘し、Codex が commit `8ac46e2` および `76a1b2f` で対応済み。

- `--animation-fps` オプション（デフォルト 10.0）を追加
- `time.sleep(1.0 / fps)` をフレームループに追加
- `plotter.open_gif(..., fps=fps)` へ fps を渡すよう変更

### 軽微な観察（修正不要）

- `evaluate_path` の `mirror` タイプで `reflect_point` を毎フレーム再計算している。`s` に依存しない定数なので `build_path` 時に保存すれば効率化できるが、パフォーマンス上の影響は小さい。
- `improper_path` は現在のテストデータ（water C2v、F2Pd P2₁3）では実行されない。今後 Sn 操作を持つ点群でテストが必要。
- インタラクティブパスで `plotter.show()` が2回呼ばれているが（263行目と267行目）、PyVista 0.48 ではエラーにならない。

### 追加修正（Codex）

F2 Pd の screw_2 GIF で、原子ごとに別々の二回螺旋軸を使っているように見える問題を確認。

原因:

- `AtomMappingEntry.transformed_cart` は最近接周期像。
- screw操作では、最近接像を原子ごとに選ぶと、選択した1本のscrew軸と整合しない周期像になることがある。
- その結果、回転後の残差が軸方向だけでなく横方向にも出て、同じ対称操作に見えにくい。

修正:

- crystal animationでは `transformed_frac + [-1,0,1]^3` から周期像候補を作る。
- rotation/screwでは、選択した軸まわりに回転した後の残差が軸方向に最も近い候補を選ぶ。
- mirror/glideでは、鏡映後の残差が面内方向に最も近い候補を選ぶ。
- インタラクティブ再生用に `--animation-fps` と `time.sleep()` を追加。

確認:

```bash
.venv/bin/python -m py_compile tools/view_json_pyvista.py
.venv/bin/python tools/view_json_pyvista.py exports/f2_pd.json --operation 1 --animate --animation-frames 8 --animation-output exports/f2_pd_op1_animation_fixed.gif
.venv/bin/python tools/view_json_pyvista.py exports/water.json --operation 0 --animate --animation-frames 8 --animation-output exports/water_op0_animation_fixed.gif
.venv/bin/python tools/view_json_pyvista.py exports/water.json --operation 1 --animate --animation-frames 8 --animation-output exports/water_op1_mirror_animation_fixed.gif
```

F2 Pd operation 1 では、全原子について「回転後の残差」の垂直成分が `1.4e-15` 以下になり、同じ選択screw軸に整合することを確認。

### 追加修正（Element selection and speed）

ユーザー確認で、アニメーション速度が速いこと、また「実際に使っている軸だけを表示したい」要望を確認。

修正:

- `--animation-fps` のデフォルトを `10` に変更。
- GIF出力でも `plotter.open_gif(..., fps=...)` へ `--animation-fps` を渡すようにした。
- `--list-elements` を追加し、指定operationに対応する軸・面・中心の候補を表示できるようにした。
- `--element-index N` を追加し、複数軸/面/中心がある場合に、アニメーション基準となる要素を選べるようにした。
- `--element-index` 指定時は、その要素だけを表示し、アニメーションパスも同じ要素を使う。
- 存在しない `--element-index` はCLIエラーにする。

確認:

```bash
.venv/bin/python tools/view_json_pyvista.py exports/f2_pd.json --operation 1 --list-elements
.venv/bin/python tools/view_json_pyvista.py exports/f2_pd.json --operation 1 --element-index 2 --screenshot exports/f2_pd_op1_axis2_only.png
.venv/bin/python tools/view_json_pyvista.py exports/f2_pd.json --operation 1 --element-index 0 --animate --animation-frames 12 --animation-fps 6 --animation-output exports/f2_pd_op1_axis0_slow.gif
.venv/bin/python tools/view_json_pyvista.py exports/f2_pd.json --operation 1 --element-index 2 --animate --animation-frames 12 --animation-fps 6 --animation-output exports/f2_pd_op1_axis2_slow.gif
.venv/bin/python tools/view_json_pyvista.py exports/water.json --operation 1 --element-index 0 --animate --animation-frames 12 --animation-fps 6 --animation-output exports/water_op1_mirror_slow.gif
```

F2 Pd operation 1 の4本の候補軸すべてで、回転後の残差が選択軸方向に揃うことを確認（垂直成分最大 `1.7e-15` 未満）。

反転と映進は現在のサンプルJSONに実操作がないため、関数レベルで確認:

```text
inversion:
  start -> inversion center -> inverted target

glide:
  start -> mirrored point -> translated target
```

---

## 直近3コミットレビュー（`a6897cf` / `8ac46e2` / `76a1b2f`）（2026-05-15）

### 変更概要

| コミット | 内容 |
|---------|------|
| `a6897cf` Add primitive symmetry animations | アニメーション基盤（`--animate`、全パスタイプ、GIF出力）を新規実装 |
| `8ac46e2` Align crystal animation targets | 周期像選択の改善（`animation_target`）、インタラクティブ fps バグ修正 |
| `76a1b2f` Add animation element selection | `--element-index` / `--list-elements` 追加、GIF fps 反映 |

### ロジック検証（Claude による独立確認）

以下をすべてパス:

- `evaluate_path(path, 1.0)` の終点が、全パスタイプ（rotation/screw/mirror/glide/inversion）で正確に selected target に一致（誤差 < 1e-12）
- `evaluate_path(path, 0.0)` が start と一致
- sequential パス（screw/glide）の s=0.5 境界で連続性（diff < 1e-3）
- 全フォールバック（軸なし/面なし/中心なし）で linear に降格 ✓
- `s` クリッピング（<0 → 0、>1 → 1）✓
- `animation_target` の返す周期像が `transformed_frac + [-1,0,1]^3` の有効な格子点であること — water/f2_pd 全原子で確認 ✓
- `element_index=0/1` を指定しても終点がそれぞれ有効な周期像 ✓

### 正常な部分

| 項目 | 評価 |
|------|------|
| `animation_target`: rotation/screw | 純回転結果に対して垂直残差が最小の候補を選ぶ設計が正しい ✓ |
| `animation_target`: mirror/glide | 鏡映結果に対して法線方向残差が最小の候補を選ぶ設計が正しい ✓ |
| `animation_target`: molecule | `transformed_frac` が None のとき候補が1件だけ → `default_target` をそのまま返す ✓ |
| `signed_angle_to_target` と `animation_target` の連携 | 角度符号決定に `default_target`（= `entry["transformed_cart"]`）を使い、その後最適周期像を選択する順序が正しい ✓ |
| `--list-elements` の出力 | 軸・面・中心の各タイプごとにインデックスを表示し、`--element-index N` と対応している ✓ |
| `--element-index` の validation | 全タイプで範囲外の場合は `parser.error` で終了 ✓ |
| `_PERIODIC_SHIFTS` の重複定義 | `atom_mapping.py` と `view_json_pyvista.py` で同じ定数を別途定義。viewer が crystal_viewer を import しない設計なので意図的。バグではない |

### 軽微な設計上の観察

**`has_element_index` の検証範囲について:**

`has_element_index` はいずれかのタイプ（axes/planes/centers）で `element_index` が範囲内なら True を返す。
一方 `selected_elements` は各タイプごとに独立してインデックスを適用する。

例：operation 1 に axes が 4 本、planes が 2 枚ある場合:
- `--element-index 3` → 検証 True（4本の軸で有効）
- 表示：axis[3] は選択されるが、planes は `element_index=3 >= 2` で空になる（planes 非表示）
- `print_elements` がタイプ別インデックスを表示するため、ユーザーは使用前に確認可能

バグではなく設計の選択。現在のサンプルデータ（screw軸のみ、面なし）では問題が顕在化しない。

### バグなし・追加修正なし

3コミットの変更について、動作上のバグは見つかりませんでした。

---

## Jacobsite 追加確認（2026-05-15）

`Jacobsite.cif` を追加し、F2 Pd 以外の高対称結晶でも JSON export と最小ビューアの代表操作を確認した。

### 解析結果

| 項目 | 結果 |
|------|------|
| formula | `Mn(FeO2)2` |
| space group | `227 Fd-3m` |
| point group | `m-3m` |
| sites | 56 |
| operations | 192 |
| centers / axes / planes | 48 / 144 / 36 |

### 確認した代表操作

| operation | kind | 確認内容 |
|-----------|------|----------|
| `1` | `screw_4` | `--element-index 0` で単一軸を表示し、sequential path を生成 |
| `4` | `rotation_2` | 回転 path を生成。一部の不動原子は linear fallback |
| `24` | `inversion` | inversion path を生成 |
| `25` | `rotoinversion_or_improper_4` | schema v3 では操作行列から軸・角度・中心を復元し、rotation -> inversion path を生成 |
| `26` | `glide` | `--element-index 0` で単一面を表示し、mirror -> translation の sequential path を生成 |
| `31` | `mirror` | mirror path を生成。一部の面上/退避原子は linear fallback |

### exports 整理

- `exports/` 直下は共有用JSONのみ: `f2_pd.json`, `water.json`, `jacobsite.json`
- 確認用GIF/PNGは `exports/checks/` に退避し、Git管理対象外にした

### 残る設計メモ

回反/回映系は、schema v3 の操作行列を使って回転軸・角度・中心を復元できる。
Jacobsite の `op 25` は中心だけが RenderData element として出ていたが、viewer 側で `matrix_cart` から rotoinversion の回転成分を取り出して rotation -> inversion に分解する。

---

## 代表原子ベースの周期像選択（2026-05-15）

全原子アニメーションで、原子ごとに独立して最も近い周期像を選ぶと、同じ対称操作ではなく複数の等価操作が混ざったように見える問題があった。

対応:

- `--animation-scope representative` を追加し、代表原子だけを動かせるようにした
- `--animation-scope all` では、代表原子で決めた整数格子シフトを全原子に共有するようにした
- `--representative-atom N` で、その共有シフトを決める原子を指定できるようにした

これにより、代表原子アニメーションで見える操作を、そのまま全原子へ適用する構造になった。

### 追加確認

Jacobsite を基準に再確認したところ、`op 4` (`rotation_2`) で周期シフトは共有されていたが、180度回転の符号が原子ごとに `+180/-180` に分かれる問題があった。
終点は同じでも中間経路が左右に割れるため、代表原子で決めた回転角の符号も全原子へ共有するよう修正した。

確認結果:

- `op 1` (`screw_4`): 全原子 `+90`
- `op 4` (`rotation_2`): 全原子 `+180`
- `op 26` (`glide`): 全原子で同じ整数格子シフト
- 存在しない `--representative-atom` 指定時はアニメーションを中止

### 操作行列ベースへの修正

その後の Jacobsite 確認で、rotoinversion が中心フォールバックのため大きくばらつく問題が見つかった。
`RenderOperationData` に `matrix_frac`, `translation_frac`, `matrix_cart`, `translation_cart` を追加し、JSON schema を v3 に更新した。

確認結果:

- `op 1` (`screw_4`): 全原子 `+90`, residual `0`
- `op 4` (`rotation_2`): 全原子 `+180`, residual `~4.6e-15`
- `op 25` (`rotoinversion_or_improper_4`): `rotation -> inversion`, 全原子 `+90`, residual `~3.7e-15`
- `op 26` (`glide`): `mirror -> translation`, residual `0`

---

## Jacobsite アニメーション変更レビュー（Claude）（2026-05-15）

レビュー対象: commit `6758e12` → `ed2ade7`（4コミット）

### 数値検証（全件パス）

Codex 指定の数値チェックを独立実行:

```
ok 1 screw_4             [90.0]  0.00e+00
ok 4 rotation_2          [180.0] 4.62e-15
ok 24 inversion          []      0.00e+00
ok 25 rotoinversion_4    [90.0]  3.66e-15
ok 26 glide              []      0.00e+00
ok 31 mirror             []      7.64e-15
```

全原子の residual ノルムが 1e-10 未満。schema_version=3 も確認済み。

### Q1: `matrix_cart` / `translation_cart` の変換式は正しいか

```python
matrix_cart = lattice.T @ W @ inv(lattice.T)
translation_cart = t @ lattice
```

**正しい。** プロジェクトの row-vector 規約（`x_cart = x_frac @ L`）では、列ベクトル表現の変換 `x' = Wx + t`（spglib）は Cartesian で `x'_col = (L^T W (L^T)^{-1}) x_col + (L^T t)` になる。NumPy の `t @ L` は `L^T @ t` と値が等しいため式が成立する。

全 192 操作・全原子サンプルで `matrix_cart @ x_cart + translation_cart ≈ (W @ frac + t) @ lattice`（mod 周期）を確認済み。

### Q2: rotoinversion で `rotation = -matrix_cart` は正しいか

**正しい。** 回折逆転操作の行列は `W_cart = -R_proper`（det = -1）。
`-W_cart = R_proper` は det = +1 かつ直交行列（orthogonality error < 5e-16）。Jacobsite の全 rotoinversion_4 と rotoinversion_6 で確認済み。

### Q3: `effective_operation_center` の pinv(I+R) の堅牢性

**堅牢。** `I+R` の最小特異値は全 rotoinversion 操作で ≥ 1.0（`I+R` が可逆）。inversion（R=-I → I+R=0）は `kind == "inversion"` で先に分岐するためこのコードは呼ばれない。`pinv` は安全策として適切。

全 rotoinversion 操作の計算中心を固定点として検証（`M_cart @ center + t_cart ≈ center` mod 周期）し全件 OK。

### Q4: visual element と affine 操作の不整合（修正済み）

**39 件の不整合を確認、うち 20 件を修正。** `effective_operation_center` が affine 行列から計算した中心と、`render_data["centers"]` の視覚的中心が最大 8.5 Å 離れているケースがあった。

差異の内訳（修正前）:
- **20 件**: 差異が格子ベクトルの整数倍（1軸方向の shift）→ 周期像スナップで修正可能
- **19 件**: 差異が半格子対角方向（diff_frac ≈ [±0.5, ±0.5, ±0.5]）→ 異なる Wyckoff 位置にあり、スナップ不可能

影響:
- アニメーションの pivot/経由点が視覚的な中心マーカーと一致しない
- inversion: アニメーションの中間点（s=0.5 付近）が見える中心ドットとずれる
- rotoinversion: 回転軸の通過点がずれる
- 原子の**終点**は affine ターゲットから正しく計算されているため**到達位置は正しい**

不整合の例（修正前、Jacobsite, op 72 inversion）:
```
visual center: [3.193, 7.451, 1.064] Å
affine center: [3.193, 3.193, 1.064] Å  (diff = -0.5*b_vector)
```

**修正実施（2026-05-15）**: `effective_operation_center` に周期像スナップを追加した。

```python
# tools/view_json_pyvista.py: effective_operation_center 内
shift_is_zero = shared_shift is None or not np.any(np.asarray(shared_shift, dtype=float))
if center is not None and shift_is_zero:
    lattice = np.asarray(unit_cell["lattice"], dtype=float)
    visual_pt = np.asarray(center["point_cart"], dtype=float)
    diff_frac = (point - visual_pt) @ np.linalg.inv(lattice)
    point = point - np.round(diff_frac) @ lattice
```

注意点:
- `shared_shift != 0` の場合はスナップしない（視覚的中心は unshifted 操作に対応しているため）
- 残る 19 件（op 72, 73, 75, 80, 87, 94, 95, 120, 121, 131, 132, 136, 137, 168, 171, 178, 180, 188, 190）は diff_frac ≈ [±0.5, ±0.5, ±0.5] で全周期像が等距離。affine 中心を使用する（位置は正しい）
- Jacobsite の6つの benchmark 操作（1, 4, 24, 25, 26, 31）は影響なし
- 数値チェック（全残差 < 1e-10）は修正後も全件通過

### Q5: mirror / inversion で固定原子が多い — バグか設計か

**設計として正しい。** 対称操作の固定点にある原子が動かないのは数学的に正しい。ただし教育用ビューアとしては「なぜ止まるのか」が分かりにくい。

推奨: 現行の挙動（固定点原子は静止）を維持しつつ、将来的には `--animation-scope representative` でデフォルトを変えるか、固定原子のハイライト表示を追加するとよい。

### Q6: residual 補正による視覚的非整合の再発

**残差ノルムは全て < 1e-14 — 視覚的影響なし。** 各操作タイプの residual が全原子でほぼゼロかつ方向も一致しており、non-uniform な動きの原因にはなっていない。

### 視覚的違和感の原因分析

Codex が挙げた4つの違和感について:

| 違和感 | 原因 | バグか設計か |
|--------|------|------------|
| 一部の原子が逆回転に見える | `shared_rotation_angle` 導入前の残存問題か、Q4の center ずれの影響 | Q4 修正（20件）で改善。19件はWyckoff位置の不一致で残存 |
| rotoinversion/rotoreflection で原子がばらばらに動く | Q4の center 不整合が主因。格子像スナップ可能な20件は修正済み | 部分修正。残19件は display inconsistency のみ（アニメーション正確性は維持） |
| 固定点上の原子だけ止まる | 数学的に正しい固定点挙動 | 設計。教育的注釈で補うことを推奨 |
| mirror/inversion で「なぜ止まるのか」が分からない | 同上 | 設計 |

### 追加確認: residual 一貫性（Q6 詳細）

| op | kind | 残差最大 | 残差最小 | 一貫性 |
|----|------|---------|---------|--------|
| 1 | screw_4 | 0 | 0 | ✓ |
| 4 | rotation_2 | 4.6e-15 | 3.1e-16 | ✓ |
| 25 | rotoinversion_4 | 3.7e-15 | 0 | ✓ |
| 31 | mirror | 7.6e-15 | 3.3e-15 | ✓ |

residual の大きさは全て機械精度以下。方向の分散もなし。

### Codex 追確認（2026-05-15）

上記レビューを確認した結果、Q4 の「visual element と affine 操作の不整合」は重要な指摘として妥当。
ただし「修正済み」「全て residual が機械精度以下」という表現は、Jacobsite の benchmark 操作（1, 4, 24, 25, 26, 31）に限定して読むべき。

追加で Jacobsite 全 192 操作を `element_index=0` で走査したところ、パス生成エラーはなかったが、rotation_3 系で大きな residual が残る操作があった。

例:

```text
op 12  rotation_3  element_index=0  max_residual ~14.75 Å
op 106 rotation_3  element_index=0  max_residual ~14.75 Å
```

原因:

- `render_data["axes"]` には、同じ operation index に対して複数の周期的に等価そうな軸が出る。
- しかし、その全てが現在の affine operation + integer lattice shift と整合するとは限らない。
- 例: Jacobsite `op 12` は `element_index=1` の原点軸では residual が機械精度になるが、`element_index=0` では大きくずれる。

追加修正:

- `effective_operation_center` の周期像スナップは、スナップ後の点が同じ affine operation の固定点として成立する場合だけ採用するようガードを追加した。
- これにより `op 94` のような rotoinversion_6 で、視覚中心へ無条件に寄せて residual を悪化させる問題を防いだ。

残る課題:

- axis/center/plane の候補表示時点で、現在の operation affine と整合しない要素を除外または警告する必要がある。
- 特に rotation_3 系は、`--list-elements` に出る候補のうち一部だけが実際の操作と整合する。
- したがって次の改善は「operation matrix に対する symmetry element compatibility check」を viewer 側または RenderData 生成側に入れること。

---

## 周期境界表示の改善（2026-05-15）

ユーザー確認で、原点や周期境界上の原子だけが固定されて見える違和感の一因として、単位格子外の等価な周期像が表示されていないことが分かった。

対応:

- 結晶では表示用原子を fractional window `[-0.5, 1.5]` に拡張した。
- これは表示だけの拡張で、AtomMapping や animation path は元の source atom ごとに1回だけ計算する。
- 周期像として複製された表示原子は、元原子の path に一定の lattice shift を足して同じ動きをする。

確認:

```text
Jacobsite source atoms: 56
display instances: 478
animation paths for op25: 56
```

この方法なら境界上の等価点が見えるため、原点だけが孤立して固定されているように見える問題を軽減できる。
一方、非並進の対称操作で等価な別原子に同じ path を流用するのは、軸・面からの距離が異なるため一般には正しくない。今回共有しているのは lattice translation による表示クローンのみ。

### 非対称単位と展開原子の対応

ユーザーの指摘通り、Jacobsite の CIF には Mn/Fe/O が1つずつしか書かれておらず、残りの原子は空間群操作から生成される。

対応:

- `AsymmetricUnitSite` を追加し、CIF に直接書かれた atom_site を保持する。
- `AtomSite.asymmetric_index` と `AtomSite.generation_operation_index` を追加し、展開原子がどの CIF 代表原子・どの空間群操作から生成されたか記録する。
- `RenderData.asymmetric_atoms` と JSON schema v4 に反映する。

Jacobsite の確認結果:

```text
asymmetric atoms: 3  (Mn1, Fe1, O1)
expanded atoms: 56
Mn from Mn1: 8
Fe from Fe1: 16
O from O1: 32
```

設計判断:

- アニメーション path は今のところ expanded atom 56個ぶん計算する。
- CIF 代表原子3個だけの path を全 expanded atom に流用するのは、非並進対称操作が一般に可換ではないため危険。
- ただし、将来の代表原子モード・orbit 選択・パズル化では、この asymmetric/expanded 対応を使える。
