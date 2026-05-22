# コードレビューメモ（Codex向け共有）

Claude によるレビュー結果をまとめています。
実装の判断材料として参照してください。

---

## 動作確認済み（全て正常）

以下のツールが正常に動作することを確認しました。

```bash
.venv/bin/python tools/analyze_molecule.py examples/molecules/water.xyz     # C2v
.venv/bin/python tools/analyze_molecule.py examples/molecules/methane.xyz   # Td
.venv/bin/python tools/analyze_structure.py examples/structures/f2_pd.cif           # P2_13, 12 ops, 24 axes
.venv/bin/python tools/inspect_render_data.py examples/structures/f2_pd.cif --mode crystal
.venv/bin/python tools/inspect_render_data.py examples/molecules/methane.xyz --mode molecule
.venv/bin/python tools/inspect_atom_mapping.py examples/structures/f2_pd.cif --mode crystal
.venv/bin/python tools/inspect_atom_mapping.py examples/molecules/water.xyz --mode molecule
.venv/bin/python tools/export_analysis_json.py examples/structures/f2_pd.cif --mode crystal -o exports/f2_pd.json
.venv/bin/python tools/export_analysis_json.py examples/molecules/water.xyz --mode molecule -o exports/water.json
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
.venv/bin/python tools/export_analysis_json.py examples/structures/f2_pd.cif --mode crystal -o exports/f2_pd.json
.venv/bin/python tools/export_analysis_json.py examples/molecules/water.xyz --mode molecule -o exports/water.json
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

仕様書 `docs/archive/specs/codex_final_spec_crystal_symmetry_viewer.md` Section 16 を参照しながら確認しました。

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
.venv/bin/python tools/export_analysis_json.py examples/molecules/water.xyz --mode molecule -o exports/water.json
.venv/bin/python tools/export_analysis_json.py examples/structures/f2_pd.cif --mode crystal -o exports/f2_pd.json
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

`examples/structures/jacobsite.cif` を追加し、F2 Pd 以外の高対称結晶でも JSON export と最小ビューアの代表操作を確認した。

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

---

## 直近4コミットレビュー（Claude）（2026-05-15）

対象: `2cf035b` → `0138694` → `980684e` → `a23eb4c`

### commit `2cf035b` — Add Claude review request

ドキュメントのみ（現在は `docs/archive/reviews/CLAUDE_REVIEW_REQUEST_JACOBSITE_ANIMATION.md` に移動）。コードなし。問題なし。

### commit `0138694` — Review Jacobsite animation center handling

Q4修正の実装を確認。

```python
# effective_operation_center 末尾の実装
shift_is_zero = shared_shift is None or not np.any(np.asarray(shared_shift, dtype=float))
if center is not None and shift_is_zero:
    ...snapped = point - np.round(diff_frac) @ lattice
    if np.linalg.norm(matrix @ snapped + translation - snapped) < 1e-8:
        point = snapped
```

2段階のガードが正しく機能している:
- `shift_is_zero` guard: `shared_shift != 0` 時はスナップ計算自体をスキップ
- fixed-point validation: スナップ後の点が同じ affine operation の固定点として成立する場合だけ採用（19件の body-diagonal stuck ケースを正しく棄却）

**数値確認: 6 benchmark 操作で残差 < 1e-10 ✓**

### commit `980684e` — Show half-cell periodic atom images

`display_fractional_shifts` が `[-0.5, 1.5]^3` の範囲で周期像を生成する設計を確認。

| 原子位置 | display instances |
|---------|-----------------|
| frac=[0,0,0]（コーナー） | 8 |
| frac=[0,0.5,0.5]（FCC面心） | 18 |
| frac=[0.375,0.375,0.375]（一般位置） | 8 |
| Jacobsite 全体 | 478（56原子から） |

`update_animated_atoms` での `center = center + display_shift_cart` は正しい。DisplayClone は元原子の path に固定 lattice shift を加算するだけ（ANIMATION_DESIGN.md の設計通り ✓）。

**観察（バグではない）**: FCC 面心原子が 18 インスタンスになるのは数学的に正しいが、視覚的に密集する可能性がある。将来的に上限を設けるか、ユーザーが表示范围を制御できるようにする余地がある。

### commit `a23eb4c` — Track asymmetric unit atom origins

`identify_asymmetric_source` の正確性を確認。Jacobsite 全 56 原子が正しく割り当てられた:

```text
asym 0 (Mn): 8 atoms  — 全て {'Mn'} ✓
asym 1 (Fe): 16 atoms — 全て {'Fe'} ✓
asym 2 (O):  32 atoms — 全て {'O'}  ✓
total: 56/56 assigned
```

`parse_cif_float("0.375(1)")` → 0.375 ✓、`wrap_frac` の near-0/near-1 処理 ✓、schema_version=4 反映 ✓。

軽微な観察:
- CIF を pymatgen と `CifParser` で 2 回 parse している（低優先度）。
- `wrap_frac(rotation @ source_frac + translation)` + `delta - round(delta)` の周期比較は通常の CIF 座標（有理数）で問題なし。

---

## Codex 既報の `rotation_3` residual 問題の追確認（Claude）（2026-05-15）

Codex が「rotation_3 系で大きな residual が残る」と報告した件を全 192 操作で検証。

**Jacobsite で `element_index=0` 使用時に residual > 0.1 Å の操作: 43 件。**

代表例:

| op | kind | element_index=0 の最大 residual | 正しい index での residual |
|----|------|---------------------------------|---------------------------|
| 12 | rotation_3 | 14.75 Å | `=1` で 0.00e+00 |
| 10 | rotation_3 | 13.91 Å | — |
| 37 | mirror | 6.02 Å | — |
| 57 | rotation_2 | 6.02 Å | — |

**原因**: `render_data["axes"]` に同じ operation index で複数の等価軸が登録されている。`element_index=0` が選ぶ軸が、代表原子の位置と整合しない場合に rotation 弧の pivot がずれて大きな residual が出る。

**op 12 (rotation_3) の確認**:
- `element_index=0`: max_residual = 14.75 Å（不整合な軸を選択）
- `element_index=1`: max_residual = 0.00e+00（正しい軸）
- `element_index=2`: max_residual = 8.52 Å（不整合）

**現状の影響**: `--list-elements` + `--element-index` で手動選択すれば回避可能。デフォルト（`element_index=0`）では 192 操作のうち 43 件が不正確なアニメーションになる。6 benchmark 操作（1, 4, 24, 25, 26, 31）は影響なし。

**推奨修正（次ステップ候補）**: `animation_paths` 内で、`element_index=None` かつ `animation_scope='all'` の場合、代表原子の residual が最小となる element_index を自動選択するロジックを追加する。

### Codex 対応（2026-05-15）

対応:

- `element_index=None` の通常利用では、候補の axis/plane/center を全部試し、path residual が最小になる要素を自動選択するようにした。
- rotation / screw / mirror / inversion / rotoinversion では、選択した要素上の点を固定するために必要な integer lattice shift を優先して使うようにした。
- `--element-index N` を明示した場合は従来通りその要素を尊重する。つまり、ユーザーが不整合な候補を手動指定した場合は、その候補に基づく動きを表示する。

確認:

```text
Jacobsite 全192操作, element_index=None:
large residual count: 0

op10  rotation_3: auto ~6.4e-15, forced element_index=0 ~13.9 Å
op12  rotation_3: auto ~5.3e-15, forced element_index=0 ~14.7 Å
op37  mirror:     auto ~2.3e-15, forced element_index=0 ~6.0 Å
op57  rotation_2: auto ~5.2e-15, forced element_index=0 ~6.0 Å
op114 rotation_3: auto ~1.1e-14, forced element_index=0 ~13.9 Å
```

これにより、デフォルトでは異なる軸・面で対称操作しているように見える問題をかなり抑えられる。

### Claude 独立検証（2026-05-15、commit `d73c554`）

**全192操作で auto-select の max residual = 0 件 (> 0.1 Å) を確認。** 6 benchmark 操作も全件通過。

`symmetry_element_shared_shift` の動作検証:

| op | kind | 互換要素 | auto residual | element_index=0 residual |
|----|------|---------|--------------|--------------------------|
| 10 | rotation_3 | axis[1] のみ | 6.42e-15 Å | 13.905 Å |
| 12 | rotation_3 | axis[1] のみ | 5.33e-15 Å | 14.748 Å |
| 37 | mirror | plane[1] のみ | 2.32e-15 Å | 6.021 Å |
| 57 | rotation_2 | axis[1,3] | 5.18e-15 Å | 6.021 Å |

`symmetry_element_shared_shift` は `required = (p - (M @ p + t)) @ inv(L)` が整数ベクトルになる要素だけを「互換」と判定し、そのシフトを `shared_shift` として採用する。互換でない要素は None を返し、代表原子のシフトにフォールバックする。

設計として正しい:
- 互換要素の特定: `required` が整数ベクトルになる ↔ 選んだ visual element 上の点が affine 操作の固定点（mod 格子）である ✓
- スコアリング: 全原子の最大 residual で評価 → 互換でない要素は大きな residual で自動排除 ✓
- `--element-index N` 明示時はスキャンをスキップし従来通り動作 ✓
- `max_count=0`（identity, pure_translation）は `element_index=None` を1候補として評価 ✓

**軽微な観察（バグではない）**:

1. `animation_paths` は `select_animation_context` から返った `axis` と `shared_angle` を受け取った後に `effective_rotation_axis` と `shared_rotation_angle` を再計算している。これらの呼び出しは idempotent なので結果は同じだが、冗長。

2. パフォーマンス: 全192操作の auto-select で 2.64 秒（13.7 ms/op）。inversion 操作は 8 候補 × 56 原子のスコアリングが発生する。対話的操作切り替えでは目立つ可能性あり。スコアリングを全原子ではなく代表原子だけで行う最適化余地がある（正確性 vs 速度のトレードオフ）。

3. `glide` は `symmetry_element_shared_shift` で非対応（kind チェックに含まれない）。glide 操作では plane 上の点が操作後に glide 成分分ずれるため返り値は常に None。これは意図的で正しい。

---

## 表示クローンのアニメーションバグ（Claude 診断）（2026-05-16）

Codex の「アニメーション修正方針」相談に対するレビュー。

### 根本原因の再診断

Codex の診断（残差補正が主因）は部分的に正しいが、**実際の主因は `980684e` で導入した表示クローンの animation 計算**です。

`d73c554` の auto-select + element_shift 適用後、benchmark 操作の全原子 residual は機械精度（< 2.2e-15 Å）。視覚的に意味のある residual はすでに存在しません。

**本当の問題:** `update_animated_atoms` が表示クローンを `evaluate_path(primary_path, s) + display_shift_cart` で動かします。これは「主原子のアークを並進したもの」であり、シフトが回転軸に垂直な場合、クローンは選択した軸と `shift_cart` だけずれた別の等価軸の周りを回転しているように見えます。

数値確認（s=0.5 でのアーク誤差、軸に垂直なシフトを持つクローンの例）:

```text
op 4  (rotation_2): 表示クローンのアーク誤差 最大 17.030 Å
op 1  (screw_4):    表示クローンのアーク誤差 最大 15.465 Å
op 31 (mirror):     表示クローンのアーク誤差 最大 12.042 Å
```

軸方向に並行なシフトのクローンは誤差 0（回転で軸方向成分は変化しないため）。垂直成分を持つシフトだけが問題になる。

### 6 つの質問への回答

**Q1 (教育的正当性):** 提案方針は正しい。全インスタンスに affine 変換を直接適用すれば、クローンも同じ軸/面の周りを正しく動く。

**Q2 (atom mapping の役割分離):** 問題なし。atom mapping の役割は「どの原子を動かすか」と「代表原子の選択」に限定してよい。target 提供の役割は affine 変換が代替する。

**Q3 (screw/glide の translation vector 導出):**
affine translation から射影して導出すべき:
- Screw: `v_screw = (t_total · axis_dir) * axis_dir`
- Glide: `v_glide = t_total - (t_total · plane_normal) * plane_normal`

ここで `t_total = t_cart + element_shift @ lattice`。全原子で同一の値になる（atom position 非依存）。

**Q4 (回反/回映の分解):** 現行の `rotation = -matrix_cart → inversion` は正しい。変更不要。

**Q5 (周期境界と連続座標):** 連続座標のまま動かすべき。現行実装もこの方針（affine target = `M @ x + t_total`）。表示クローンも同様に wrap せず連続軌跡で。

**Q6 (等価な別軸への補正を避けるべきか):** Yes。現行で残っている問題は residual 補正（< 2e-15 Å）ではなく、表示クローンが並進されたアークを描く `display_shift_cart` 加算。これが「別の等価軸で動いているように見える」原因。

### 推奨修正（優先度順）

**最重要（視覚インパクト大）**: 表示クローンの animation を修正する。クローンの実際の開始位置（`start + display_shift_cart`）に対して同じ幾何操作を適用する。

```python
# evaluate_path の型情報があれば、axis_point/angle を取り出して clone_start = start + shift で回転
# 最小実装: clone_start を path["start"] の代わりに使って同じ軸で回転
```

具体的には `evaluate_path` に `start_override` を渡すか、`build_operation_path` をクローンの開始位置で呼び出して個別 path を構築する。

**次に重要（コード整理）**: residual フィールドと `+ residual * s` を除去。視覚的影響はほぼゼロだが、コードの意図を明確にする。

**やや重要（設計整合）**: `animation_target` を `operation_affine_target` のみに統一し、atom_mapping の `transformed_cart` への依存を除去。`shared_periodic_shift` も不要になる（`element_shift` に一本化）。

---

## Codex 直近 2 コミット レビュー (2026-05-16)

対象コミット: `d73c554` Auto-select compatible symmetry elements / `a23eb4c` Track asymmetric unit atom origins

### バグなし — 全チェック通過

**数値確認 (schema_version=4 で再実行):**

```text
ok 1  screw_4                     [90.0]  2.66e-15
ok 4  rotation_2                  [180.0] 4.62e-15
ok 24 inversion                   []      0.00e+00
ok 25 rotoinversion_or_improper_4 [90.0]  2.18e-15
ok 26 glide                       []      2.22e-15
ok 31 mirror                      []      7.64e-15
```

全 192 操作を `element_index=None`（auto-select）で実行: **residual > 1e-6 の操作 0 件**。

操作種別ごとの worst residual:

```text
glide:                       5.10e-15
mirror:                      8.14e-15
rotation_2:                  9.78e-15
rotation_3:                  1.05e-14
rotoinversion_or_improper_4: 5.02e-15
rotoinversion_or_improper_6: 1.19e-14
screw_2:                     5.02e-15
screw_4:                     3.97e-15
```

**非対称単位追跡 (a23eb4c):**
- `render_data["asymmetric_atoms"]`: 3 件 (Mn1, Fe1, O1)
- 全 56 原子で `asymmetric_index` 割り当て済み（未割り当て 0 件）
- サイト別: site 0 → 8, site 1 → 16, site 2 → 32（Fd-3m 空間群の Wyckoff 多重度と一致）

**`evaluate_path` の `start_override` (表示クローン修正):**
- 全パス型（rotation / screw / mirror / glide / inversion / rotoinversion / rotoreflection）で start_override が正しく適用されることを確認
- 操作固有の幾何パラメータ（axis_point, plane_point, center）はすべての原子・クローンで共通なので、start だけ置き換えれば正確なアークが得られる
- screw/glide の translation は操作固有量（原子位置非依存）であり、`shared_step_translation` が reference atom から正しく導出している

**`shared_step_translation` の `center=None` 渡し:**
- `animation_target` への `center=None` は意図的な防御処置
- screw/glide 以外では `shared_step_translation` は `None` を返すため影響なし

**冗長な再計算（バグではないが性能への影響あり）:**
`animation_paths` の lines 461–470 で `effective_rotation_axis` と `shared_rotation_angle` を再計算しているが、`select_animation_context`（内部の `build_animation_context` line 603–612）がすでに同じ値を計算して返している。入力が変わらないため結果は同一だが無駄。

### パフォーマンス計測（Jacobsite, 192 操作）

```text
select_animation_context 合計: 1330 ms （6.93 ms/op）
  build_animation_context:      127 ms （0.66 ms/op）
  animation_context_score:     1195 ms （6.22 ms/op） ← ボトルネック
