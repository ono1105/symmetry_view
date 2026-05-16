# Codex向け：結晶構造ビューアー＋対称要素ビューアー 実装仕様書

## 1. 実装目的

結晶構造を3D表示し、spglibで得た対称操作を使って、対称軸・対称面・対称中心を表示できるビューアーを作る。

最終的には「結晶構造パズル」に発展させるが、まずは以下を実装対象とする。

1. CIFを読み込む
2. 原子と単位胞を3D表示する
3. ユーザー操作で対称性解析を実行する
4. spglibで `W, t` を取得する
5. 既存の対称要素抽出ロジックを組み込める構成にする
6. 対称操作を選択すると、対応する軸・面・中心を表示する
7. 選択原子、または全原子を操作後位置へアニメーションする

---

## 2. 使用ライブラリ

予定ライブラリ:

```text
pymatgen
spglib
numpy
pyvista
pyvistaqt
PyQt6 または PySide6
```

最初はPyVista単体でもよいが、GUI化を前提にするならPyVistaQtを使う。

---

## 3. モード設計

将来的には結晶モードと分子モードを持つ。

ただし、今回の最初の実装は結晶モードを優先する。

```text
Crystal mode:
  CIF読み込み
  pymatgen Structure
  lattice / frac / cart
  spglib解析
  周期境界あり
  単位胞表示あり

Molecule mode:
  後回し
  pymatgen Molecule 等を想定
  cart座標のみ
  周期境界なし
```

分子モードを後から追加できるように、描画層は直交座標ベースで共通化する。

---

## 4. 推奨ディレクトリ構成

例:

```text
crystal_viewer/
├── main.py
├── models.py
├── structure_loader.py
├── viewer.py
├── symmetry_analyzer.py
├── animation.py
└── requirements.txt
```

役割:

```text
main.py:
  アプリ起動、メインウィンドウ

models.py:
  データクラス定義

structure_loader.py:
  CIF読み込み、pymatgen Structure から内部データへ変換

viewer.py:
  PyVista/PyVistaQt描画

symmetry_analyzer.py:
  spglib解析、W,t取得、軸・面・中心計算

animation.py:
  原子移動アニメーション、周期境界処理
```

---

## 5. データ構造

### 5.1 描画用原子

```python
from dataclasses import dataclass
import numpy as np

@dataclass
class RenderAtom:
    index: int
    element: str
    atomic_number: int
    cart: np.ndarray
    frac: np.ndarray | None = None
    selected: bool = False
```

結晶モードでは `frac` を持つ。  
分子モードでは `frac = None` でよい。

### 5.2 結晶構造データ

```python
@dataclass
class CrystalStructureData:
    lattice: np.ndarray
    atoms: list[RenderAtom]
    source_file: str
```

`lattice` は pymatgen の `structure.lattice.matrix` を使う。  
pymatgenでは基本的に各行が格子ベクトル。

```text
lattice[0] = a vector
lattice[1] = b vector
lattice[2] = c vector
```

分率座標から直交座標への変換は以下。

```python
cart = frac @ lattice
```

### 5.3 対称操作

```python
@dataclass
class CrystalSymmetryOperation:
    index: int
    W: np.ndarray
    t: np.ndarray
    kind: str
    order: int | None
```

spglibの操作は分率座標で以下の形。

```text
frac' = W frac + t
```

### 5.4 対称要素

```python
@dataclass
class CrystalAxis:
    direction_frac: np.ndarray
    point_frac: np.ndarray
    operations: list[int]
    kind: str
    order: int | None

@dataclass
class CrystalPlane:
    point_frac: np.ndarray
    basis_frac: np.ndarray
    normal_frac: np.ndarray
    operations: list[int]
    kind: str

@dataclass
class CrystalCenter:
    point_frac: np.ndarray
    operations: list[int]
    kind: str
```

### 5.5 描画用対称要素

```python
@dataclass
class RenderAxis:
    point_cart: np.ndarray
    direction_cart: np.ndarray
    label: str

@dataclass
class RenderPlane:
    point_cart: np.ndarray
    basis1_cart: np.ndarray
    basis2_cart: np.ndarray
    normal_cart: np.ndarray
    label: str

@dataclass
class RenderCenter:
    point_cart: np.ndarray
    label: str
```

描画層では、結晶由来か分子由来かを意識せず、このRender系だけを扱う。

---

## 6. CIF読み込み

`pymatgen` を使う。

```python
from pymatgen.core import Structure

structure = Structure.from_file(cif_path)
```

内部データへの変換例:

