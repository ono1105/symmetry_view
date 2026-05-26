# Claude Review Request: Jacobsite Animation Changes

このメモは、Jacobsite を基準サンプルにしてから入れたアニメーション関連変更を Claude にレビューしてもらうための依頼書です。

## Review Range

レビュー対象は主に以下のコミットです。

```text
6758e12 Add Jacobsite symmetry check data
002a939 Use representative atom for animation targets
009c2af Share rotation direction in animations
ed2ade7 Use operation matrices for animation paths
```

比較するなら:

```bash
git diff 76a1b2f..ed2ade7
```

## Current Baseline

今後の検証基準は `examples/structures/jacobsite.cif` / `exports/jacobsite.json` です。

```text
space group: 227 Fd-3m
point group: m-3m
sites: 56
operations: 192
```

代表確認操作:

```text
op 1   screw_4
op 4   rotation_2
op 24  inversion
op 25  rotoinversion_or_improper_4
op 26  glide
op 31  mirror
```

現在の GIF 確認対象はここだけです。

```text
exports/checks/current/
```

特に見てほしいファイル:

```text
exports/checks/current/jacobsite_op04_rotation2_all.gif
exports/checks/current/jacobsite_op25_rotoinversion4_all.gif
exports/checks/current/jacobsite_op31_mirror_all.gif
```

古い GIF は修正前の動きが混ざっているため、レビュー対象にしないでください。

## Main Changes

### 1. Jacobsite sample and export

Added:

```text
examples/structures/jacobsite.cif
exports/jacobsite.json
```

`exports/` 直下は共有用 JSON のみを置く方針です。確認用 GIF/PNG は ignored の `exports/checks/current/` に生成しています。

### 2. Representative atom animation target

全原子アニメーションで、各原子が個別に近い周期像を選ぶと、同じ対称操作ではなく複数の等価操作が混ざって見える問題がありました。

対応:

```text
--animation-scope all|representative
--representative-atom INDEX
```

`all` では、代表原子で決めた整数格子シフトを全原子に共有します。

### 3. Shared rotation direction

周期シフトを共有しても、回転角の符号が原子ごとに `+180/-180` などに割れる問題がありました。

対応:

```text
代表原子または操作行列から決めた回転符号を全原子に共有
180度回転は見た目の一貫性のため +180 に固定
```

### 4. Operation matrices in JSON schema v3

rotoinversion は軸・角度・中心を RenderData element だけから復元すると不安定でした。

対応:

```text
schema_version = 3
RenderOperationData.matrix_frac
RenderOperationData.translation_frac
RenderOperationData.matrix_cart
RenderOperationData.translation_cart
```

Viewer は `matrix_cart` / `translation_cart` から最終位置を計算します。AtomMapping は対応関係と代表原子選択には使いますが、アニメーションの幾何は操作行列を優先します。

### 5. Roto-inversion path

Jacobsite `op 25` は、現状では以下として動かします。

```text
rotoinversion_or_improper_4:
  rotation phase
  inversion phase
```

`matrix_cart` から `rotation = -matrix_cart` を取り出し、回転軸・回転角を復元しています。

## Important Files

重点レビュー対象:

```text
tools/view_json_pyvista.py
crystal_viewer/render_data.py
crystal_viewer/json_export.py
docs/VIEWER_GUIDE.md
docs/REVIEW_NOTES.md
```

特に `tools/view_json_pyvista.py` の以下を見てください。

```text
animation_paths
representative_mapping_entry
shared_periodic_shift
shared_rotation_angle
operation_affine_target
effective_operation_center
effective_rotation_axis
operation_rotation_matrix
build_operation_path
improper_path
evaluate_path
```

## Verification Commands

構文と JSON:

```bash
.venv/bin/python -m py_compile crystal_viewer/render_data.py crystal_viewer/json_export.py tools/view_json_pyvista.py
.venv/bin/python -m json.tool exports/jacobsite.json /tmp/jacobsite_checked.json
```

Jacobsite 操作確認:

```bash
.venv/bin/python tools/view_json_pyvista.py exports/jacobsite.json --list-operations
.venv/bin/python tools/view_json_pyvista.py exports/jacobsite.json --operation 1 --list-elements
.venv/bin/python tools/view_json_pyvista.py exports/jacobsite.json --operation 25 --list-elements
```

現行 GIF 生成:

```bash
mkdir -p exports/checks/current
.venv/bin/python tools/view_json_pyvista.py exports/jacobsite.json --operation 1 --element-index 0 --animate --animation-scope all --animation-frames 24 --animation-fps 6 --animation-output exports/checks/current/jacobsite_op01_screw4_all.gif
.venv/bin/python tools/view_json_pyvista.py exports/jacobsite.json --operation 4 --element-index 0 --animate --animation-scope all --animation-frames 24 --animation-fps 6 --animation-output exports/checks/current/jacobsite_op04_rotation2_all.gif
.venv/bin/python tools/view_json_pyvista.py exports/jacobsite.json --operation 24 --element-index 0 --animate --animation-scope all --animation-frames 24 --animation-fps 6 --animation-output exports/checks/current/jacobsite_op24_inversion_all.gif
.venv/bin/python tools/view_json_pyvista.py exports/jacobsite.json --operation 25 --element-index 0 --animate --animation-scope all --animation-frames 24 --animation-fps 6 --animation-output exports/checks/current/jacobsite_op25_rotoinversion4_all.gif
.venv/bin/python tools/view_json_pyvista.py exports/jacobsite.json --operation 26 --element-index 0 --animate --animation-scope all --animation-frames 24 --animation-fps 6 --animation-output exports/checks/current/jacobsite_op26_glide_all.gif
.venv/bin/python tools/view_json_pyvista.py exports/jacobsite.json --operation 31 --element-index 0 --animate --animation-scope all --animation-frames 24 --animation-fps 6 --animation-output exports/checks/current/jacobsite_op31_mirror_all.gif
```