```

候補数分布:

```text
1 candidate: 4 ops
2 candidates: 92 ops
3 candidates: 32 ops
4 candidates: 60 ops
8 candidates: 4 ops
平均 2.9 候補/op
```

`animation_context_score` が全原子（56 件）× 全候補でパスを構築・評価することがボトルネック。

### 安全な高速化案（3 件）

**案 A: early exit when score = 0 （推定 ~40-60% 削減）**

全 192 操作で最終 residual が機械精度であることを確認済み。多くの操作では最初の候補が score=0 になるはず。`select_animation_context` に以下を追加:

```python
for context in candidates:
    score = animation_context_score(
        render_data, operation, mapping, atoms_by_index, context,
        threshold=best_score,   # 案 B と組み合わせる場合
    )
    if score < best_score:
        best_score = score
        best_context = context
    if best_score == 0.0:
        break  # これ以上試す必要なし
```

**案 B: `animation_context_score` に threshold 引数を追加 （案 A と組み合わせると効果的）**

現在の best_score を超えた時点でその候補の評価を打ち切れる:

```python
def animation_context_score(..., threshold: float = float("inf")) -> float:
    worst = 0.0
    for entry in mapping["entries"]:
        ...
        worst = max(worst, max_path_residual(path))
        if worst >= threshold:
            return worst  # これ以上悪くなっても比較結果は変わらない
    return worst
```

**案 C: `animation_paths` の冗長計算を除去 （微小だが確実）**

`select_animation_context` が返す tuple の `axis`（index 0）と `shared_angle`（index 5）はすでに `effective_rotation_axis` と `shared_rotation_angle` を適用済み。`animation_paths` の lines 461–470 を除去し、tuple の値をそのまま使う:

```python
# 変更前 (animation_paths 内)
axis, plane, center, reference_entry, shared_shift, shared_angle = select_animation_context(...)
axis = effective_rotation_axis(operation, axis, center)   # 冗長
shared_angle = shared_rotation_angle(...)                  # 冗長
translation_override = shared_step_translation(...)

# 変更後
axis, plane, center, reference_entry, shared_shift, shared_angle = select_animation_context(...)
translation_override = shared_step_translation(
    render_data, operation, atoms_by_index, reference_entry,
    axis, plane, shared_shift, shared_angle,
)
```

### sequential パスは現在デッドコード

`evaluate_path` と `max_path_residual` に "sequential" 型の処理があるが、`build_operation_path` は "sequential" 型を生成しない。将来用の準備コードとして問題はないが、現時点では未使用。

---

## 32 CIF サンプル 全件検証 (2026-05-16)

`examples/cif/` の 32 CIF ファイルを全件 JSON export してアニメーション residual を確認した。

### エクスポート

全 32 件エラーなしでエクスポート成功。

```text
32 OK, 0 FAIL
```

### 空間群・点群カバレッジ

| 点群 | 件数 | 結晶 |
|------|------|------|
| 1 | 1 | Babefphite |
| -1 | 1 | O9 V5 |
| m | 1 | Tenorite |
| 2/m | 2 | AgCl, Hydrohematite |
| mm2 | 1 | C12H14N4 |
| 222 | 1 | Tridymite |
| mmm | 1 | Bromine |
| 4 | 1 | Pb(Al,Si)4O8 |
| -4 | 1 | SiO2 |
| 4/m | 1 | Ge Hf O4 |
| 4mm | 1 | Cl H4 N O2 |
| -42m | 1 | Adamantane |
| 4/mmm | 2 | NbP, Tin |
| 3 | — | **未収録** |
| -3 | 2 | Bi I3, H11 I N2 O6 |
| 32 | 1 | Tellurium |
| 3m | 1 | Tellurobismuthite |
| -3m | 1 | Antimony |
| 6 | 1 | Thaumasite |
| -6 | — | **未収録** |
| 6/m | 1 | Ho2Rh12As7 |
| 622 | 1 | Edgarite |
| 6mm | — | **未収録** |
| -6m2 | 2 | Ge I2, Qusongite |
| 6/mmm | 2 | Helium, LiI3H2O |
| 23 | 1 | N2 O4 |
| m-3 | 1 | Cl2 H6 N2 |
| 432 | — | **未収録** |
| -43m | 1 | Co H18 I N6 O4 S |
| m-3m | 2 | F4 Si, Halite |

**カバー 26 / 32 点群**。未収録の 6 点群: `2`, `3`, `-6`, `422`, `432`, `6mm`。

### アニメーション残差チェック

全 32 CIF のすべての操作を `element_index=None`（auto-select）で実行:

```text
Name                     Ops  Bad>1e-6    MaxRes
Adamantane                 8         0  2.85e-15
AgCl                       4         0  2.04e-15
Antimony                  36         0  6.66e-15
Babefphite                 4         0  0.00e+00
Bi I3                      6         0  1.37e-14
Bromine                   16         0  3.64e-15
C12H14N4                  16         0  1.12e-14
Cl H4 N O2                16         0  4.70e-15
Cl2 H6 N2                 24         0  1.24e-14
Co H18 I N6 O4 S          96         0  1.20e-14
Edgarite                  12         0  7.82e-15
F4 Si                     48         0  7.17e-15
Ge Hf O4                  16         0  2.44e-15
Ge I2                     12         0  5.43e-15
H11 I N2 O6               18         0  1.09e-14
Halite                   192         0  9.39e-15
Helium                    24         0  3.27e-15
Ho2Rh12As7                12         0  6.06e-15
Hydrohematite              8         0  3.58e-15
LiI3H2O                   24         0  7.23e-15
N2 O4                     24         0  1.15e-14
NbP                       32         0  3.67e-15
O9 V5                      4         0  1.28e-15
Pb(Al,Si)4O8               8         0  3.32e-15
Qusongite                 12         0  3.88e-15
SiO2                       8         0  3.90e-15
Tellurium                  6         0  2.72e-15
Tellurobismuthite         18         0  7.27e-15
Tenorite                   4         0  1.09e-15
Thaumasite                 6         0  5.69e-15
Tin                       32         0  5.35e-15
Tridymite                  8         0  4.07e-15
```

**全件 residual ≤ 1e-6（すべて機械精度）。バグなし。**

### Codex 検証との比較

Codex は格子系（7 種）の代表 CIF を選び GIF を生成して目視確認した（`exports/checks/lattice_systems/`）。同じ 7 ファイルを数値確認すると一致:

```text
triclinic    (O9 V5)        4 ops  0 bad  1.28e-15
monoclinic   (AgCl)         4 ops  0 bad  2.04e-15
orthorhombic (Bromine)     16 ops  0 bad  3.64e-15
tetragonal   (Cl H4 N O2)  16 ops  0 bad  4.70e-15
trigonal     (Antimony)    36 ops  0 bad  6.66e-15
hexagonal    (LiI3H2O)     24 ops  0 bad  7.23e-15
cubic        (F4 Si)       48 ops  0 bad  7.17e-15
```

Codex の GIF 確認と私の数値確認は矛盾なし。Codex は目視のみ・私は全操作の残差。

### mapping 完全性 + asymmetric_index

全 32 CIF で:
- `atom_mappings.complete = True`（全件）
- `asymmetric_index` 未割り当て原子 = 0（全件）

### 次の対応提案

6 つの未収録点群（`2`, `3`, `-6`, `422`, `432`, `6mm`）は今すぐ追加が必須ではないが、点群コレクションとして完全にしたい場合は CIF を追加するだけで対応できる。残差チェックが通れば自動でカバー扱いにできる。

---

## GUI 化前の設計確認 (2026-05-16)

`PROJECT_SPEC.md`・アーカイブ仕様書・現行コードを照合して、簡単な GUI に移行する前に Codex が決める必要のある点をまとめる。

### データ層・アニメーションに残存バグなし

全 32 CIF・全操作で residual 機械精度であることを確認済み。GUI 移行を妨げる技術的バグはない。

### 必須対応 1: `run_animation()` のブロッキングループ

`tools/view_json_pyvista.py` の `run_animation()`（line ~454）が `time.sleep()` でフレームを刻んでいる:

```python
for frame in range(frames):
    update_animated_atoms(animated_atoms, paths, frame / (frames - 1))
    plotter.update()
    time.sleep(delay)   # Qt イベントループをブロックする
```

Qt GUI に埋め込むと `time.sleep()` がイベントループを止めてウィンドウがフリーズする。

**修正方針**: `BackgroundPlotter.add_callback(func, interval_ms, count)` に置き換える。`pyvistaqt 0.11.4` でこの API は利用可能であることを確認済み。`update_animated_atoms()` 自体は変更不要。

```python
# GUI 用のループドライバー例
frame_state = {"index": 0}
def advance():
    s = frame_state["index"] / (frames - 1)
    update_animated_atoms(animated_atoms, paths, s)
    frame_state["index"] += 1
