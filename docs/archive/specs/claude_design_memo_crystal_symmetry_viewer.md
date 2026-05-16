# Claude向け：結晶・分子構造ビューアー＋対称要素ビューアー 設計相談メモ

## 1. 目的

最終的に作りたいものは、結晶構造や分子構造を3Dで表示し、ユーザーが対称性を見つけて学べる「結晶構造パズル」である。

ただし、最初からパズル機能を作るのではなく、次の順番で段階的に開発したい。

1. 構造ビューアー
2. 対称要素ビューアー
3. パズル機能

現時点で相談したい主対象は、**構造ビューアー** と **対称要素ビューアー** の設計である。

---

## 2. 想定している技術構成

現在の想定は以下。

- `pymatgen`
  - CIFなどの構造ファイル読み込み
  - 結晶構造データ管理
- `spglib`
  - 結晶の空間群対称操作 `W, t` の取得
  - 空間群・点群・Wyckoff位置・等価原子の取得
- 自作コード
  - `W, t` から回転軸・らせん軸・鏡映面・映進面・反転中心を計算
  - 原子対応やアニメーションを管理
- `PyVista`
  - 3D描画
  - 原子、単位胞、対称軸、対称面、反転中心の表示
- `PyVistaQt` / `PyQt` / `PySide`
  - 将来的なGUI化
  - 最初は簡単なUIでよい

大きな役割分担は次のように考えている。

```text
pymatgen:
  元構造データを作る

spglib:
  結晶の対称操作 W, t を求める

自作コード:
  W, t から軸・面・中心を求める
  原子対応やアニメーションを管理する

PyVista:
  3D描画とアニメーション表示を行う
```

---

## 3. 結晶モードと分子モード

将来的に、結晶だけでなく分子にも対応したい。

そのため、最初から以下の2モードを想定したい。

```text
Crystal mode:
  周期境界あり
  格子あり
  分率座標あり
  spglibを使う

Molecule mode:
  周期境界なし
  格子なし
  基本的に直交座標のみ
  分子点群解析を使う
```

ただし、最初の実装は結晶モードを優先してよい。

相談したい点：

- 分子モードと結晶モードをどこまで共通化できるか
- どこから先は明確に分けるべきか
- 最初から分子モードを意識した設計にすべきか
- それともまず結晶モードだけを安定させるべきか

---

## 4. 共通化できそうな部分

### 4.1 原子表示

原子はどちらも3D空間上の球として表示する。

描画側では、結晶か分子かを意識せず、直交座標だけを扱う設計にしたい。

```python
@dataclass
class RenderAtom:
    index: int
    element: str
    atomic_number: int
    cart: np.ndarray
    frac: np.ndarray | None = None
    selected: bool = False
```

分子モードでは `frac = None` でよい。

### 4.2 対称要素の描画

描画用の対称要素は、結晶・分子で共通にしたい。

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

PyVista側はこれらだけを見て描画する。

### 4.3 アニメーション

アニメーション処理は共通化したい。

基本形は以下。

```text
start_positions_cart
target_positions_cart
frame_parameter s = 0 ... 1
interpolated_positions = (1-s) * start + s * target
```

ただし、回転操作については後で軸まわりの円弧補間に改良したい。

---

## 5. 分けて設計すべき部分

### 5.1 座標系

結晶モードでは、解析用に分率座標、描画用に直交座標を使う。

```text
結晶:
  解析: frac
  描画: cart

分子:
  解析: cart
  描画: cart
```

結晶の座標変換は以下。

```python
cart = frac @ lattice
```

軸方向は、

```python
direction_cart = direction_frac @ lattice
```

でよいと考えている。

ただし、面の法線は斜交格子では注意が必要。面の法線を描画するときは、`normal_frac @ lattice` をそのまま使うより、面内基底を直交座標に変換して外積を取る方が安全だと考えている。

```python
v1_cart = basis_frac[:, 0] @ lattice
v2_cart = basis_frac[:, 1] @ lattice
normal_cart = np.cross(v1_cart, v2_cart)
```

### 5.2 周期境界

結晶モードでは周期境界を考慮する。

```text
frac と frac + integer vector は同じ位置
```

分子モードでは周期境界はない。

ここは完全に別設計にする必要があると思っている。

### 5.3 対称性解析

#### 結晶モード

```text
pymatgen Structure
↓
spglib cell = (lattice, positions, numbers)
↓
spglib.get_symmetry_dataset()
↓
W, t を取得
↓
自作コードで軸・面・中心を計算
```

spglibの対称操作は以下。

```text
frac' = W frac + t
```

#### 分子モード

spglibは基本的に使わない。

候補としては以下。

- `pymatgen.symmetry.analyzer.PointGroupAnalyzer`
- 必要なら後で自作の分子対称性解析

最初は分子モードの対称性解析は後回しでもよいと考えている。

