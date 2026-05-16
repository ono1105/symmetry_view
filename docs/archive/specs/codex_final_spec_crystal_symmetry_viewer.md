# Codex向け実装仕様書：結晶構造ビューアー + 対称要素ビューアー

## 0. この仕様書の目的

この仕様書は、結晶構造パズルの前段階として、まず以下を実装するためのものです。

1. 段階1: 結晶構造ビューアー
2. 段階2: 対称要素ビューアー

パズル機能は段階3として後で設計・実装します。
今回の実装では、**ビューアーを先に作り、その上に将来パズル機能を載せられる構造**にしてください。

この仕様書は、Claudeとの相談で確定した以下の方針を反映しています。

- ビューアーを先に作り、パズルは後から載せる
- 技術スタックは `pymatgen + spglib + PyVista + PyVistaQt`
- 段階1と段階2を分割して実装する
- 回転アニメーションは最初から円弧補間を使う
- 鏡映・反転・並進は線形補間を使う
- 軸・面・中心は重複解消し、対応する spglib operation index を保持する
- 結合表示・分子点群解析・ゲーム性は後回しにする

---

## 1. 開発方針

旧方針では pygame + PyOpenGL でパズルを直接作る予定でしたが、方針を変更します。

新方針:

```text
pymatgen + spglib + PyVista + PyVistaQt
```

を使って、まず VESTA 風の結晶構造ビューアーと対称要素ビューアーを作ります。

### 技術スタック

- Python
- pymatgen
- spglib
- numpy
- PyVista
- PyVistaQt
- PyQt6 または PySide6

### 役割分担

```text
pymatgen:
  CIF読み込み
  結晶構造データ管理

spglib:
  空間群対称操作 W, t の取得

自作コード:
  W, t から軸・面・中心を計算
  操作分類
  対称要素の重複解消
  原子対応とアニメーション処理

PyVista / PyVistaQt:
  3D描画
  原子・単位胞・軸・面・中心の表示
  GUIへの埋め込み
```

---

## 2. 実装段階

### 段階1: 構造ビューアー

まずは結晶構造を見るための最小ビューアーを作ります。

実装対象:

1. PyVista + PyVistaQt で結晶構造ビューアーを作る
2. pymatgen で CIF を読み込む
3. 原子を3D表示する
4. 単位胞を線で表示する
5. 基本的なカメラ操作を使えるようにする
6. 簡単なUIを作る
   - Open CIF
   - Show atoms
   - Show unit cell
   - Reset view

段階1では、以下は不要です。

- spglib解析
- 対称要素表示
- アニメーション
- パズル機能
- 結合表示

---

### 段階2: 対称要素ビューアー

段階1が動くことを前提に、対称性解析と可視化を追加します。

実装対象:

1. Analyze Symmetry ボタンで spglib 解析を実行
2. `W, t` を取得
3. 対称操作を分類する
4. 回転軸・らせん軸・鏡映面・映進面・反転中心を計算する
5. 軸・面・中心の重複を解消する
6. 対称操作リストをUIに表示する
7. 操作を選択すると、対応する対称要素を3D表示する
8. Selected atoms / All atoms モードでアニメーションする
9. 回転は円弧補間、それ以外は線形補間する
10. 周期境界では最近接周期像を使う

---

### 段階3: パズル化

段階3は今回の実装対象外です。
ただし、後でパズル化できるように、対称要素・operation index・原子対応のデータ構造は保持してください。

---

## 3. ディレクトリ構成案

以下のように、描画・構造・対称性解析・アニメーションを分けてください。

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

### 役割

```text
main.py:
  アプリ起動、メインウィンドウ、UI接続

models.py:
  dataclass定義

structure_loader.py:
  CIF読み込み
  pymatgen Structure から内部データへの変換

viewer.py:
  PyVista / PyVistaQt 描画処理

symmetry_analyzer.py:
  spglib解析
  W,t取得
  操作分類
  軸・面・中心の計算と重複解消

animation.py:
  原子移動アニメーション
  周期境界の最近接像処理
```

---

## 4. データ構造

### 4.1 描画用原子

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

結晶モードでは `frac` を持ちます。
将来の分子モードでは `frac = None` でよいです。

---

### 4.2 結晶構造データ

```python
@dataclass
class CrystalStructureData:
    lattice: np.ndarray
    atoms: list[RenderAtom]
    source_file: str
```

`lattice` は `pymatgen.Structure.lattice.matrix` を使ってください。
pymatgen の `lattice.matrix` は、各行が格子ベクトルです。

```text
lattice[0] = a vector
lattice[1] = b vector
lattice[2] = c vector
```

分率座標から直交座標への変換は以下です。

```python
cart = frac @ lattice
```

spglib に渡す `cell = (lattice, positions, numbers)` の `lattice` も、pymatgen の `structure.lattice.matrix` をそのまま渡してください。転置しないでください。

---

### 4.3 結晶対称操作

```python
@dataclass
class CrystalSymmetryOperation:
    index: int
    W: np.ndarray
    t: np.ndarray
    kind: str
    order: int | None
```

spglib の操作は分率座標で次の形です。

```text
frac' = W frac + t
```

