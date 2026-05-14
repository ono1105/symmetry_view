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