---

## 6. 対称要素の求め方

spglibが返す各操作は、

```text
frac' = W frac + t
```

で表される。

### 6.1 回転軸・らせん軸

軸方向は、固有値 `1` の固有ベクトルとして求める。

```text
W v = v
(W - I) v = 0
```

軸上の点は、

```text
W x + t = x + a v + n
```

を解く。

整理すると、

```text
(I - W) x + a v = t + n
```

ここで `n` は整数格子並進。

### 6.2 鏡映面・映進面

面内方向は固有値 `1` の固有ベクトル空間。

```text
W v = v
```

面の法線方向は固有値 `-1` の固有ベクトル。

```text
W n = -n
```

面上の点は、

```text
W x + t = x + V a + n
```

から求める。

### 6.3 反転中心

反転は、

```text
W = -I
```

の場合。

反転中心は、

```text
x = W x + t
```

つまり、

```text
(I - W)x = t + n
```

を解くことで求める。

---

## 7. アニメーション仕様

### 7.1 アニメーション対象モード

2つ用意したい。

```text
Selected atoms mode:
  ユーザーが選択した原子だけ動かす

All atoms mode:
  全原子を動かす
```

### 7.2 複数原子選択

代表原子だけ動かすモードでは、ユーザーが複数原子を選択できるようにしたい。

内部的には以下のように管理する。

```python
selected_atom_indices: set[int]
```

最初のUIでは、3Dクリック選択が難しければ、左パネルの原子リストから選択する方式でよい。

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

Clear Selection:
  選択解除
```

### 7.3 結晶での周期境界処理

アニメーション中に毎フレーム `frac % 1` をすると、原子が単位胞境界でワープして見える。

そのため、アニメーション時には最近接周期像を選ぶ。

手順:

```text
1. 操作後の target_frac を計算
2. target_frac + [i, j, k] の候補を作る
3. start_frac から直交距離が最も短い候補を選ぶ
4. その unwrapped target に向かってアニメーションする
5. 必要なら最後だけ wrapped_frac = target % 1 に戻す
```

関数イメージ:

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

### 7.4 操作ごとのアニメーション

最初はすべて線形補間でよい。

```text
start_cart → target_cart
```

ただし将来的には以下に改良したい。

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

### 7.5 軽量表示モード

アニメーション中は軽量表示にする。

```text
通常表示:
  原子球表示
  単位胞表示
  必要ならラベル

アニメーション中:
  低解像度球または点表示
  結合表示OFF
  ラベルOFF
  選択中の対称要素だけ強調
```

結合表示は後回しにする。

---

## 8. UI仕様

最初のUIは簡単でよい。

### 8.1 左パネル

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

### 8.2 操作リスト

spglib解析後に表示。

```text
Operation 0: identity
Operation 1: screw_3
Operation 2: screw_3
Operation 3: rotation_2
...
```

操作を選択すると、

```text
対応する軸・面・中心を3D上で表示
```

する。

---

## 9. カメラ操作

VESTA風を目指す。

最低限必要な操作:

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

後で追加したい操作:

```text
View along a
View along b
View along c
View along x
View along y
View along z
```

PyVista標準の操作でかなり近いものができるので、最初から完全なVESTA互換にしなくてよい。

---

## 10. 解析実行タイミング

採用したい方式:

```text
ファイル読み込み直後:
  構造だけ表示

Analyze Symmetry ボタン押下:
  spglib解析を実行
  対称操作を取得
  軸・面・中心を計算
  対称要素リストを表示
```

理由:

- 構造表示と対称性解析を分けられる
- エラー原因を切り分けやすい
- 大きな構造で解析が重い場合にも対応しやすい

---

## 11. 候補選択方式

最初のパズル方式は候補選択式でよい。

```text
内部:
  spglibが見つけた対称要素候補を持つ

ユーザー:
  候補リストから選ぶ

判定:
  選んだ候補が未発見なら正解
```

自由入力は後回し。

自由入力では以下が難しいため。

```text
軸の向きの誤差許容
面の位置の誤差許容
周期境界込みの同一判定
等価な回答の同一視
```

---

## 12. 後回しにする機能

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

## 13. 相談したい点

Claudeには、特に以下について意見を聞きたい。

1. 結晶モードと分子モードの切り分けはこの設計で妥当か
2. 共通描画層を `RenderAtom`, `RenderAxis`, `RenderPlane`, `RenderCenter` にする設計は妥当か
3. 結晶では分率座標、描画では直交座標に分ける設計で問題ないか
4. アニメーション時の周期境界処理はこの方法でよいか
5. Selected atoms mode / All atoms mode の設計は妥当か
6. 最初は結合表示を後回しにする方針でよいか
7. 後からパズル化する前提で、今の段階で足りないデータ構造や設計上の注意点はあるか