```python
def load_crystal_from_cif(cif_path: str) -> CrystalStructureData:
    structure = Structure.from_file(cif_path)
    lattice = structure.lattice.matrix

    atoms = []
    for i, site in enumerate(structure):
        atoms.append(
            RenderAtom(
                index=i,
                element=site.specie.symbol,
                atomic_number=site.specie.Z,
                frac=np.array(site.frac_coords),
                cart=np.array(site.coords),
            )
        )

    return CrystalStructureData(
        lattice=lattice,
        atoms=atoms,
        source_file=cif_path,
    )
```

---

## 7. spglib解析

pymatgen Structure から spglib cell に変換する。

```python
def structure_to_spglib_cell(structure):
    lattice = structure.lattice.matrix
    positions = structure.frac_coords
    numbers = [site.specie.Z for site in structure]
    return lattice, positions, numbers
```

spglib解析:

```python
dataset = spglib.get_symmetry_dataset(
    cell,
    symprec=1e-3,
    angle_tolerance=5.0,
)
```

取得するもの:

```python
rotations = dataset.rotations
translations = dataset.translations
space_group_number = dataset.number
international_symbol = dataset.international
hall_symbol = dataset.hall
point_group = dataset.pointgroup
```

各操作は以下のペア。

```text
W = rotations[i]
t = translations[i]
frac' = W frac + t
```

---

## 8. 対称操作分類

分類方針:

```text
W = I, t = 0:
  identity

W = I, t != 0:
  pure translation / centering translation

W = -I:
  inversion

det(W) = +1:
  rotation or screw

det(W) = -1:
  mirror / glide / rotoinversion
```

回転次数は `W^n = I` となる最小の `n` で求める。

---

## 9. 対称要素計算

### 9.1 回転軸・らせん軸

軸方向:

```text
(W - I)v = 0
```

軸上の点:

```text
W x + t = x + a v + n
```

整理:

```text
(I - W)x + a v = t + n
```

`n` は整数格子並進。  
探索範囲 `search_range` はデフォルトで `2`。

### 9.2 鏡映面・映進面

面内基底:

```text
(W - I)v = 0
```

法線方向:

```text
(W + I)n = 0
```

面上の点:

```text
(I - W)x + V a = t + n
```

### 9.3 反転中心

```text
(I - W)x = t + n
```

で求める。

---

## 10. 描画仕様

### 10.1 原子表示

PyVistaで球として表示する。

最初は元素ごとの簡単な色・半径でよい。

```text
通常表示:
  球表示

アニメーション中:
  低解像度球または点表示
```

結合表示は後回し。

### 10.2 単位胞表示

結晶モードでは単位胞枠を線で表示する。

格子ベクトル:

```python
a = lattice[0]
b = lattice[1]
c = lattice[2]
```

単位胞8頂点:

```python
vertices = [
    origin,
    a,
    b,
    c,
    a + b,
    a + c,
    b + c,
    a + b + c,
]
```

辺:

```python
edges = [
    (0, 1), (0, 2), (0, 3),
    (1, 4), (1, 5),
    (2, 4), (2, 6),
    (3, 5), (3, 6),
    (4, 7), (5, 7), (6, 7),
]
```

### 10.3 軸表示

`RenderAxis` を線分として描画する。

```python
p = axis.point_cart
v = axis.direction_cart / np.linalg.norm(axis.direction_cart)
p1 = p - length * v
p2 = p + length * v
```

PyVista:

```python
line = pv.Line(p1, p2)
plotter.add_mesh(line, line_width=4)
```

### 10.4 面表示

`RenderPlane` を四角形メッシュとして描画する。

```python
p = plane.point_cart
v1 = plane.basis1_cart
v2 = plane.basis2_cart
```

4頂点:

```python
p - s*v1 - s*v2
p + s*v1 - s*v2
p + s*v1 + s*v2
p - s*v1 + s*v2
```

半透明表示にする。

### 10.5 中心表示

小さい球で表示する。

```python
sphere = pv.Sphere(radius=0.1, center=center.point_cart)
plotter.add_mesh(sphere)
```

---

## 11. UI仕様

最初は簡単なUIでよい。

左パネル:

```text
[Open CIF]
[Analyze Symmetry]

表示:
  [ ] Show atoms
  [ ] Show unit cell
  [ ] Show symmetry elements

Animation target:
  ( ) Selected atoms
  ( ) All atoms

[Play selected operation]
[Clear selection]
```

右側:

```text
PyVista 3D viewer
```

---

## 12. 解析実行タイミング

ファイル読み込み直後は構造だけを表示する。

```text
Open CIF:
  CIF読み込み
  原子表示
  単位胞表示
```

`Analyze Symmetry` ボタンを押したときに解析する。