---

### 4.4 結晶対称要素

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

重要: `operations` は、その対称要素に対応する spglib operation index のリストです。
将来のパズル化で使うため、必ず保持してください。

---

### 4.5 描画用対称要素

```python
@dataclass
class RenderAxis:
    point_cart: np.ndarray
    direction_cart: np.ndarray
    label: str
    operations: list[int]

@dataclass
class RenderPlane:
    point_cart: np.ndarray
    basis1_cart: np.ndarray
    basis2_cart: np.ndarray
    normal_cart: np.ndarray
    label: str
    operations: list[int]

@dataclass
class RenderCenter:
    point_cart: np.ndarray
    label: str
    operations: list[int]
```

描画層はこの Render 系だけを使います。
結晶由来か分子由来かを描画層で意識しない設計にしてください。

---

## 5. CIF読み込み

`pymatgen` を使って CIF を読み込みます。

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

## 6. spglib解析

pymatgen Structure から spglib cell に変換します。

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

各操作は次のペアです。

```text
W = rotations[i]
t = translations[i]
frac' = W frac + t
```

---

## 7. 対称操作分類

### 7.1 基本分類

```text
W = I, t = 0:
  identity

W = I, t != 0:
  pure_translation_or_centering_translation

W = -I:
  inversion

det(W) = +1:
  rotation または screw

det(W) = -1 かつ W^2 = I:
  mirror または glide

det(W) = -1 かつ W^2 != I:
  rotoinversion_or_improper
```

回転次数は `W^n = I` となる最小の `n` で求めます。

### 7.2 screw / glide 判定

固定解が存在するかを調べます。

```text
x = W x + t mod 1
(I - W)x = t + n
```

- 回転系で固定軸があれば `rotation_n`
- 回転系で固定軸がなければ `screw_n`
- 鏡映系で固定面があれば `mirror`
- 鏡映系で固定面がなければ `glide`

---

## 8. 対称要素計算

### 8.1 回転軸・らせん軸

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

`n` は整数格子並進です。
探索範囲 `search_range` はデフォルトで `2`。

---

### 8.2 鏡映面・映進面

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

---

### 8.3 反転中心

```text
(I - W)x = t + n
```

で求めます。

---

## 9. 対称要素の重複解消

### 9.1 軸の同一性判定

2つの軸が同じである条件:

1. 方向が平行または反平行
2. 一方の軸上の点が、もう一方の軸上にある
3. 周期境界込みで判定する

つまり、軸1を `p1 + s v1`、軸2を `p2 + s v2` とすると、

```text
p2 - p1 = a v1 + n
```

を満たす実数 `a` と整数ベクトル `n` が存在すれば同じ軸とみなします。

---

### 9.2 面の同一性判定

2つの面が同じである条件:

1. 法線方向が平行または反平行

```text
|n1 · n2| > 1 - tol
```

2. 面1上の点が面2上にある
3. 周期境界込みで判定する

面を `p + a v1 + b v2` とすると、一方の面上の点が他方の面内基底で表せるかを、整数格子並進込みで判定します。

```text
p2 - p1 = a v1 + b v2 + n
```

これを満たす `a, b` と整数ベクトル `n` が存在すれば同じ面とみなします。

---

### 9.3 中心の同一性判定

2つの中心が同じである条件:

```text
p1 - p2 = integer vector
```

を `tol` 以内で満たすこと。

---

## 10. 描画仕様

### 10.1 原子表示

PyVistaで球として表示します。

最初は元素ごとの簡単な色・半径でよいです。

```text
通常表示:
  球表示

アニメーション中:
  低解像度球または点表示
```

結合表示は後回しです。

---

### 10.2 単位胞表示

結晶モードでは単位胞枠を線で表示します。

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

---

### 10.3 軸表示

`RenderAxis` を線分として描画します。

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

---

### 10.4 面表示

`RenderPlane` を四角形メッシュとして描画します。

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

半透明表示にしてください。

---

### 10.5 中心表示

小さい球で表示します。

```python
sphere = pv.Sphere(radius=0.1, center=center.point_cart)
plotter.add_mesh(sphere)
```

---

## 11. 座標変換

結晶の解析は分率座標、描画は直交座標です。

### 11.1 点

```python
point_cart = point_frac @ lattice
```

### 11.2 軸方向

```python
direction_cart = direction_frac @ lattice
```

その後、正規化してください。

### 11.3 面

面の法線は、斜交格子で注意が必要です。

`normal_frac @ lattice` をそのまま使わず、面内基底を直交座標に変換して外積から法線を求めてください。

```python
basis1_cart = basis_frac[:, 0] @ lattice
basis2_cart = basis_frac[:, 1] @ lattice
normal_cart = np.cross(basis1_cart, basis2_cart)
normal_cart = normal_cart / np.linalg.norm(normal_cart)
```

---

## 12. UI仕様

最初は簡単なUIでよいです。

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

## 13. 解析実行タイミング

ファイル読み込み直後は構造だけを表示します。

```text
Open CIF:
  CIF読み込み
  原子表示
  単位胞表示
```

`Analyze Symmetry` ボタンを押したときに解析します。