Numerical check used by Codex:

```bash
.venv/bin/python - <<'PY'
import json
import numpy as np
from tools import view_json_pyvista as v

payload=json.load(open('exports/jacobsite.json'))
rd=payload['render_data']
assert payload['schema_version'] == 3
expected = {
    1: ('screw_4', [90.0], 1e-10),
    4: ('rotation_2', [180.0], 1e-10),
    24: ('inversion', [], 1e-10),
    25: ('rotoinversion_or_improper_4', [90.0], 1e-10),
    26: ('glide', [], 1e-10),
    31: ('mirror', [], 1e-10),
}
for op_idx, (kind, expected_angles, tol) in expected.items():
    mapping=v.selected_mapping(payload['atom_mappings'], op_idx)
    op=v.operation_by_index(rd['operations'], op_idx)
    assert op['kind'] == kind
    paths=v.animation_paths(rd, op, mapping, element_index=0, animation_scope='all')
    residuals=[]
    angles=[]
    for path in paths.values():
        stack=[path]
        while stack:
            cur=stack.pop()
            if cur['type']=='sequential':
                stack.extend(cur['segments'])
            if cur['type'] in ('rotation','mirror','inversion'):
                residuals.append(np.linalg.norm(cur.get('residual', np.zeros(3))))
            if cur['type']=='rotation':
                angles.append(round(float(np.degrees(cur['angle'])), 6))
    unique_angles=sorted(set(angles))
    assert unique_angles == expected_angles, (op_idx, unique_angles, expected_angles)
    assert max(residuals or [0]) < tol, (op_idx, max(residuals or [0]))
    print('ok', op_idx, kind, unique_angles, f'{max(residuals or [0]):.2e}')
PY
```

Expected output:

```text
ok 1 screw_4 [90.0] 0.00e+00
ok 4 rotation_2 [180.0] ~4.62e-15
ok 24 inversion [] 0.00e+00
ok 25 rotoinversion_or_improper_4 [90.0] ~3.66e-15
ok 26 glide [] 0.00e+00
ok 31 mirror [] ~7.64e-15
```

## Specific Questions For Claude

最重要: ユーザーは現在の GIF を見て、以下に強い違和感を持っています。数値チェックが通っていても、視覚的・教育的に「同じ対称操作に見えない」なら問題として扱ってください。

```text
1. 回転操作なのに、一部の原子が逆回転して見える。
2. rotoinversion / rotoreflection 系で、原子が全体としてまとまった1つの操作ではなく、ばらばらに動いて見える。
3. 原点や対称要素上にある原子だけが固定され、他の全原子が大きく動くと、操作の見え方として不自然に感じる。
4. mirror / inversion のように数学的には固定点が正しい場合でも、学習用ビューアとしては「なぜ止まるのか」が分からずバグに見える可能性がある。
```

この違和感が、実装バグなのか、対称操作として正しいが見せ方が悪いのか、あるいは代表原子/全原子アニメーションの設計を分けるべきなのかを重点的に判断してください。

1. `matrix_cart = lattice.T @ W @ inv(lattice.T)` and `translation_cart = t @ lattice` are correct for row-vector Cartesian coordinates used in this project. Please verify there is no convention mismatch.
2. In `rotoinversion`, the viewer uses `rotation = -matrix_cart` and then `rotation -> inversion`. Is this decomposition correct for the spglib operation conventions used here?
3. `effective_operation_center()` currently solves the rotoinversion center using `pinv(I + R) @ translation`. Please check whether this is robust for all improper operations we expect, especially cases where `I + R` is singular or non-unique.
4. The current viewer still uses selected axes/planes/centers for visual elements and for primitive path construction. Are there cases where the selected visual element and the affine operation disagree?
5. Mirror operations leave atoms on the mirror plane fixed. That is expected mathematically, but visually it can look like a bug. Should the education viewer keep that exact behavior, or add an optional "representative atom only" default for improper/mirror operations?
6. Are there remaining cases where atom-wise residual correction could reintroduce visually inconsistent motion?

## Current Known Notes

- `exports/checks/current/` contains regenerated GIFs from the current code, but it is intentionally ignored by Git.
- Older generated GIFs outside `exports/checks/current/` may exist as ignored local files. They are not part of the reviewed code.
- `archive/old_gui_attempt/` is old failed GUI work and should not be treated as active implementation.