bp.add_callback(advance, interval=int(1000 / playback_fps), count=frames)
```

### 必須対応 2: 対称要素アクターの追跡

`add_symmetry_elements()` は `plotter.add_mesh()` するがアクターの参照を返さない。操作リストで別の操作に切り替えたとき「前の対称要素だけ消す」ができない。

**修正方針**: `add_symmetry_elements()` が追加したアクターのリストを返すよう変更し、呼び出し側が保持して `plotter.remove_actor()` で差し替える。原子・単位胞は起動時の1回だけで操作切り替えの影響を受けない。

```python
# 変更例
def add_symmetry_elements(plotter, render_data, ...) -> list:
    actors = []
    mesh = plotter.add_mesh(...)
    actors.append(mesh)
    return actors

# 操作切り替え時
for actor in current_element_actors:
    plotter.remove_actor(actor)
current_element_actors = add_symmetry_elements(plotter, render_data, new_op_index)
```

### 設計決定: 解析のトリガー（案 A / B / C）

旧 GUI は CIF 読み込み・解析・描画を一体化して失敗した。現行の JSON 境界設計を GUI でどう扱うかを決める必要がある。

| 案 | GUI の動き | 推奨度 |
|---|---|---|
| A. JSON 先読み | ユーザーが事前 export、GUI は JSON を開くだけ | 最シンプル。初期 GUI に最適 |
| B. auto-export | CIF 開くと裏で `export_analysis_json()` を呼び temp JSON 生成 | UX 自然。既存コード再利用可能 |
| C. インメモリ | `analyze_cif()` → dict → JSON ファイル不要 | 将来的に理想。今はオーバーエンジニアリング |

**初期 GUI には案 A か B を推奨**。案 B は `tools/export_analysis_json.py` の内部関数を直接呼ぶだけで実現できる。

### 流用可能な関数（変更不要）

以下はそのまま GUI から呼べる。PyVistaQt の `BackgroundPlotter` は `pv.Plotter` のサブクラスなので API 互換。

```text
add_atoms(plotter, render_data)          ← 起動時 1 回
add_unit_cell(plotter, render_data)      ← 起動時 1 回
add_symmetry_elements(...)               ← 操作切り替えで差し替え（要 actor 返却追加）
add_animated_atoms(plotter, render_data) ← アニメーション用 atom list 生成
animation_paths(...)                     ← 純粋計算、変更不要
update_animated_atoms(...)               ← 純粋更新、変更不要
```

### 推奨する簡単 GUI の構成

```text
左パネル (QWidget):
  [Open CIF / XYZ]
  ---
  操作リスト (QListWidget)
    → 選択で右の対称要素を差し替え
  ---
  [Play / Stop]
  速度スライダー
  scope: All / Representative ラジオボタン

右パネル:
  BackgroundPlotter (PyVistaQt)
```

### 今は不要（パズル段階に回してよい）

```text
原子クリック選択 (enable_element_picking / enable_point_picking)
パズル正誤判定 (AtomMapping.atom_to_atom との照合)
操作結果を単位胞内に wrap して表示
分子モードの GUI サポート
```

原子クリックは PyVista の `enable_point_picking(callback)` で実装できる準備はあるが、`AtomMapping.atom_to_atom` との連携設計が必要なため GUI 基盤が安定してから追加する。

---

## PyVista 単体 GUI への切り替え評価 (2026-05-16)

### 経緯

`tools/view_json_gui.py` を PyQt6 + pyvistaqt.QtInteractor で実装したところ、WSL/X11 環境で即座にクラッシュした。

```text
X Error of failed request:  BadWindow (invalid Window parameter)
  Major opcode of failed request:  12 (X_ConfigureWindow)
  Serial number of failed request:  7