```text
Analyze Symmetry:
  spglib実行
  W,t取得
  対称操作分類
  軸・面・中心を計算
  操作リストを更新
```

---

## 14. 操作リスト

解析後、左パネルに操作リストを出します。

例:

```text
Operation 0: identity
Operation 1: screw_3
Operation 2: screw_3
Operation 3: rotation_2
Operation 4: rotation_2
Operation 5: rotation_2
```

操作を選択すると、対応する軸・面・中心を3D上で表示します。

---

## 15. 原子選択

アニメーション対象は2モード。

```text
Selected atoms mode:
  ユーザーが選択した原子だけ動かす

All atoms mode:
  全原子を動かす
```

選択原子は以下で管理してください。

```python
selected_atom_indices: set[int]
```

最初は3Dクリック選択でなくてもよいです。
左パネルの原子リストから選択できればよいです。

例:

```text
[ ] Atom 0 Ga
[ ] Atom 1 Ga
[ ] Atom 2 As
[ ] Atom 3 O
```

将来的には以下を目指します。

```text
クリック:
  単一選択

Ctrl + クリック:
  複数選択に追加 / 解除
```

---

## 16. アニメーション

### 16.1 基本

選択した操作 `W, t` に対して、対象原子の移動先を計算します。

結晶モード:

```python
target_frac = W @ start_frac + t
```

その後、周期境界を考慮して最近接周期像を選びます。

---

### 16.2 最近接周期像

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

アニメーション中は `candidate` を使います。
必要なら最後だけ `candidate % 1.0` に戻します。

---

### 16.3 補間方式

最初から以下を実装してください。

#### 回転操作

対象:

```text
det(W) = +1
W != I
```

軸 `v`、軸上の点 `p`、角度 `theta` を使って、Rodrigues 公式で円弧補間します。

```text
pos(s) = p + R(s * theta) @ (start - p)
```

ここで `s` は `0.0` から `1.0`。
`R(alpha)` は軸 `v` まわりの回転行列です。

#### らせん操作

回転は円弧補間、軸方向の並進は線形補間します。

```text
pos(s) = circular_rotation_part(s) + linear_axis_translation_part(s)
```

簡略化として、回転と軸方向並進を独立に合成してよいです。

#### 鏡映

線形補間。

```python
pos = (1 - s) * start_cart + s * target_cart
```

#### 反転

線形補間。
反転中心を通るような直線補間になる。

#### 純粋並進

線形補間。

#### 映進

鏡映と面内並進の合成として、線形補間でよい。

---

### 16.4 Selected atoms mode の挙動

選択原子だけを動かす場合、選択原子が非選択原子の位置へ移ることがあります。

この場合、最初は以下の方針にしてください。

```text
案A:
  そのまま移動させる。
  結果的に非選択原子と重なってもよい。
```

理由:

- 対称操作の挙動を素直に見せるため
- 実装が簡単
- 学習者が「この原子はそこに移る」と理解しやすい

将来的に、必要なら警告表示や「選択原子群が操作で閉じていない」という表示を追加します。

---

### 16.5 軽量表示モード

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

結合表示はMVPでは実装しなくてよいです。

---

## 17. カメラ操作

PyVista標準操作を使います。
VESTA風を目指しますが、最初から完全一致でなくてよいです。

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

## 18. 後回しにする機能

最初は以下を実装しません。

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

## 19. 実装順

### 依頼A: 段階1

まず以下だけを実装してください。

```text
1. PyVista + PyVistaQt で結晶構造ビューアーを作る
2. pymatgen で CIF を読み込む
3. 原子と単位胞を 3D 表示する
4. 基本的なカメラ操作を使えるようにする
5. 簡単な UI を作る
   - Open CIF
   - Show atoms
   - Show unit cell
   - Reset View
```

この段階では spglib 解析は不要です。

---

### 依頼B: 段階2

段階1が動いた後、以下を実装してください。

```text
1. Analyze Symmetry ボタンで spglib 解析を実行
2. 対称操作リストを表示する
3. 操作を分類する
4. 操作を選ぶと、対応する軸・面・中心を3D表示する
5. 鏡映面・回転軸・反転中心の重複を解消する
6. Playボタンでアニメーションする
7. Selected atoms / All atoms モードを切り替える
8. 周期境界の最近接像処理を入れる
9. 回転は円弧補間、それ以外は線形補間する
```

---

## 20. 受け入れ条件

### 段階1の受け入れ条件

- CIFを開ける
- 原子が3D表示される
- 単位胞が線で表示される
- マウスで回転・ズーム・平行移動できる
- Reset View が動く
- Show atoms / Show unit cell の表示切替ができる

### 段階2の受け入れ条件

- Analyze Symmetry を押すと spglib 解析が走る
- 空間群・点群・対称操作数が取得できる
- 操作リストが表示される
- 操作を選ぶと軸・面・中心が表示される
- 重複した軸・面・中心が統合される
- Selected atoms mode で選択原子が動く
- All atoms mode で全原子が動く
- 周期境界で不自然にワープしにくい
- 回転は円弧で動く
- 鏡映・反転・並進は線形補間で動く