```text
Analyze Symmetry:
  spglib実行
  W,t取得
  対称操作分類
  軸・面・中心を計算
  操作リストを更新
```

---

## 13. 操作リスト

解析後、左パネルに操作リストを出す。

例:

```text
Operation 0: identity
Operation 1: screw_3
Operation 2: screw_3
Operation 3: rotation_2
Operation 4: rotation_2
Operation 5: rotation_2
```

操作を選択すると、対応する軸・面・中心を3D上で表示する。

---

## 14. 原子選択

アニメーション対象は2モード。

```text
Selected atoms mode:
  ユーザーが選択した原子だけ動かす

All atoms mode:
  全原子を動かす
```

選択原子は以下で管理する。

```python
selected_atom_indices: set[int]
```

最初は3Dクリック選択でなくてもよい。  
左パネルの原子リストから選択できればよい。

例:

```text
[ ] Atom 0 Ga
[ ] Atom 1 Ga
[ ] Atom 2 As
[ ] Atom 3 O
```

将来的には以下を目指す。

```text
クリック:
  単一選択

Ctrl + クリック:
  複数選択に追加 / 解除
```

---

## 15. アニメーション

### 15.1 基本

選択した操作 `W, t` に対して、対象原子の移動先を計算する。

結晶モード:

```python
target_frac = W @ start_frac + t
```

その後、周期境界を考慮して最近接周期像を選ぶ。

### 15.2 最近接周期像

```python
def choose_nearest_periodic_image(start_frac, target_frac, lattice):
    best = None
    best_dist = None

    for shift in itertools.product([-1, 0, 1], repeat=3):
        shift = np.array(shift, dtype=float)
        candidate = target_frac + shift
        dist = np.linalg.norm((candidate - start_frac) @ lattice)

        if best is None or dist < best_dist:
            best = candidate
            best_dist = dist

    return best
```

アニメーション中は `candidate` を使う。  
必要なら最後だけ `candidate % 1.0` に戻す。

### 15.3 最初の補間方式

最初は線形補間でよい。

```python
pos = (1 - s) * start_cart + s * target_cart
```

`s` は `0.0` から `1.0`。

将来的には改良する。

```text
回転:
  軸まわりの円弧補間

らせん:
  回転 + 軸方向移動

反転:
  反転中心を通る直線補間

鏡映:
  面に垂直な方向に面を通過する補間

映進:
  鏡映 + 面内方向移動
```

### 15.4 軽量表示モード

アニメーション開始時:

```text
結合表示OFF
ラベルOFF
低解像度球または点表示へ切替
選択中の対称要素だけ強調
```

アニメーション終了時:

```text
通常表示に戻す
```

---

## 16. カメラ操作

PyVista標準操作を使う。  
VESTA風を目指すが、最初から完全一致でなくてよい。

最低限:

```text
左ドラッグ:
  回転

マウスホイール:
  ズーム

右ドラッグまたは中ドラッグ:
  平行移動

Reset View:
  初期視点に戻す
```

後で追加:

```text
View along a
View along b
View along c
View along x
View along y
View along z
```

---

## 17. 後回しにする機能

最初は以下を実装しない。

```text
結合表示
原子ラベルの詳細表示
高品質なUI
完全なVESTA互換操作
自由入力による軸・面指定
分子点群解析
スコア・ヒント・解説
```

---

## 18. 実装順

推奨順:

```text
Step 1:
  CIFを読み込んで原子と単位胞をPyVistaで表示

Step 2:
  Open CIFボタンを追加

Step 3:
  原子選択機能を追加
  最初は左パネルのリスト選択でよい

Step 4:
  Analyze Symmetryボタンを追加
  spglib解析を実行

Step 5:
  対称操作リストを表示

Step 6:
  操作を選ぶと軸・面・中心を3D表示

Step 7:
  Playボタンで選択原子を操作後位置へアニメーション

Step 8:
  All atoms modeを追加

Step 9:
  アニメーション中の軽量表示モードを追加
```

---

## 19. Codexへの最初の依頼

まずは以下を実装してください。

```text
1. PyVistaまたはPyVistaQtを使った簡単な結晶構造ビューアーを作る
2. pymatgenでCIFを読み込む
3. 原子と単位胞を表示する
4. 簡単なUIでCIFを開けるようにする
5. Analyze Symmetryボタンを用意する
6. spglibで W, t を取得する
7. 対称操作リストを表示する
8. 既存の対称要素抽出コードを組み込める構造にする
9. 操作を選ぶと軸・面・中心を表示する
10. 選択原子だけを操作後位置へアニメーションする
```

実装時は、後から分子モードやパズル機能を追加できるように、描画層・構造データ層・対称性解析層を分けてください。