```

JSON 読み込みの遅延・`BackgroundPlotter` への切り替えを試みたが同様のエラーが継続した。

### 根本原因

Qt ウィンドウ管理と VTK レンダーウィンドウの連携が WSL/X11 上で不安定。アニメーション計算・AtomMapping・JSON スキーマとは無関係の表示バックエンド問題。

### Codex の対策

Qt / PyVistaQt 依存を完全に除去し、`pv.Plotter` 単体の最小 GUI に置き換えた。

```text
操作選択:  add_slider_widget（0 〜 N-1 のスライダー）
速度変更:  add_slider_widget（0.1 〜 4.0）
アニメーション駆動:  add_timer_event(max_steps, duration, callback)
キー操作:  add_key_event（space / n / p / r / 1 / 2 / 3）
ステータス表示:  add_text（操作名・種別・scope をオーバーレイ）
```

### 技術的正当性の確認

| 項目 | 確認結果 |
|---|---|
| `animation_paths()` が `selected_atoms` 引数を受け付けるか | ✓ 実装済み（line 503、scope="selected" で entries をフィルタ） |
| `add_symmetry_elements()` がアクターリストを返すか | ✓ 実装済み（GUI からの remove_actor に対応済み） |
| `pv.Plotter.add_timer_event(max_steps, duration, callback)` の API | ✓ 存在確認済み |
| 構文エラー | なし（`py_compile` 通過） |
| `--help` / `--selected-atoms` の動作 | ✓ 正常 |

### 軽微な問題

`on_timer` のフレーム進行が整数丸めで粗い:

```python
self.frame = (self.frame + max(int(round(self.speed)), 1)) % self.frame_count
```

speed=0.1〜1.4 がすべて「1 フレーム/tick」と同一になり、スライダー下端付近が効かない。現状の「1倍未満は無効」制限として許容できるが、将来的には timer の `duration` 引数で速度を制御する方が正確。ただし `add_timer_event` は実行後に `duration` を変更できないため、改善は別設計が必要。

### 対策の評価

**妥当。** WSL 環境での Qt + VTK 不安定性を避けるために PyVista 単体に戻す判断は合理的。`viewer.animation_paths` / `viewer.add_symmetry_elements` / `viewer.update_animated_atoms` 等の描画・アニメーション関数はすべて正しく流用できている。

### 今後の方針

- `pv.Plotter` 単体で「JSON を開く・操作を選ぶ・アニメーションする」が動く状態を維持する
- Qt GUI への再移行は WSL の OpenGL サポート状況が改善されてから検討する（`LIBGL_ALWAYS_SOFTWARE=1` + PyVistaQt の組み合わせで安定するか要確認）
- CIF から直接読み込む案 B は GUI 基盤が安定してから追加する

---

## Browser Control UI チェックポイント (2026-05-16)

Claude に確認してほしい現状共有。

### 現在の構成

- `tools/view_json_server.py`
  - stdlib `ThreadingHTTPServer` でブラウザ操作パネルを配信
  - PyVista はメインスレッドで `pv.Plotter` を実行
  - ブラウザと PyVista は `shared_state` + `threading.Lock` で同期
  - UI は操作リスト、方向フィルタ、原子チェックリスト、Play/Stop/Reset、View along direction
- `tools/view_json_gui.py`
  - Qt を使わない PyVista native widget 版
  - ブラウザUIが主経路になったため、現在はバックアップ/簡易確認用
- `tools/view_json_pyvista.py`
  - 描画・アニメーション本体
  - GUI/ブラウザはこの関数群を呼ぶだけにしている

### Codex が今回確認したこと

```bash
.venv/bin/python -m py_compile tools/view_json_server.py tools/view_json_gui.py tools/view_json_pyvista.py crystal_viewer/*.py
```

構文エラーなし。

`exports/*.json` に対して `operation_summaries()` を実行し、例外なし。

```text
f2_pd.json      12 ops   36.7 ms
jacobsite.json 192 ops 1014.4 ms
mg2v2o7.json     2 ops    1.9 ms
water.json       4 ops    0.6 ms
```

### 見つけて修正したバグ

操作リストの軸/面/通過座標が、実際に PyVista で表示・アニメーションに使う軸/面とずれるケースがあった。

原因:

- `operation_summaries()` が高速化のため `display_symmetry_elements(render_data, None, ...)` を使っていた
- そのため複数の等価な軸/面がある操作では「先頭候補」の表示になり、`atom_mappings` を使って選ばれる実際の要素と一致しなかった
- Jacobsite では 42 操作で通過座標がずれていた

修正:

- `operation_summaries()` でも `atom_mappings` を渡し、実際のアニメーション文脈で選ばれる軸/面/中心を表示するよう変更
- pure translation だけは、周期境界で実際にアニメーションする代表原子の `start -> target` 方向を表示するため、表示上の translation 方向を上書きしている

修正後:

- 回転/鏡映/回反などのリスト表記は PyVista 表示要素と一致
- translation は JSON 生データの `+1/2` 方向ではなく、実際に見える最短像方向を表示

### 現在の既知トレードオフ

- Jacobsite の起動時 summary 生成は約 1 秒かかる
  - 以前の fast path は約 0.09 秒だったが、リスト表示と実際の表示要素の一致を優先した
  - 体感上まだ許容範囲
  - 将来操作数がさらに増える場合は、初期表示を fast path にして、選択時だけ詳細ラベルを更新する lazy 方式を検討
- `tools/view_json_server.py` と `tools/view_json_gui.py` はまだ未追跡ファイル
  - push 前に `git add` が必要
- docs の一部に古い UI 説明が残っている
  - 例: operation filter / atom filter と書いているが、現在のUIでは検索入力欄を削除済み

### Claude に特に確認してほしい点

1. `operation_summaries()` が `atom_mappings` を使うようになった判断は妥当か
2. translation の表記を「JSON 生データ」ではなく「実際に見える最短像方向」に合わせる方針でよいか
3. summary 生成 1 秒程度を今の段階で許容してよいか、lazy 化すべきか
4. ブラウザUIの `shared_state` 同期に競合・上書きバグが残っていないか
5. 次の段階で、CIF直接読み込みより先に行うべき設計整理があるか

---

## Browser UI コードレビュー (2026-05-16)

Codex の 5 問への回答と、実際にコードを読んで見つけたバグ・最適化案。

### Q1 ～ Q5 への回答

**Q1: `operation_summaries` が `atom_mappings` を使うようになった判断は妥当か**

妥当。Jacobsite で 42 操作のラベルが 3D 表示と食い違っていたのは実際の問題。ブラウザのリスト表記と PyVista 表示が一致していないと、「どの操作を選んでいるか」がユーザーに伝わらない。現行の slow path（atom_mappings あり）を維持する判断は正しい。

**Q2: translation の表記を「実際に見える最短像方向」に合わせる方針でよいか**

よい。`translation_cart` の生の値（例: `[4.26, 4.26, 0]` Å）より、代表原子の `animation_paths` から導いた実際の表示方向の方が直感的で、3D での動きと一致する。`_display_translation_cart` を `summary_operation` に持たせて `translation_direction_cart` で参照する設計も正しい。

**Q3: summary 生成 700ms を今の段階で許容してよいか**

許容できるが、**無料で 23× 高速化できる方法がある**（後述）。

**Q4: `shared_state` の競合・上書きバグは残っているか**

前回指摘した 2 件は修正済み:
- write-back を `playing` のみに限定 ✓
- `scope=shared_state["scope"]` をコンストラクタに明示渡し ✓

現在のコードに競合バグはない。`view_request_id` のトランジェント処理も `last_view_request_id` で正しく重複実行を防いでいる。

**Q5: CIF 直接読み込みより先に行うべき設計整理はあるか**

今の段階で行うべき整理が 1 点ある（後述の最適化と同時に）。

---

### 現行コードの確認: バグなし

前回レビューのバグは全件修正済みを確認:

| 項目 | 前回 | 今回 |
|---|---|---|
| write-back 競合 | ❌ `operation_index/scope/selected_atoms` も書き戻し | ✓ `playing` のみ |
| 初期 scope 不整合 | ❌ `scope="all"` vs `shared_state="representative"` | ✓ 明示渡しで一致 |

`element_actor_cache` + `SetVisibility` による操作切り替えは良い設計。`remove_actor/add_mesh` より大幅に速い。

`camera_up_vector` の実装も正しい（方向が [1,1,1] 等の場合でも垂直な up ベクトルが得られる）。

---

### 最適化: `display_symmetry_elements` の重複呼び出し

#### 現状（コスト内訳）

```text
operation_summaries() 起動時:
  display_symmetry_elements × 192 (slow path) = 658 ms  ← ボトルネック
  visual_translation_direction × 192           =   3 ms
  ラベル計算                                   =  40 ms
  合計                                         = 700 ms

ユーザーが操作を初めて選ぶとき:
  show_element_actors() で display_symmetry_elements を再度呼ぶ = 3.7 ms/click

view_along_current_operation():
  display_symmetry_elements を再度呼ぶ = 3.7 ms/click
```

`display_symmetry_elements(rd, atom_mappings, ...)` は、起動時（summaries 生成）と操作初回選択（`show_element_actors`）の 2 回呼ばれている。axes/planes/centers の dict を起動時に返して `BrowserControlledViewer` に渡せば、2 回目は不要になる。

#### 最適化案（コスト: 起動は変わらず、操作切り替えと view_along は 0ms に）

`operation_summaries` が `axes/planes/centers` のキャッシュも一緒に返すよう変更:

```python
def operation_summaries(
    render_data: dict, atom_mappings: dict | None
) -> tuple[list[dict], dict[int, tuple]]:
    summaries = []
    element_cache: dict[int, tuple[list, list, list]] = {}
    for operation in render_data["operations"]:
        ...
        axes, planes, centers = viewer.display_symmetry_elements(
            render_data, atom_mappings, operation["index"], None
        )
        element_cache[operation["index"]] = (axes, planes, centers)
        summaries.append({...})
    return summaries, element_cache
```

`BrowserControlledViewer` にこのキャッシュを渡し、`show_element_actors` で使う:

```python
class BrowserControlledViewer(NativePyVistaViewer):
    def __init__(self, *args, element_context_cache: dict | None = None, **kwargs):
        super().__init__(...)
        self.element_context_cache = element_context_cache or {}

    def show_element_actors(self, operation_index: int) -> None:
        if operation_index not in self.element_actor_cache:
            precomputed = self.element_context_cache.get(operation_index)
            if precomputed:
                axes, planes, centers = precomputed
                actors = _add_elements_from(self.plotter, axes, planes, centers, span)
            else:
                actors = viewer.add_symmetry_elements(...)
            self.element_actor_cache[operation_index] = actors
        ...
```

`view_along_current_operation` も `element_context_cache` から取得すれば再計算不要。

#### 別案: 起動 700ms を 30ms にする fast-path 方式

REVIEW_NOTES 前回記載の `None` 渡し案（fast path, 3ms）と slow path の組み合わせ:

```python
# 起動: fast path でラベル生成（30ms）
summaries, _ = operation_summaries(render_data, None)

# 操作初回選択時: show_element_actors が slow path を呼ぶ (3.7ms/click)
```

**トレードオフ**: ブラウザのリスト表記が PyVista 表示と一致しない ops が最大 42 件残る（Codex が解決済みの問題が再発）。起動速度を優先するなら採用してよいが、教育ツールとして「リスト→3D 一致」の方が重要なら今のままでよい。

---

### 推奨: 最適化案 A（element_context_cache 共有）

- 起動時間: 現状と同じ（700ms）
- 操作切り替え初回: 3.7ms → 0ms
- `view_along` click: 3.7ms → 0ms
- ラベルと 3D の一致: 維持
- 変更量: `operation_summaries` の戻り値変更 + `BrowserControlledViewer` への cache 渡し + `show_element_actors` での参照追加

ただし `viewer.add_symmetry_elements` の中で `display_symmetry_elements` を再度呼ぶ問題も残るため、`add_symmetry_elements` に `axes/planes/centers` を直接受け取るオーバーロードを追加すると完結する。

**今すぐ直すかどうか**: 700ms は体感で許容範囲なら後回しでよい。CIF 直接読み込み実装前（analysis 呼び出しが追加されるとさらに遅くなる可能性）に対処しておくことを推奨。

### Codex 対応 (2026-05-16)

Claude 推奨の最適化案 A を実装。

- `tools/view_json_pyvista.py`
  - `add_symmetry_element_actors(plotter, render_data, axes, planes, centers)` を追加
  - 既存の `add_symmetry_elements()` は `display_symmetry_elements()` 後にこの関数へ委譲
- `tools/view_json_server.py`
  - `operation_summaries()` が `(summaries, element_context_cache)` を返すよう変更
  - `BrowserControlledViewer` が `element_context_cache` を受け取り、操作初回選択時の対称要素描画に再利用
  - `view_along_current_operation()` も同じ cache を参照

確認:

```bash
.venv/bin/python -m py_compile tools/view_json_server.py tools/view_json_gui.py tools/view_json_pyvista.py crystal_viewer/*.py
.venv/bin/python tools/view_json_server.py --help
```

`exports/*.json` の summary/cache 生成も例外なし。

```text
f2_pd.json      ops= 12  cache= 12
jacobsite.json  ops=192  cache=192
mg2v2o7.json    ops=  2  cache=  2
water.json      ops=  4  cache=  4
```

---

## Camera Rotation UI 追加 (2026-05-16)

ブラウザ操作パネルに、現在の視点を任意角度で上下左右に回転する機能を追加。

目的:

- `View along direction` で (001) 面などを正面から見た後、90° 右回転して「その面を右側から見る」ような確認をしたい
- VESTA 的に、現在の視点を基準に少しずつ回して構造を確認できるようにする

実装:

- `tools/view_json_server.py`
  - UI に `Camera` セクションを追加
  - `camera-angle` 入力欄と `Up / Left / Right / Down` ボタンを追加
  - ブラウザから `camera_request_id`, `camera_direction`, `camera_angle` を POST
  - PyVista 側で現在の camera position / focal point / view up を取得し、focal point を中心に回転
  - 左右: 現在の view-up 軸まわり
  - 上下: 現在の screen-right 軸まわり
  - カメラ位置だけでなく view-up も同時に回して、画面の上下が不自然にねじれないようにした

確認:

```bash
.venv/bin/python -m py_compile tools/view_json_server.py tools/view_json_gui.py tools/view_json_pyvista.py
.venv/bin/python tools/view_json_server.py --help
```

数値確認:

```text
view radius [0,0,1], up [0,1,0]
right 90 -> [1,0,0]
left  90 -> [-1,0,0]
```

---

## Browser UI 機能追加コードレビュー (2026-05-16)

前回レビューからの追加機能（カメラ回転、GIF保存、速度ボタン、表示範囲切り替え、元素フィルター、element_context_cache）を確認した。

### バグなし — 全件確認

| 確認項目 | 結果 |
|---|---|
| 構文エラー | なし（py_compile 通過） |
| `element_context_cache` が 192 op 全件をカバー | ✓ |
| `rotate_vector` の数値正確性（right 90° → [1,0,0]、left 90° → [-1,0,0]）| ✓ |
| `imageio.v2.mimsave(..., fps=fps)` GIF 書き出し | ✓ API 正常 |
| `scope="selected"` 全原子 vs `scope="all"` の同一性 | ✓ 残差一致・角度一致 |

### 新機能の設計確認

**カメラ回転 (`rotate_current_camera`):**
Rodrigues 回転公式を正しく使用。Left/Right は `up` 軸周り、Up/Down は `screen_right` 軸周り。camera_request_id による重複実行防止も正しく機能。

**GIF 保存 (`save_current_gif`):**
`on_timer` からブロッキング呼び出しだが、VTK はスレッドセーフでないため正当な設計。s=0→1 の全サイクルを 48 フレームに等間隔サンプリング。`imageio.mimsave` の `fps` 引数は正常動作確認済み。`finally` で `frame_position` を元に戻す処理も正しい。

**速度ボタン (`operation_speed_multiplier`):**
mirror/inversion/glide/translation を 2×、rotation/screw を 1× にするのは妥当な設計。`rotoinversion` は 1× のまま（回転+反転の複合操作なので速くしない）。

**`scope="selected"` 全原子デフォルト:**
`animation_paths(scope="selected", representative_atom=0, selected_atoms=all)` は `scope="all"` と同じ残差・角度になることを数値確認済み（Jacobsite rotation_2 で一致）。唯一の差異は代表原子が auto-select か atom[0] かという点のみで、全操作 residual < 1e-6 を維持している。

**表示範囲切り替え (`rebuild_display_atoms`):**
元の atom actor（`item["actor"]`）を正しく除去してから再構築する設計。element_actor_cache は影響を受けない（表示範囲は atom 球の数と位置のみを変える）。

### 起動時間の詳細プロファイル

```text
operation_summaries (192 ops, Jacobsite): 1214 ms

ボトルネック: display_symmetry_elements × 192 = ~660 ms
  ├ select_animation_context (avg 2.9 候補 × 56 atoms × build_operation_path):
  │   effective_rotation_axis 呼び出し合計: 17,725 回
  │   このうちラベル関数からの冗長呼び出し: 最小限
  │   （axes が既に populated なら label 関数は effective_axis_from_operation を呼ばない）
  └ 大半は animation_context_score → build_operation_path 内の呼び出し
```

element_context_cache 実装後:
- 初回操作選択: display_symmetry_elements を再呼び出ししない → 0ms
- 2 回目以降: element_actor_cache から visibility toggle → 0ms
- view_along_current_operation: element_context_cache からの fallback なし（全 op がキャッシュ済み）

### 残存する最適化余地

現在の 1.2 秒起動の根本原因は `animation_context_score` が全 ops × 全候補 × 全原子で `build_operation_path` を呼んでいること（前回 REVIEW_NOTES の最適化案 A,B が未対応のままの部分）。追加機能の実装でこのボトルネックは変わっていない。

今後 CIF 直接読み込みを実装する際には、この起動コストが analysis 時間に加算される。現段階では許容範囲（1 秒強）だが、その時点で lazy 化を検討するタイミングになる。

---

## Claude 実装: カスタム操作チェック機能 (2026-05-16)

### 概要

`tools/view_json_server.py` のみを変更。既存コードには触れていない。

### 追加内容

**ブラウザ UI (HTML/JS):**
- 「Custom Operation Check」セクションをページ下部に追加
- 操作タイプ選択: 回転 / 鏡映 / 反転 / らせん軸 / 映進反射 / 回反 / 並進 / 恒等 / 行列直接入力
- タイプ別の入力フォーム（全て分率座標）
- 許容距離 (Å) 入力
- Check ボタン → 即時結果表示（ブラウザ）
- Clear ボタン → PyVista のハイライト消去

**新 API エンドポイント `/api/check_operation` (POST):**
- リクエスト: `{type, params, tolerance, request_id}`
- レスポンス: `{is_symmetry, total, mapped_count, unmapped_count, unmapped: [...]}`
- 計算は HTTP ハンドラーで同期的に実行（純粋な数学計算のため）
- 結果を `shared_state["custom_op_result"]` に保存 → PyVista が次の timer tick でハイライト

**`/api/state` POST に追加したキー:**
- `custom_op_check_id` — ブラウザから PyVista にハイライト要求を伝えるトリガー
- `clear_custom_check` — ハイライト消去

**Python 新関数:**
- `rotation_matrix_from_axis_angle(axis, angle)` — Rodrigues 回転公式
- `build_custom_operation_frac(op_type, params, lattice)` → `(W_frac, t_frac)` または エラー文字列
  - 入力: ユーザーフレンドリーなパラメータ（軸方向、角度、通過点、法線など）
  - 出力: spglib 規約の分率座標行列 `x'_frac = W_frac @ x_frac + t_frac`
  - 座標変換: `W_frac = inv(L.T) @ W_cart @ L.T`、法線変換: `n_cart = inv(L) @ hkl`
- `check_custom_operation(render_data, W_frac, t_frac, tolerance_cart)` → 結果 dict
  - 全原子に操作を適用し、同元素の原子に重なるか判定
  - 周期境界条件を考慮（`delta -= round(delta)` で最短像を使用）

**BrowserControlledViewer に追加:**
- `custom_check_actors: list` — 赤いハイライト球のアクターリスト
- `last_custom_op_check_id` — 重複実行防止
- `apply_custom_check(result)` — 未対応原子に赤い半透明球を追加
- `clear_custom_check_actors()` — ハイライト消去
- `on_timer` でハイライト更新処理を追加
- `make_handler` に `render_data` を追加渡し（チェック計算のため）

**動作検証（自動テスト）:**
```text
NaCl (Fm-3m) inversion through (1/2,1/2,1/2): is_symmetry=True ✓
NaCl inversion through (0,0,0):                is_symmetry=True ✓
NaCl face-centering translation (1/2,1/2,0):   is_symmetry=True ✓
NaCl random translation (0.3,0,0):             is_symmetry=False unmapped=8/8 ✓
Jacobsite known screw_4 matrix:                is_symmetry=True ✓
Jacobsite rotation_2 built from axis data:     is_symmetry=True ✓
Jacobsite pure 90° rotation (no pure 4-fold in Fd-3m): is_symmetry=False ✓
Jacobsite mirror (110) through origin:         is_symmetry=True ✓
```

### 設計判断

- チェックは HTTP ハンドラー内で同期実行（数学計算のみ、~数ms）→ ブラウザに即心応答
- PyVista ハイライトは shared_state 経由で非同期（次の timer tick = ~33ms 後）
- 分子モード (unit_cell なし) はエラーメッセージを返す
- Codex が変更した既存関数は一切変更していない

---

## Claude 実装 (2026-05-17): デバッグセッションで発見した問題と修正

### 修正済みバグ

#### 1. JS構文エラー (`lines.join("\n")`)
**場所:** `view_json_server.py` の `renderOperationDetails` 関数内（HTML テンプレート）

**原因:** Python の `"""..."""` 文字列内で `"\n"` を書くと Python が改行文字に変換し、ブラウザに届く JS に改行を含むダブルクォート文字列リテラルが生成される（JS では構文エラー）。

**修正:** `"\n"` → `"\\n"` でバックスラッシュ+n として渡す。

---

#### 2. `NameError: name 'pv' is not defined` の無限ループ
**場所:** `view_json_server.py` の `apply_custom_check()` / `_on_timer_inner()`

**原因:** `apply_custom_check` が `pv.Sphere()` を呼ぶが `view_json_server.py` に `import pyvista as pv` がなかった。NameError が発生すると `last_custom_op_check_id` が更新されず、次の timer tick でも同じ例外を繰り返す（33ms 毎）→ CPU スパイク。

**修正:**
- `import pyvista as pv` を追加
- `last_custom_op_check_id = custom_op_check_id` を `apply_custom_check()` 呼び出しの**前**に移動（例外が起きても ID が更新され、ループしない）

---

#### 3. VTK warning 再帰ループ
**場所:** `view_json_server.py` 起動時 / PyVista レンダリング

**原因:** `opacity < 1` のアクターが VTK の depth peeling (透明順ソート) 警告を発生させる→ PyVista がそれを Python logging 経由でログ→ そのログ出力が何らかの VTK イベントを再トリガー→ 指数的に増殖するメッセージが端末を占拠し、他の出力が一切見えなくなる。WSL/Mesa 環境で顕著。

**修正:** `BrowserControlledViewer.__init__` で全レンダラーの depth peeling を無効化：
```python
for renderer in self.plotter.renderers:
    renderer.UseDepthPeelingOff()
```

---

### 現在残っている問題（Codex に引き渡す）

#### Bug (中): カスタムアニメ後に同じ操作でPlayしても通常アニメが動かない

**場所:** `view_json_gui.py:114` の `set_operation_position` 早期リターン / `view_json_server.py` `_on_timer_inner`

**再現手順:**
1. Custom Operation Check でアンマップ原子を確認 → Animate all unmapped で再生
2. ブラウザの operation list で**同じ操作**を選択
3. Play → **カスタムアニメが再生され、通常操作アニメが動かない**

**根本原因:** `_on_timer_inner` は `operation_index` の変化で `using_custom_paths = False` を設定するが、同じ操作を再クリックしても `operation_index != self.last_operation_index` が偽になるためこのブロックに入らない。`using_custom_paths` は True のまま残り、`self.paths` はカスタムパスを保持し続ける。`set_operation_position` の早期リターン条件 `self.paths` (非空) も Build paths を呼ばない。

**回避策:** "Clear highlight" ボタンを押すと `build_paths()` が強制呼び出され解消。

**提案修正:** 以下のいずれか：
- `_on_timer_inner` の `active_mode` が "standard" に変わったときに `using_custom_paths = False` + `build_paths()` を呼ぶ
- `set_operation_position` の早期リターン条件に `not self.using_custom_paths` を加える（base クラスは `using_custom_paths` を持たないので server.py でオーバーライドするのが安全）

---

#### Bug (低): `apply_custom_check` 失敗時にハイライトが無音で消える

**場所:** `view_json_server.py:1424`

**状況:** `last_custom_op_check_id` を呼び出し前に更新する修正で例外ループは防げたが、`apply_custom_check` 内で例外が発生した場合、赤ハイライトが表示されない上にユーザーへのフィードバックもない。

**提案修正:** `apply_custom_check` を `try/except` で囲み、失敗時はブラウザのステータスに "check highlight failed" を出す（`shared_state["status_message"]` 等）。

---

#### Latent (低): `sphere_mesh_cache` で同じ PolyData を共有

**場所:** `view_json_gui.py:261` `sphere_mesh()` / `ensure_display_atom()`

**状況:** 同じ原子番号・半径のアクター全員が同一 `pv.PolyData` オブジェクトを `item["mesh"]` として参照する。現在は `actor.SetPosition()` のみ使用するため問題ない。しかし `update_animated_atoms` の `else` ブランチ (`item["mesh"].points = item["base_points"] + center`) はまだコード上に残っており、将来的に actor が None になる経路ができると全同元素アクターの形状が破壊される。

**提案:** `else` ブランチを削除するか、コメントで「このブランチは actor がある限り到達しない」と明記。

---

### コードの良い点（変更不要）

- `atom_actor_cache` + `sphere_mesh_cache` の設計：表示モード切替時にアクターを再生成せず hide/show するため、高頻度な display_mode 変更でも VTK オブジェクトを使い回せる。
- `custom_op_check_id` / `custom_op_animate` / `reset` 等の shared_state 読み取りがすべてロック内に統一された（race condition なし）。
- `active_mode` フィールドで standard/custom の状態管理が明確化された。
- `custom_speed_multiplier` で操作種別ごとの速度調整ができるようになった。

---

## Claude 実装 (2026-05-17): view_json_server.py 分割リファクタリングのレビュー

Codex が `view_json_server.py` の大部分を `crystal_viewer/viewer/` パッケージに分割した。
以下は新モジュール (`pyvista_controller.py`, `custom_operation.py`, `operation_labels.py`, `browser_ui.py`) のレビュー結果。

### リグレッションなし（正常に移植された部分）

- `shared_state` の全読み取りが `state_lock` 内に統一されたまま維持されている ✓
- `last_custom_op_check_id` を `apply_custom_check()` 呼び出し前に更新するパターンが維持されている ✓
- `active_mode` が standard に戻る際に `using_custom_paths = False` + `build_paths()` が呼ばれる ✓
- `build_custom_animation_paths` の拡張表示モードにおける `start_override` の数学的扱いが正しい ✓
- `operation_summaries` が起動時に（バックグラウンドスレッドなしで）呼ばれるようになった（速度改善） ✓
- `apply_custom_check` の例外が `gif_status` 経由でユーザーに通知されるようになった ✓

### 新機能（正常に実装）

- `apply_custom_check` が赤い球に加え、カスタム操作の対称要素（軸・面・点）も PyVista 上に表示するようになった。
- `custom_matrix_validity_error()` が W の直交性（det = ±1、W^T W = I）を事前検証するようになった。
- `save_three_view_gifs()` で front/right/top の3方向 GIF を一括保存できるようになった。
- `operation_camera_basis()` が分離され、"View along direction" と 3-view GIF 両方で再利用される。
- `export_gif_dir()` でエクスポート先ディレクトリの決定ロジックが統一された。

### 発見したバグ

#### Bug (中): 拡張表示モードでアンマップ原子ハイライトの位置がずれる

**場所:** `pyvista_controller.py:609-622` `apply_custom_check()`

**問題:**
```python
for atom in self.render_data.get("atoms", []):
    center = np.asarray(atom["cart"], dtype=float)  # ← 常にソース位置
```
`render_data["atoms"]` の `atom["cart"]` はユニットセル内の原点基準座標。拡張表示モード（±1/4 など）では、同じ原子が `display_shift_cart` だけずれた位置に表示される。ハイライト球はソース位置に置かれ、実際の表示位置からズレる。

**以前の実装:** `self.animated_atoms` をループして `item["display_shift_cart"]` を加算していた（"source" モードでは問題なく、拡張モードでも正しく機能していた）。

**提案修正:**
```python
for item in self.animated_atoms:
    atom = item["atom"]
    if atom["index"] not in unmapped_set:
        continue
    center = np.asarray(atom["cart"], dtype=float) + item["display_shift_cart"]
    # ... 以下変更なし
```

---

#### Bug (低): 対称要素アクターキャッシュが表示モード変更のたびに肥大化

**場所:** `pyvista_controller.py:260` `show_element_actors()`

**問題:**
```python
cache_key = (operation_index, self.display_mode)
```
キャッシュに `display_mode` を含めたことで、操作と表示モードの組み合わせごとに新しいアクターセットが生成される。古い表示モードのアクターは `hide_element_actors()` で非表示にされるだけで、プロッタから削除されない（`remove_actor` なし）。

192 操作 × 5 表示モードを全て選択すると 960 セットのアクターが GPU メモリに蓄積する可能性がある。

**提案修正案:**
1. 表示モード変更時に `element_actor_cache` の全エントリを `remove_actor` してからクリアする
2. または表示モードが変わったら前の `display_mode` のキャッシュエントリのみ削除する

---

#### Potential Bug (低): `infer_screw_symbol` が純粋 2 回軸を "2_1" と誤判定する可能性

**場所:** `operation_labels.py:88-91`

```python
if screw == 0:
    if int(order) == 2:
        return "2_1"
    return None
```

`screw = int(round(fraction * order)) % order` が 0 になるのは、軸方向への投影が 0 または 1 周期分（丸め誤差を含む）の場合。2 回軸で `screw == 0` は「軸方向変位なし」を意味し、純粋な 2 回回転である可能性が高い。これを "2_1" と返すのは誤判定になりうる。

ただし、この関数はシンボルに "?" が含まれる場合のみ呼ばれる（つまり spglib がすでに判定に失敗した場合）ので、実害は限定的。

---

## Claude レビュー (2026-05-17) — browser-ui 分割後リファクタ

対象ファイル: `crystal_viewer/viewer/browser_ui.py`, `operation_labels.py`, `pyvista_controller.py`, `tools/view_json_server.py`

---

### Bug (中): `renderDirectionFilter` でフィルタリセット後に `renderOperations` が呼ばれない

**場所:** `crystal_viewer/viewer/browser_ui.py:775-778`

```js
if (directionFilterValue && !directions.some(([value]) => value === directionFilterValue)) {
  directionFilterValue = "";
  renderDirectionFilter();   // renderOperations() は呼ばれない
}
```

**状況:** `refreshState()` が `summaries_ready` を検知して `operations` を更新したとき、
`renderDirectionFilter()` が呼ばれる。このとき選択中の方向が新 operations に存在しない場合、
上記ブランチに入り `directionFilterValue = ""` にして再帰呼び出しするが、
`renderOperations()` が呼ばれないため操作リストが旧フィルタのまま（空）になる。

**修正案:**
```js
if (directionFilterValue && !directions.some(([value]) => value === directionFilterValue)) {
  directionFilterValue = "";
  renderDirectionFilter();
  renderOperations();   // 追加
}
```

---

### Bug (小): `formatSymbol` が `_0` を変換しない

**場所:** `crystal_viewer/viewer/browser_ui.py:689-696`

`_1`〜`_6` は下付き文字に変換されるが `_0` の変換がない。
`6_0` のような notation があった場合に `6_0` のまま表示される。

**修正案:** `replaceAll("_0", "₀")` を先頭に追加するか、まとめて正規表現に置き換える:
```js
return String(symbol).replace(/_([0-6])/g, (_, d) => "₀₁₂₃₄₅₆"[Number(d)]);
```

---

### Potential Bug (中): `build_custom_animation_paths` が `matrix_cart: None` の fake_op を渡す

**場所:** `crystal_viewer/viewer/pyvista_controller.py:717`

```python
fake_op = {"kind": kind, "angle_deg": angle_deg, "order": None, "matrix_cart": None}
```

`viewer.build_operation_path` がアーク/反射パスを構築するとき `matrix_cart` を使う可能性がある。
`None` を渡した場合に直線補間にフォールバックするかどうかは `view_json_pyvista.py` の実装次第。
カスタム操作（rotation/screw/mirror/glide）のアニメーションが正しくアーク・反射パスを描くか
実機で確認すること。

---

### Bug (小): `fmtFrac` が `r ≈ 1.0` を正しく処理しない

**場所:** `crystal_viewer/viewer/browser_ui.py:831-839`

Python側 `format_fraction` は `abs(value - 1.0) < 1e-8` のとき "0" を返すが、
JS側 `fmtFrac` には `r ≈ 1.0` のガードがない。
`point_label` 経由では事前ラップされるので通常発生しないが、
将来の呼び出し元が未ラップの `1.0` を渡すと `"2/2"` などが表示される。

**修正案:** 既存の `r < 1e-8` チェックの隣に追加:
```js
if (Math.abs(r) < 1e-8 || Math.abs(r - 1.0) < 1e-8) return "0";
```

---

### 効率: `boot()` の API 呼び出しが直列

**場所:** `crystal_viewer/viewer/browser_ui.py:1483-1490`

```js
const info = await api("/api/operations");
const atomInfo = await api("/api/atoms");
state = await api("/api/state");
```

3 呼び出しが直列のため、サーバー起動時に往復時間 × 3 がかかる。
`Promise.all` で並列化すれば起動時間を短縮できる:

```js
const [info, atomInfo, st] = await Promise.all([
  api("/api/operations"),
  api("/api/atoms"),
  api("/api/state"),
]);
operations = info.operations;
summariesReady = Boolean(info.summaries_ready);
atoms = atomInfo.atoms;
state = st;
```

---

### 効率: `refreshState` が多重実行される可能性

**場所:** `crystal_viewer/viewer/browser_ui.py:1504`

```js
setInterval(refreshState, 500);
```

`refreshState` は `async` だが `setInterval` は Promise を待たない。
GIF 保存中などサーバー応答が遅い場合、複数の `refreshState` が同時実行され
状態の上書き競合が起きうる。

**修正案:**
```js
let _refreshing = false;
setInterval(async () => {
  if (_refreshing) return;
  _refreshing = true;
  try { await refreshState(); } finally { _refreshing = false; }
}, 500);
```

---

### 効率: `element_colors_key` がフレームごとに生成される

**場所:** `crystal_viewer/viewer/pyvista_controller.py:132-133`

```python
element_colors_key = tuple(sorted((str(key), str(value)) for key, value in element_colors.items()))
atom_colors_key    = tuple(sorted((str(key), str(value)) for key, value in atom_colors.items()))
```

タイマーは 33ms 毎に発火し、変化がなくてもこのソート＋タプル生成が毎回実行される。
色数が多い構造では無視できないコスト。
元データを dict として保持し `tuple(sorted(d.items()))` を直接比較するか、
変更フラグを `shared_state` に持たせて差分があるときだけ更新する設計が望ましい。

**確認事項:** `screw == 0, order == 2` が正当な 2_1 ケース（例: 投影が 1.0 周期にほぼ一致して mod 演算で 0 になった場合）を意図しているなら、コメントで明記すること。そうでなければ `return None` に修正。

---

## Claude レビュー (2026-05-21) — 分子ビューア追加後

対象ファイル: `crystal_viewer/molecule_analysis.py`, `atom_mapping.py`, `render_data.py`, `viewer/browser_ui.py`, `viewer/pyvista_controller.py`, `tools/view_json_server.py`

---

### Bug (中): `operation_symbol` が "CNone" / "SNone" を返す（線形分子で発生の可能性）

**場所:** `crystal_viewer/molecule_analysis.py:256-267`, `L244-252`

`matrix_order` は order > 24 で `None` を返す。線形分子 (C∞v, D∞h) を pymatgen が高次回転で近似した場合に発生しうる。

```python
def classify_molecular_operation(...):
    if det == 1:
        return f"rotation_{order}"   # order=None → "rotation_None"
    if det == -1:
        return f"improper_{order}"   # order=None → "improper_None"

def operation_symbol(kind, order):
    if kind.startswith("rotation_"):
        return f"C{order}"           # → "CNone"
    if kind.startswith("improper_"):
        return f"S{order}"           # → "SNone"
```

ミラー操作だけは `convert_operation` で `order is None` のガードあり (L145-146) だが、回転・不正回転には対応していない。

**修正案:**
```python
def operation_symbol(kind: str, order: int | None) -> str:
    ...
    if kind.startswith("rotation_"):
        return f"C{order}" if order is not None else "C∞"
    if kind.startswith("improper_"):
        return f"S{order}" if order is not None else "S∞"
```

---

### Bug (小): `set_manual_view_center` のエラーメッセージが分子モードで誤り

**場所:** `crystal_viewer/viewer/pyvista_controller.py:650-651`

```python
raise ValueError("enter three fractional coordinates")
```

分子モードでは `unit_cell is None` のとき入力値をデカルト Å として扱う (L656-657)。エラーメッセージが "fractional" と表示されるのは誤解を招く。

**修正案:**
```python
label = "fractional" if self.render_data.get("unit_cell") else "Cartesian Å"
raise ValueError(f"enter three {label} coordinates")
```

---

### Bug (小): `renderOperationDetails` が分子モードで `Wc=null` のとき空ヘッダーを表示

**場所:** `crystal_viewer/viewer/browser_ui.py:1077-1080`

```js
lines.push("W (cart):");
if (Wc) {
  for (const row of Wc) lines.push(...)   // Wc null のとき行列行が出ない
}
```

通常 `render_data_from_molecule` は常に `matrix_cart` を設定するので発生しないが、防御的に：

```js
if (Wc) {
  lines.push("W (cart):");
  for (const row of Wc) lines.push(...)
}
```

---

### 効率・設計: `warm_molecule_analysis()` がブラウザ XYZ インポートに効かない

**場所:** `tools/view_json_server.py:530-534`, `L537-562`

ブラウザからの XYZ インポートは `export_analysis_to_json_worker` が **別プロセス** (`subprocess.run`) で実行する。
`warm_molecule_analysis()` はサーバープロセスのメモリ内にだけキャッシュを温めるため、サブプロセスには恩恵がない。
初回分子インポートは常にサブプロセス起動コスト（Python インタプリタ + pymatgen インポート）が上乗せされる。

**改善案 (2択):**
- 案A: サーバー内で直接 `export_analysis_to_json` を呼ぶ（エラー分離が失われる）
- 案B: 起動時にバックグラウンドで `export_analysis_json.py --mode molecule /dev/null` 相当を1回走らせ `.pyc` キャッシュを生成（OS の disk cache 経由で次回起動が速くなる）

---

### 効率: `find_matching_molecule_atom` が O(N²M)

**場所:** `crystal_viewer/atom_mapping.py:222-236`

```python
for candidate in atoms:
    if candidate.atomic_number != atomic_number:
        continue
    distance = np.linalg.norm(...)
```

水・メタンでは問題ないが C60 (60原子, 120操作) では 7200 回のノルム計算が走る。
要素別辞書で O(NM) に改善可能：

```python
# 事前に atoms_by_element: dict[int, list[AtomSite]] を構築してから渡す
```

---

### 備考: CSS クラス `.overbar` と `.overline` の重複

**場所:** `crystal_viewer/viewer/browser_ui.py:103`, `L350`

どちらも `text-decoration: overline` で機能は同一。JS が `.overbar`、Python 生成 HTML が `.overline` を使う。バグではないが将来統一推奨。

### Codex 対応 (2026-05-21)

- `CNone` / `SNone` は妥当な指摘。`operation_symbol()` は order 不明時に `C∞` / `S∞` を返し、kind は `rotation_unknown` / `improper_unknown` として保持するよう修正。
- 分子モードの手入力中心はデカルト Å として扱うため、エラーメッセージを `Cartesian Å` に変更。
- `Wc=null` の防御として、分子詳細の `W (cart):` ヘッダーは行列がある場合だけ表示。
- `warm_molecule_analysis()` はブラウザインポートのサブプロセスに効かないため削除。起動時の余計な事前処理も削除。
- `find_matching_molecule_atom()` は操作ごとに元素別候補を事前構築し、対象元素だけを走査するよう変更。
- `.overbar` / `.overline` は `.overline` に統一。

---

## Claude レビュー (2026-05-22) — 全体構造・2モード共通化・コア集中度

対象: `tools/view_json_pyvista.py`, `crystal_viewer/viewer/pyvista_controller.py`, `crystal_viewer/molecule_analysis.py`, `crystal_viewer/viewer/operation_lookup.py`, `crystal_viewer/viewer/custom_operation.py`, `crystal_viewer/render_data.py`

---

### 構造: `view_json_pyvista.py` に責務が集中しすぎている（1710行）

**場所:** `tools/view_json_pyvista.py` 全体

このファイルには以下がすべて混在している:
- CLI エントリポイント (L1–184)
- PyVista 描画ラッパー (L187–540)
- アニメーションコンテキスト選択アルゴリズム (L550–1210) ← PyVista 非依存
- パス構築（rotation/screw/mirror/glide/inversion/improper）(L1215–1500) ← PyVista 非依存
- `evaluate_path` とすべての幾何プリミティブ (L1498–1706) ← PyVista 非依存

**提案する分割（変更量が少なく安全）:**
```
crystal_viewer/viewer/animation_path.py
  ← build_operation_path, evaluate_path, rotation_path, screw_path,
     mirror_path, glide_path, inversion_path, improper_path,
     rotate_about_axis, reflect_point, signed_rotation_angle_from_matrix,
     rotation_angle_deg, interpolate, normalize (~350行)

crystal_viewer/viewer/animation_context.py
  ← animation_paths, select_animation_context, build_animation_context,
     animation_context_score, representative_mapping_entry,
     animation_target, shared_periodic_shift, shared_rotation_angle,
     shared_step_translation, effective_operation_center, effective_rotation_axis,
     symmetry_element_shared_shift, periodic_target_candidates (~330行)

tools/view_json_pyvista.py ← CLI + PyVista描画のみ (~400行)
```

---

### Bug (中): `atoms_by_index` が `select_animation_context` 内で複数回再構築される

**場所:** `tools/view_json_pyvista.py:561`, `L842`, `L909`

`animation_paths` → `select_animation_context` の中で、`shared_periodic_shift`・`shared_rotation_angle`・`representative_mapping_entry` がそれぞれ独立して `{atom["index"]: atom for atom in render_data["atoms"]}` を再構築している。

Jacobsite (56原子 × 192操作) では起動時スキャンで計 192 × 3 = 576 回の dict 構築が走る。

**修正案:** `animation_paths` で1回だけ構築して下流すべてに引数として渡す。

---

### Bug (中): `selected_mapping` と `operation_by_index` が O(n) 線形スキャン

**場所:** `crystal_viewer/viewer/operation_lookup.py:4`, `L39`

`operation_summaries` の192回のループ内で毎回 `selected_mapping(atom_mappings, op_index)` が全マッピングをスキャン。

**修正案:** 呼び出し前に dict 化して渡す:
```python
mapping_by_op = {m["operation_index"]: m for m in (atom_mappings or {}).get("mappings", [])}
```

---

### Bug (小): `normalize` が3箇所で重複定義、許容値が不統一

**場所:**
- `tools/view_json_pyvista.py:1702` — `1e-12`
- `crystal_viewer/molecule_analysis.py:325` — `TOL = 1e-7`
- `crystal_viewer/render_data.py:366` — `1e-12`

`molecule_analysis` 側が `1e-7` と5桁大きく、ゼロベクトル判定の挙動が異なる。
共有 utility モジュール (`crystal_viewer/viewer/geometry.py` 等) に統一を推奨。

---

### Bug (小): `plane_basis_from_normal_cart` が2箇所で重複定義

**場所:** `tools/view_json_pyvista.py:1470` と `crystal_viewer/viewer/custom_operation.py:212`

ロジック同一。`custom_operation.py` は `viewer` をすでにインポートしているので `viewer.plane_basis_from_normal_cart(...)` に一本化できる。

---

### Bug (小): `rotation_angle_deg` が2箇所で重複定義

**場所:** `tools/view_json_pyvista.py:1187` と `crystal_viewer/molecule_analysis.py:280`

同一アルゴリズム。共有ユーティリティに移動後、`molecule_analysis` 側はインポートで使うだけにする。

---

### Bug (小): `effective_operation_center` の結晶専用スナップ処理が分子モードでも前段まで実行される

**場所:** `tools/view_json_pyvista.py:1109-1148`

```python
def effective_operation_center(render_data, operation, center, shared_shift):
    kind = str(operation["kind"])
    affine = operation_affine_matrix_translation(render_data, operation, shared_shift)
    if affine is None:
        return center
    matrix, translation = affine
    point = None
    if kind == "inversion":
        point = 0.5 * translation   # ← 分子でも計算される
    elif "rotoinversion" in kind:
        ...                          # ← 分子でも計算される
    # 後続の lattice snapping は unit_cell is None で自動スキップ
```

分子モードでは `unit_cell is None` により格子スナップはスキップされるが、`point` の計算（行列演算）は実行される。意図は正しいが、分子モードで早期リターンすることで意図が明確になる:

```python
if render_data.get("unit_cell") is None:
    return center
```

---

### 効率/設計: 結晶専用ロジックが `animation_paths` / `animation_target` に埋め込まれている

**場所:** `tools/view_json_pyvista.py:550-620`, `L986-1031`

`shared_periodic_shift`・`symmetry_element_shared_shift`・`periodic_target_candidates` は分子モードで常に `None` / 要素1の配列を返し、無意味なコストになっている。

```python
# periodic_target_candidates — 分子では必ずこのパスを通る
if frac is None or unit_cell is None:
    return np.asarray([entry["transformed_cart"]], dtype=float)
```

**提案:** `animation_paths` の先頭で `source_kind` を判定し、分子モードは簡略パスに分岐することで結晶専用の探索コストを排除する:
```python
if render_source_kind(render_data) == "molecule":
    return _animation_paths_molecule(render_data, operation, mapping, ...)
```

---

### 効率: `select_animation_context` の候補スコアリングで分子モードが無駄な全原子パス構築

**場所:** `tools/view_json_pyvista.py:642-687`

```python
candidates = [build_animation_context(..., element_index=i) for i in range(max_count)]
# ↓ 各候補について全原子のパスを構築してスコアリング
for context in candidates:
    score = animation_context_score(...)
```

分子モードでは各操作の要素数が1以下（axes/planes/centers それぞれ高々1個）なので `candidates` は常に長さ1。スコアリングループに入る前に早期リターンを追加することで、分子の全操作スキャンのコストを大幅に削減できる:

```python
if len(candidates) == 1:
    return candidates[0]
```

---

### 結晶・分子の共通化・分離まとめ

**統一推奨（重複関数）:**

| 関数 | 現在の場所 |
|---|---|
| `normalize` | `view_json_pyvista`, `molecule_analysis`, `render_data` |
| `plane_basis_from_normal_cart` | `view_json_pyvista`, `custom_operation` |
| `rotation_angle_deg` | `view_json_pyvista`, `molecule_analysis` |
| `rotate_about_axis` / `rotate_vector` | `view_json_pyvista`, `operation_labels`（API違いだが同アルゴリズム）|

→ `crystal_viewer/viewer/geometry.py` に集約推奨。

**分離推奨（現在 animation_paths 内に結晶専用コードが混在）:**

| 関数 | 性質 |
|---|---|
| `shared_periodic_shift` | 結晶専用（分子では常に None）|
| `symmetry_element_shared_shift` | 結晶専用（分子では常に None）|
| `periodic_target_candidates` | 結晶で27候補、分子で1候補 |
| `operation_affine_matrix_translation` の `shared_shift` 補正 | 結晶専用 |

### Codex 対応 (2026-05-22)

- `selected_mapping()` は `operation_index` -> mapping の内部キャッシュを持つように修正。
- `operation_by_index()` は operations list の id/length 単位で内部キャッシュするように修正。
- `animation_paths()` で構築した `atoms_by_index` を `shared_periodic_shift()` / `shared_rotation_angle()` に渡し、同じ辞書の再構築を削減。
- `select_animation_context()` は候補が1件だけならスコアリングを省略して即返すように修正。
- `effective_operation_center()` は分子モード (`unit_cell is None`) では早期returnし、結晶専用の固定点補正を実行しないように明確化。
- `view_json_pyvista.py` の大規模分割と geometry utility 統合は妥当だが、現在の未コミット機能差分に重ねるとリスクが高いため次の整理タスクへ回す。

---

## Claude レビュー (2026-05-22) — 処理ロジック精査（分岐以外）

対象: `tools/view_json_pyvista.py`, `tools/view_json_gui.py`, `crystal_viewer/viewer/pyvista_controller.py`, `crystal_viewer/viewer/atom_style.py`, `tools/view_json_server.py`

---

### Bug (中): `effective_rotation_axis` が improper パスで2回計算される

**場所:** `tools/view_json_pyvista.py:1234`, `L1393`

`build_operation_path` で axis を計算・更新してから `improper_path` に渡すが、`improper_path` 内部でも同じ引数で再計算している。`effective_rotation_axis` は `rotation_axis_from_matrix`（`np.linalg.eig`）を呼ぶ場合があり無駄なコスト。

```python
# build_operation_path (L1234)
axis = effective_rotation_axis(operation, axis, center)
...
return improper_path(start, target, operation, axis, ...)

# improper_path 内 (L1393)
axis = effective_rotation_axis(operation, axis, center)  # ← 同じ計算が再実行される
```

**修正案:** `improper_path` 冒頭の呼び出しを削除。渡された `axis` をそのまま使う。

---

### Bug (中): GUI ビューアが操作タイプの速度乗数を適用しない

**場所:** `tools/view_json_gui.py:362-370`

`BrowserControlledViewer` は mirror/inversion/translation/glide に `multiplier=2.0` を適用するが、`NativePyVistaViewer.on_timer` は乗数なしで `frame_position += speed` するだけ。mirror アニメーションが回転より2倍の実時間をかけて完了し、ブラウザビューアと挙動が一致しない。

**修正案:**
```python
def on_timer(self, step: int) -> None:
    ...
    multiplier = viewer.operation_speed_multiplier(self.current_operation())
    self.frame_position = min(self.frame_position + self.speed * multiplier, self.frame_count - 1)
```

---

### Bug (小): `build_paths` で `selected_atoms[0]` を固定の代表原子に使う

**場所:** `tools/view_json_gui.py:318`

`scope="displayed"` / `"unit_cell"` のとき `selected_atoms` は全原子リスト。`representative_atom = selected_atoms[0]`（原子 0）として渡すため、`representative_mapping_entry` は移動チェックなしに原子 0 を使う。

原子 0 が操作の固定点（回転軸上など）だった場合: `shared_periodic_shift` が `rint(start_frac - raw_frac)` を計算し、非ゼロになりうる。このシフトが全原子に適用されると、アニメーション先が1格子分ずれる可能性がある。

**修正案:** `scope` が `"displayed"` / `"unit_cell"` のとき `representative_atom=None` を渡し、内部の自動選択に委ねる:
```python
representative_atom = selected_atoms[0] if self.scope == "selected" and selected_atoms else None
```

---

### Bug (小): `atom_radius(atomic_number, scene_span_value)` に死んだパラメータ

**場所:** `crystal_viewer/viewer/atom_style.py:145-147`

```python
def atom_radius(atomic_number: int, scene_span_value: float) -> float:
    del scene_span_value  # 即廃棄
    return element_radius_angstrom(atomic_number)
```

現行コードではこの関数を直接呼び出す箇所は存在せず、ビューアの `self.atom_radius` メソッドは `display_atom_radius` を経由している。実質的に未使用の関数。

**修正案:** 関数を削除して `display_atom_radius` に統一する。

---

### Bug (小): `display_radius_scale` がロックなしで `render_data` dict を変更する

**場所:** `crystal_viewer/viewer/atom_style.py:186-190`

```python
render_data["_display_radius_scale"] = result  # タイマースレッドからロックなし書き込み
```

`render_data` は HTTP スレッドが `state_lock` 下で読む辞書と同一オブジェクト。CPython GIL により実害はないが、`render_data` を読み取り専用として扱うべき設計に反する。

**修正案:** スケール値をビューア側（例: `self._display_radius_scale`）に保持し、`render_data` を変更しない。

---

### 効率: `save_current_gif` が全フレームをメモリに保持してから書く

**場所:** `crystal_viewer/viewer/pyvista_controller.py:713-729`

48フレーム × スクリーンショット（解像度次第で 5〜15 MB/枚）= ピーク数百 MB。

**修正案:** `imageio.get_writer` でストリーミング書き込みに変更し、最後の1フレームだけ保持:
```python
last_image = None
with imageio.get_writer(output_path, fps=fps, loop=0) as writer:
    for frame in range(frames):
        ...
        if image is not None:
            writer.append_data(image)
            last_image = image
    if last_image is not None:
        for _ in range(hold_frames):
            writer.append_data(last_image)
```

---

### 効率: `example_catalog` が `/api/examples` 初回呼び出しまで未初期化

**場所:** `tools/view_json_server.py:246-255`

複数 HTTP スレッドが同時に最初の `/api/examples` を処理するとカタログを複数回構築する（ファイルシステムスキャンの重複）。

**修正案:** `main()` のサーバー起動前に1回呼んで初期化:
```python
# start_server の前に
example_catalog()  # キャッシュを事前ウォームアップ
```

### Codex 対応 (2026-05-22, 処理ロジック精査)

- `improper_path()` 内の `effective_rotation_axis()` 再計算を削除し、呼び出し元で補正済みの axis をそのまま使うように修正。
- native PyVista GUI の `on_timer()` に `operation_speed_multiplier()` を適用し、ブラウザ版とアニメーション速度を揃えた。
- native PyVista GUI の `build_paths()` では `scope="selected"` のときだけ明示代表原子を渡し、`displayed` / `unit_cell` は自動選択に委ねるように修正。
- 未使用の `atom_radius()` 関数と stale import を削除し、表示半径は `display_atom_radius()` に統一。
- `display_radius_scale()` は `render_data` に `_display_radius_scale` を書き込まない純粋計算に変更。計算量は小さく、ロックなし mutation を避ける方を優先。
- `save_current_gif()` は `imageio.get_writer()` によるストリーミング書き込みへ変更し、保持する画像を最後の1フレームだけにした。
- サーバー起動前に `example_catalog()` を呼び、初回 `/api/examples` の同時アクセスで重複初期化しないようにした。

### Codex 追加精査 (2026-05-22)

- example の解決を CWD ではなくプロジェクトルート基準に変更し、別ディレクトリから起動・import しても `examples/...` が正しく解決されるようにした。
- `selected_mapping()` のキャッシュは `atom_mappings` dict に内部キーを書き込まず、mappings list の id/length ベースのモジュール内キャッシュに変更した。

---

## Claude レビュー (2026-05-22) — view_json_pyvista.py 分離後バグ確認

対象変更: `tools/view_json_pyvista.py` の大規模分割
新規ファイル: `crystal_viewer/geometry.py`, `crystal_viewer/viewer/animation_path.py`, `crystal_viewer/viewer/animation_context.py`, `crystal_viewer/viewer/animation.py`, `crystal_viewer/viewer/scene_rendering.py`, `crystal_viewer/viewer/symmetry_elements.py`

---

### Bug (高) — 今回の分離で導入: `viewer.effective_rotation_axis` が消えた

**場所:** `crystal_viewer/viewer/operation_labels.py:378`

```python
axis = viewer.effective_rotation_axis(operation, None, center)
```

旧 `view_json_pyvista.py` (L1092) に定義されていた `effective_rotation_axis` が、今回の分離で `crystal_viewer/viewer/animation_path.py` に移動された。しかし `view_json_pyvista.py` も `animation.py` もこの関数を再エクスポートしていない。

**実測で確認:**
```
ATTRIBUTEERROR: module 'tools.view_json_pyvista' has no attribute 'effective_rotation_axis'
```

**影響範囲:** `operation_labels.effective_axis_from_operation()` が呼ばれる条件:
- `display_symmetry_elements(render_data, None, op_index, None)` — `atom_mappings=None` で呼んだ場合
- `operation_summaries(render_data, None)` — `atom_mappings` なしで呼んだ場合

通常の起動（JSON に atom_mappings が含まれる場合）では隠れる。`--no-mapping` フラグや将来のコードで `atom_mappings=None` を渡すと即クラッシュ。

**修正案:** `crystal_viewer/viewer/animation.py` の `animation_path` インポートに追加:
```python
from crystal_viewer.viewer.animation_path import (
    build_operation_path,
    effective_rotation_axis,   # ← 追加
    evaluate_path,
    ...
)
```
さらに `tools/view_json_pyvista.py` の `animation` インポートにも追加:
```python
from crystal_viewer.viewer.animation import (
    animation_paths,
    build_operation_path,
    effective_rotation_axis,   # ← 追加
    ...
)
```

---

### Bug (中) — 分離前から存在: `viewer.operation_speed_multiplier` が未定義

**場所:** `tools/view_json_gui.py:366`

```python
multiplier = viewer.operation_speed_multiplier(self.current_operation())
```

`operation_speed_multiplier` は `crystal_viewer/viewer/pyvista_controller.py:941` に定義されているが、`view_json_pyvista` モジュールには含まれていない。旧 `view_json_pyvista.py`（1710行版）にもこの関数は存在しなかったため、今回の分離前から壊れていた既存バグ。

**修正案:**
```python
# view_json_gui.py に直接インポートを追加
from crystal_viewer.viewer.pyvista_controller import operation_speed_multiplier
# viewer.operation_speed_multiplier(...) → operation_speed_multiplier(...) に変更
```
または `view_json_pyvista.py` に `pyvista_controller` から re-export する。

---

### 確認済み（問題なし）

- 全新規モジュールのインポートが正常に通ること ✓
- `improper_path` 内の `effective_rotation_axis` 二重呼び出し（旧バグ）が解消されている ✓
- `pyvista_controller.py` が `viewer.X` で使う関数はすべて `view_json_pyvista` 経由で解決できる ✓（`effective_rotation_axis` 以外）
- `normalize` が `crystal_viewer/geometry.py` に統合されている ✓
- 循環インポートなし ✓

### Codex 対応 (2026-05-22, 分離後レビュー)

- `effective_rotation_axis` を `animation.py` と `view_json_pyvista.py` で再エクスポートし、`operation_labels.py` の既存 `viewer.effective_rotation_axis(...)` 参照を復旧。
- `operation_speed_multiplier` / `custom_operation_speed_multiplier` を `animation.py` に移し、`view_json_pyvista.py` からも参照できるようにした。
- `pyvista_controller.py` は同じ速度倍率関数を `animation.py` から import するようにし、重複定義を削除。

---

## Claude レビュー (2026-05-22) — 直近2コミット確認

対象コミット:
- `76cc1af` Decouple native GUI from PyVista CLI facade
- `6011e24` Move PyVista CLI helpers into viewer package

---

### 修正確認: 前回レポートした2バグが解消されていた ✓

**`viewer.effective_rotation_axis` 欠損 (高):**
`animation.py` の `animation_path` インポートに `effective_rotation_axis` が追加済み。
`operation_summaries(render_data, None)` でもクラッシュしないことを実測確認:
```
jacobsite: with_mappings=192  without_mappings=192  OK
```

**`viewer.operation_speed_multiplier` 欠損 (中):**
`operation_speed_multiplier` / `custom_operation_speed_multiplier` が `animation.py` に移動・定義され、`view_json_gui.py` は `crystal_viewer.viewer.animation` から直接インポートするよう修正済み。

---

### 変更概要（バグなし）

**`tools/view_json_gui.py`:**
- `from tools import view_json_pyvista as viewer` を削除し、`crystal_viewer.*` から直接インポートに全面移行。
- `representative_atom = selected_atoms[0] if self.scope == "selected" and selected_atoms else None` に修正 — 前回レビューで指摘した「scope=displayed/unit_cell のとき atom[0] を代表にしていた」バグが解消されている。

**`crystal_viewer/viewer/cli_helpers.py` (新規):**
- `parse_selected_atoms`, `print_operations`, `print_elements`, `print_mapping`, `add_title` をここに集約。
- PyVista (`pyvista`) に依存するのは `add_title` のみ (`pv.Plotter` を引数で受け取るだけで import 宣言はある)。

**`crystal_viewer/viewer/cli_animation.py` (新規):**
- `run_animation`, `effective_animation_fps` を移動。
- `frames = max(frame_count, 2)` → `frame / (frames - 1)` でゼロ除算なし ✓

**`tools/view_json_pyvista.py`:**
- 旧来の全 re-export を削除し、178行の純粋な CLI エントリポイントに縮小。
- `numpy`、`animation_paths`、`atom_color` 等の重量ライブラリ・関数をインポートしなくなった。

---

### 残留確認事項（新バグなし）

- `from tools import view_json_pyvista as viewer` を使うファイルがプロジェクト内に0件であることを確認済み ✓
- 全モジュールの import チェーン（循環なし）✓
- 機能テスト（jacobsite rotoinversion / water / アニメーションパス構築）すべて OK ✓

---

## Claude レビュー (2026-05-22) — Jacobsite 読み込み遅延の原因調査

**症状:** ブラウザで "Open Example → Jacobsite" を選択すると他の構造より明らかに読み込みが遅い。

---

### 原因1（主因・修正可能）: 7MB JSON を2回パースしている

**場所:** `tools/view_json_server.py`  
- `cached_export_json_path()` (L695): キャッシュ有効チェックのために `jacobsite.json`（7MB）を全読み込み＋パース
- `handle_open_example()` (L480): 直後に同じファイルをもう一度読み込み＋パース

```python
# cached_export_json_path の中
payload = json.loads(output_path.read_text(encoding="utf-8"))  # 7MB パース
...
return output_path  # payload を捨てる ← ここが問題

# handle_open_example の呼び出し側
new_payload = json.loads(json_path.read_text(encoding="utf-8"))  # 同じ 7MB を再パース
```

**実測値:**
```
1st parse (cache check): 46ms
2nd parse (load):        43ms  ← 丸ごと無駄
合計の無駄:              89ms
```

**修正案:** `cached_export_json_path` がパース済みペイロードも返すように変更し、呼び出し側で再パースしない。

```python
def cached_export_json_path(
    input_path, output_path, *, mode
) -> tuple[Path, dict] | None:
    ...
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    ...
    return output_path, payload  # payload も返すことで二重パースを排除
```

---

### 原因2（副因・構造的）: jacobsite.json が 7MB と突出して大きい

```
agcl.json      22KB  (4 ops)    → 瞬時
f2_pd.json    126KB  (12 ops)   → 瞬時
halite.json   1.1MB  (192 ops)  → やや体感あり
jacobsite.json 7.0MB (192 ops)  → 明確に遅い
```

56原子 × 192操作 × `atom_mappings` エントリ（`transformed_cart` / `transformed_frac` / `wrapped_frac` / `animation_frac` の 4 種 × 各 3 float）によりファイルが肥大化している。同じ 192 操作の halite（8 原子）の 6 倍のサイズ。

---

### 原因3（既に改善済み）: `operation_summaries` の計算コスト

```
operation_summaries (192 ops): 59ms  ← 旧バージョンの 700ms から大幅改善
```

`display_symmetry_elements`（`select_animation_context` を呼ぶ重い処理）→ `selected_elements`（単純なフィルタ）への切り替えにより解消済み。現状では問題ではない。

---

### 構造別・フル読み込み時間の実測比較

```
構造           サイズ    二重パース    summaries    合計
─────────────────────────────────────────────────────
agcl (4 ops)    22KB       <1ms          <1ms      ~2ms
f2_pd (12 ops) 126KB        4ms           5ms      ~9ms
halite (192op) 1.1MB       20ms          59ms     ~80ms
jacobsite      7.0MB       89ms          59ms    ~150ms
```

Jacobsite が他と比べて遅い直接原因は JSON サイズによる二重パースコスト。`operation_summaries` は 192 ops でも 59ms と共通のため、ファイルサイズだけが差を生む。

---

### 推奨対応優先順位

1. **二重パース解消（即効性あり）:** `cached_export_json_path` が `(path, payload)` を返すよう変更し、`handle_open_example` での再読み込みを廃止。約 43ms 削減。
2. **参考・将来対応:** `atom_mappings` エントリから `animation_frac` / `wrapped_frac` など再計算可能なフィールドをエクスポート時に省略してファイルサイズを削減（ただし viewer 側でのオンザフライ計算が必要になるためトレードオフあり）。

### Codex 対応状況（2026-05-22）

- `1e893c3` で example 構造の読み込み時に既存 JSON キャッシュを再利用するよう変更済み。
- `47626a1` で `operation_summaries` を軽量な `selected_elements` ベースに変更済み。
- `a2a7945` で `cached_export_json_path()` がパース済み payload を返し、`handle_open_example()` 側の二重 JSON パースを解消済み。

残る将来対応は JSON 自体の軽量化。`atom_mappings` の一部フィールド省略は viewer 側の再計算設計が必要なため、現時点では未着手。

---

## Claude 設計メモ (2026-05-22) — 表示範囲（Range）拡張時の描画重さ改善案

**症状:** ブラウザの Display Range を source → ±1/4 → ±1 と広げると PyVista 画面の更新が重い。  
VESTA は同操作が瞬時に完了する。

---

### なぜ VESTA が速いか

VESTA は **GPU インスタンシング** を使用。元素種ごとに球メッシュ1つをGPUにアップロードし、全原子位置の変換行列をまとめて渡して1回のドローコールで描画する。

---

### 現在のビューアが遅い理由

**場所:** `crystal_viewer/viewer/pyvista_controller.py` `ensure_display_atom()`

```python
actor = self.plotter.add_mesh(mesh, color=color, ...)
actor.SetPosition(*center)
```

原子インスタンス1つにつき1回 `plotter.add_mesh()` を呼ぶ個別 actor 方式。

```
Jacobsite ±1 表示: 56 原子 × 最大 27 周期イメージ = ~1512 actor
= 1512 回の plotter.add_mesh()  (初回作成時)
= 1512 ドローコール / フレーム  (描画時)
```

`atom_actor_cache` によりモード間での actor 再利用は実装済みだが、**初回作成コスト**と**フレームごとのドローコール数**が多いことが根本原因。

---

### アニメーションを維持しつつ高速化できるか → できる

**アプローチ: glyph メッシュ ＋ VTK 点座標インプレース更新**

PyVista の `glyph()` (内部: VTK `vtkGlyph3D`) を使うと、元素種ごとに1つの actor で全インスタンスを描画できる。

```python
# 初期化: 元素ごとに1 glyph actor
cloud = pv.PolyData(positions_array)  # 全原子座標 shape=(N, 3)
glyphs = cloud.glyph(geom=sphere_template, scale=False)
actor = plotter.add_mesh(glyphs, color=element_color)

# アニメーション毎フレーム
cloud.points[animated_indices] = new_positions  # numpy 配列インプレース更新
cloud.Modified()                                 # VTK に変更通知
plotter.render()
```

```
Jacobsite ±1 表示: 元素種 3 (Mn/Fe/O) → 3 actor = 3 ドローコール / フレーム
```

アニメーションの精度・コストは現行 (`actor.SetPosition()` × N) と同等。

---

### 互換性上の注意点

| 機能 | 現行 | glyph 移行後 |
|---|---|---|
| 原子ごとの色変更 | `actor.GetProperty().SetColor()` | glyph の `point_data` にカラー配列 (`vtkUnsignedCharArray`) を持たせて更新 |
| unit_cell_only フラグ | `path["unit_cell_only"]` で判定 | primary image のインデックスのみ更新 |
| unmapped atom ワイヤーフレーム | 個別 actor（現行どおり） | 変更不要（少数なので個別 actor で問題なし） |

---

### 変更が必要なコンポーネント

| 変更箇所 | 変更内容 |
|---|---|
| `rebuild_display_atoms` | 個別 actor 生成 → 元素ごと glyph 作成（`atom_actor_cache` 廃止） |
| `update_atoms` | `actor.SetPosition()` × N → `cloud.points[indices] = new_pos` + `Modified()` |
| `apply_atom_colors` | `actor.GetProperty().SetColor()` → `point_data` カラー配列更新 |
| `NativePyVistaViewer` 側 | 同様の変更（`BrowserControlledViewer` と共通化） |

---

### 実装上の推奨事項

- `atom_actor_cache` と `sphere_mesh_cache` を廃止し、`element_glyph_actors: dict[str, tuple[pv.PolyData, vtkActor]]`（元素 → (cloud, actor)）に置き換える。
- `cloud.points` は `display_atom_instances()` の出力から毎回構築し直すのではなく、表示モードごとに numpy 配列をキャッシュしておくと display mode 切り替えが配列スワップだけで済む。
- 実装前に Jacobsite でのアニメーション正確性（残差 < 2e-14 Å）を確認するテストを準備することを推奨。
- `NativePyVistaViewer` と `BrowserControlledViewer` の両方に影響するため、変更は一度に行うか、`rebuild_display_atoms` / `update_atoms` の実装を base class 側で一本化してから行うと安全。

### Codex 対応状況（2026-05-22）

- `44ccf30` で Display Range の中心処理を統一。`source` / `expanded_*` の特殊扱いを減らし、全モードで原点中心の表示座標に揃えた。
- `673d89b` で `crystal_viewer/viewer/atom_instances.py` を追加し、`display_atom_instances()` の結果を元素ごとのバッチにまとめる `element_instance_batches()` を実装済み。
- Halite / Jacobsite の `source`, `expanded_quarter`, `expanded_half`, `expanded_1_0` で、個別インスタンス数とバッチ内 item 数が一致することを確認済み。

未対応: PyVista 側の glyph actor 置き換え。これは原子色変更・ハイライト・アニメーション更新に影響するため、次は本体描画へ直接入らず、range ごとの原子数と元素バッチ数を確認できる検査ツールを追加してから段階的に進める。
