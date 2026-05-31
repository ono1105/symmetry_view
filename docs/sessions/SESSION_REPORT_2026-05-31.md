# Session Report 2026-05-31

このメモは、2026-05-22 のセッションレポート以降に進んだ開発内容を、後から報告書や引き継ぎ資料へまとめやすくするための記録です。

前回までの流れでは、PyVista ベースのビューアー、ブラウザ操作パネル、対称操作アニメーション、glyph 表示の検討、screw symbol 表示修正までが主な内容だった。  
今回の範囲では、CIF 読み込みの安定化、セル設定変換、Bravais cell 表示、グライド・並進・ITC 風表記、PyVista 表示上の補助線、レビューで見つかった効率・保守性の改善を進めた。

## 目的

この期間の目的は、将来的な「対称操作を使ったパズル」の前段階として、対称操作ビューアーの信頼性と説明力を上げることだった。

特に重要だったテーマは以下。

1. ReciPro 由来の菱面体晶 CIF が読み込めない問題を直す
2. primitive / conventional / refined などのセル設定変換をブラウザから使えるようにする
3. Bravais cell 変換後も対称操作アニメーションが正しく見えるようにする
4. glide / screw / translation の方向と表記を分かりやすくする
5. ITC 風表記モードを追加し、標準表示とは別モードとして扱う
6. Claude レビューで指摘された効率・競合・重複実装を小さいものから修正する
7. 今後 Web 上で描画する方針を踏まえ、PyVista 固有の描画高速化は優先度を下げる

## 現在の状態

2026-05-31 時点で、最新コミットは以下。

```text
3f46764 Add ITC-style operation notation and fix several viewer bugs
```

`.claude/` と `exports/gifs/` は別作業・ローカル出力なので、通常のレビュー対象外として扱う。

現在、未追跡ファイルとして以下のテストが残っている。

```text
tests/test_atom_mapping.py
tests/test_structure_analysis.py
```

これらは、spglib の `equivalent_atoms` を使った非対称単位代表の生成と、atom mapping の回帰確認のために追加したテストである。`unittest discover` では拾われ、通過している。

検証状況:

```text
.venv/bin/python -m unittest discover -s tests
Ran 54 tests ... OK
```

また、主要 Python ファイルの `py_compile` と `git diff --check` も通過している。

## 菱面体晶 CIF 読み込みエラー

### 発生したエラー

`BaTiO3.cif`, `Calcite.cif`, `Ice II.cif` など、ReciPro から出力された一部 CIF を開くと、pymatgen の CIF parser がクラッシュした。

原因は、CIF 内に以下のような空の symmetry operation loop が含まれていたことだった。

```text
loop_
_symmetry_equiv_pos_as_xyz
loop_
_atom_site_label
...
```

ヘッダーだけがあり、対称操作のデータ行がない。この形式を pymatgen が処理できず、ゼロ除算や parse error になる場合があった。

### 単純な修正が危険だった理由

最初に考えられる対応は、空ループを削除して pymatgen に任せることだった。  
しかし、BaTiO3 のような rhombohedral primitive cell では、この方法だと pymatgen が空間群番号だけを見て hexagonal setting の操作で展開し、原子数が不自然に増える。

例:

```text
BaTiO3: 5 atoms expected
単純に pymatgen 任せ: 39 atoms になるケースがある
```

このため、CIF の空間群番号を無条件に信用して一般展開するのではなく、限定的な fallback が必要だった。

### 修正内容

`structure_analysis.py` に、菱面体 primitive cell かどうかを判定する fallback を追加した。

主な処理:

- 空の `_symmetry_equiv_pos_as_xyz` / `_space_group_symop_operation_xyz` loop を検出
- 格子定数から rhombohedral primitive cell と判断できる場合だけ fallback する
- 対象空間群番号を限定する
- R-setting 用の操作だけを補完して atom_site を展開する
- 最終的な空間群判定は、補完後の原子配置を spglib に渡して決める

対象として扱った R 系 fallback 操作は以下。

```text
146, 148, 155, 160, 161, 166, 167
```

重要な設計判断:

- CIF の空間群番号は fallback で atom_site を展開するためだけに使う
- 最終報告する空間群は必ず spglib が原子配置から決める
- non-rhombohedral の空ループは黙って修復しない

### 検証

`tests/test_rhombohedral_cif_fallback.py` を追加・拡張し、以下を確認した。

- rhombohedral primitive cell + empty symmetry loop は warning 付きで修復される
- normal CIF は fallback に入らない
- non-rhombohedral empty loop は黙って修復しない
- pymatgen `SpaceGroup.from_int_number(...).symmetry_ops` は現在の R-setting fallback と操作数が違うため、そのまま置換してはいけない

代表例:

```text
BaTiO3.cif -> 5 atoms, spglib detects No.160 R3m
```

## セル設定変換

### 背景

ユーザーが primitive cell と Bravais / conventional cell を切り替えて対称操作を見たい、という要望があった。  
特に BaTiO3 のような rhombohedral primitive cell を conventional / hexagonal setting に変換し、ITC の表と見比べたいという用途があった。

### 実装内容

`crystal_viewer/viewer/cell_settings.py` を追加・拡張し、pymatgen の `SpacegroupAnalyzer` を使って以下のセル設定へ変換できるようにした。

```text
native
primitive
conventional
refined
```

ブラウザ UI には Cell basis / Cell setting の選択を追加し、`tools/view_json_server.py` の `/api/cell_setting` から変換できるようにした。

変換後は単なる座標変換ではなく、変換後の構造を再度 `analyze_structure()` にかける。  
これにより、変換後セルに対応する `operations`, `axes`, `planes`, `centers`, `atom_mappings` を作り直す。

### 発生した問題

当初、セル設定変換を HTTP handler 内で直接実行していた。  
この場合、重い構造で `analyze_structure()` や legacy core が詰まると、HTTP レスポンスが返らずブラウザ側が待ち続ける可能性があった。

また、ファイル読み込み中に cell setting 変更を押すと、古い session の payload に対して変換が走り、新しい session を上書きする競合の可能性があった。

### 修正内容

`tools/export_cell_setting_json.py` を追加し、セル設定変換をサブプロセスで実行するようにした。

サーバー側では以下を行う。

- `export_cell_setting_json_worker(..., timeout_sec=analysis_timeout_sec)` で変換
- `import_in_progress` 中は cell setting 変更を拒否
- 変換完了後に再度 lock を取り、session が変わっていないか確認
- `native` へ戻す場合は `base_payload` を使う
- primitive/conventional などへ切り替える場合は現在の payload を元に変換する

### 検証

`tests/test_cell_settings.py` と `tests/test_view_json_server.py` で以下を確認した。

- BaTiO3 を conventional cell に変換できる
- Halite の primitive / conventional 往復ができる
- distinct でない primitive/conventional 変換は `require_distinct` で拒否できる
- native path でも `display_atom_count` / `display_lattice_parameters` が metadata に入る
- worker 経由でタイムアウト付き変換が動く

## Bravais cell 変換後の screw animation 修正

### 発生した問題

BaTiO3 を Bravais / conventional cell に変換して対称操作アニメーションを確認したところ、op7 の 3 回螺旋で、並進方向が軸に平行に見えない問題があった。

これは、周期境界の等価な終点を選ぶときに、回転軸方向を保つ周期シフトではなく、単に近い像が選ばれるケースがあったためである。

### 修正内容

`animation_context.py` に、回転・らせん軸については軸方向を保つ periodic shift を選ぶ処理を追加した。

主な考え方:

- screw / rotation では、操作後の代表原子の移動を軸に沿う成分として解釈する必要がある
- 周期像の選択時に、軸に平行な並進成分になる候補を優先する
- `symmetry_element_shared_shift()` で rotation / screw axis 向けの shift 選択を補正する

### 検証

`tests/test_cell_settings.py` に、BaTiO3 conventional cell の screw animation translation が軸方向と一致することを確認するテストを追加した。

## Glide 表記の問題

### 発生した問題

最初の課題は、glide 操作のラベルが単に `g` と出るだけで、a glide / b glide / c glide / n glide / d glide のどれなのか分からないことだった。

確認中に以下の問題が見つかった。

- Cadmoselite.cif, No.186 には c glide があるはずだが `g` と表示されていた
- Halite.cif, No.225 には n glide があるはずだが `g` と表示されていた
- BaTiO3 R3m を hexagonal conventional cell で見ると、ITC では `g` と書かれる操作を、最初の分類コードが `c` と誤判定した

### なぜ誤判定が起きたか

最初の分類では、glide plane 上の点を実際に操作して得られる面内移動ベクトルから、1/2 成分や 1/4 成分を見て a/b/c/n/d を推定していた。

しかし、R lattice や centering translation を含む操作では、同じ `(W,t)` 操作でも代表面や周期像の選び方により、見える glide vector が変わる。  
そのため、単純に幾何的に短いベクトルを選ぶと、ITC 表の `g` と一致しない場合があった。

### 修正方針

標準表示では、無理にすべてを a/b/c/n/d に分類しないことにした。

現在の標準表示の方針:

- 明確に 1/2 成分が 1 軸だけなら a/b/c
- 1/2 成分が複数なら n
- 1/4 成分が複数なら d
- それ以外は `g` のまま
- `g` の場合は、どの方向に映進するか分かるように `; glide (...)` を追加

さらに、`planes[0]` だけで分類すると代表面によって誤判定する可能性があるため、候補面を見て最短の妥当な代表を選ぶ方式にした。

### 具体例

確認した代表例:

```text
Cadmoselite: glide symbols -> {"c"}
Halite: n glide を含む
BaTiO3 conventional R3m: generic g のまま
```

### 検証

`tests/test_operation_labels.py` を追加・拡張し、以下を確認した。

- Cadmoselite の glide は c と表示される
- Halite の glide に n が含まれる
- BaTiO3 R lattice の glide は generic g のまま
- generic g の標準 summary には glide vector が含まれる

## PyVista 上の glide direction 表示

### 要望

glide 操作について、鏡映後にどの方向へ並進するかを PyVista 上でも分かるようにしたい、という要望があった。

最初は矢印で表示したが、視覚的に主張が強すぎた。  
その後、矢印ではなく、映進面の中心を通って glide vector に平行な控えめな直線を表示する方針に変えた。

### 発生した問題

Halite の op75 などで、表示した glide vector とアニメーション中の並進方向が逆または別方向に見えるケースがあった。

原因は、glide vector には周期的に等価な候補が複数あり、ラベル用・表示用・アニメーション用で別の代表を選んでいたためである。

### 修正内容

`viewer/glide_geometry.py` を追加し、glide vector の共通計算をまとめた。

主な変更:

- `glide_translation_frac()` を共通化
- `centered_fractional_vector()` を共通化
- `periodic_shift_vectors()` を `geometry.periodic_shifts()` の互換ラッパーに変更
- PyVista の glide direction line は、アニメーションの shared translation に最も向きが合う周期像へ合わせる
- line length は回転軸と同程度に延長
- 線は `#f7dc6f`, `line_width=3`, `opacity=0.55` の控えめな表示

### 検証

`tests/test_operation_labels.py` に以下を追加した。

- Cadmoselite の glide direction vector が centered periodic image を使う
- Halite op75 の glide direction line が animation translation direction と同じ向きになる

## 並進操作の表示

### 背景

R3m の ITC 表では、centering translation が `t(2/3,1/3,1/3)` のように表示される。  
一方で、従来の表示では生成元や操作リストで `g(2/3,1/3,1/3), C3` のように見え、ITC の `t, 3+, m` とは違って見えた。

議論の結果、生成元は一意でなく、「群を生成できる集合」であって ITC の選ぶ生成元と同じである必要はない、と整理した。

### 修正内容

標準 summary では純粋並進操作を分率ベクトルで表示するようにした。  
ITC-like では `t|(2/3,1/3,1/3)` のような表記を出す。

重要な点:

- `translation_frac` は spglib が返す raw な t 値をそのまま使う
- `centered_fractional_vector()` で `-1/3` などへ寄せない
- ITC の centering translation 表記に合わせるため

## ITC-like 表記モード

### 背景

ユーザーは、ITC の symmetry operation 一覧のように、各操作について「どこの面・軸・中心で、どの並進成分を持つか」を簡潔に見たいという要望を持っていた。

ただし、完全に ITC と一致させるには、空間群番号・setting・origin choice ごとの ITC 操作表データベースと、spglib の `(W,t)` との照合が必要になる。  
これはパズル用途のサブ目的である対称操作ビューアーとしては過剰であるため、まずは「ITC-like approximation」として別モードにした。

### 実装方針

標準表示は従来どおり残し、ブラウザ UI に Notation 選択を追加した。

```text
standard
ITC-like
```

ITC-like では、`operation_itc_like_summary()` が以下のような文字列を出す。

```text
t|(2/3,1/3,1/3)
m x, y, 0
c(0,0,1/2) x, x, z
g(1/6,-1/6,1/3) x+1/2, -x, z
```

### 実装内容

`operation_labels.py` に ITC 風の位置表現生成を追加した。

主な関数:

- `_itc_t_intrinsic(W, t, order)`
- `_itc_null_space(A)`
- `_itc_rationalize(v)`
- `_itc_param_names(null_vecs)`
- `_itc_coord_str(const, terms)`
- `_itc_normalize(x0, null_vecs)`
- `operation_itc_position(operation)`
- `operation_itc_like_summary(...)`

基本式は以下。

```text
t_int = (1/n) * Σ W^k t
(W - I) x = -(t - t_int)
```

これにより、操作の固定集合をパラメトリックに表し、自由変数を `x, y, z` として割り当てる。

### 既知の限界

ITC-like は、完全 ITC 一致ではない。

既知の限界:

- null space basis が複数ある場合、ITC と異なる等価表現を選ぶ可能性がある
- `2x, -x, z` のような複雑な自由変数で、オフセット正規化が ITC とずれる可能性がある
- 空間群ごとの origin choice や conventional setting を完全には照合していない

そのため、UI には「ITC-like notation is a readable approximation; exact ITC row matching is not guaranteed.」という注意を出す。

### 検証例

代表例では以下を確認した。

```text
BaTiO3 R3m glide:
g(1/6,-1/6,1/3) x+1/2, -x, z

Cadmoselite c glide:
c(0,0,1/2) x, x, z

Halite n glide:
n(1/2,1/2,0) x, y, 0
```

`tests/test_operation_labels.py` では、BaTiO3 の ITC-like summary が読みやすい面・glide vector を持つことを固定している。

## PyVista orientation axes と current-view 3-view GIF

### orientation axes

Bravais / conventional cell に変換したあと、PyVista 左下の orientation widget が world XYZ の向きのままに見える問題があった。

これを修正するため、`scene_rendering.add_orientation_axes()` が `unit_cell` dict を受け取った場合、vtkAxesActor に格子ベクトル方向の transform を適用するようにした。

これにより、orientation widget の a/b/c が、実際の格子ベクトル方向を指すようになった。

確認:

```text
PyVista offscreen で add_orientation_axes(..., unit_cell=...) が例外なく動作
```

### current-view 3-view GIF

通常の 3-view GIF は、操作の軸・面に基づく正面・右・上方向を保存する。  
追加で、現在のカメラ方向を front として、そこから right / top を作る `Save 3-view GIFs (current view)` を追加した。

追加内容:

- `gif_3view_current_request_id` を render state に追加
- ブラウザ UI にボタン追加
- `BrowserControlledViewer.save_three_view_gifs_from_current_view()` を追加
- 現在カメラの position / focal point / view up から front/right/top を計算

## 照明・背景・凡例まわり

5月下旬には、見た目の調整も進めた。

主な変更:

- VESTA 風の atom color に変更
- 背景を dark / white で切り替え可能にした
- camera-relative lighting を追加
- atom legend を初期非表示にした
- legend 表示が false のときに実際に actor を削除するよう修正
- F と N の色が同じだった問題を修正

これらは主に視認性向上と、教材・パズル用途で見やすい画面を作るための変更である。

## spglib / pymatgen 活用と解析効率

### asymmetric unit の再パース削減

以前は、通常 CIF の読み込みで以下の二重処理があった。

1. `Structure.from_file()` が内部で CIF を parse
2. `read_asymmetric_unit_sites()` が再度 `CifParser` で CIF を parse

これは I/O と parse の無駄だった。

spglib の dataset には `equivalent_atoms` が含まれているため、通常 CIF ではこれを使って非対称単位代表を作るようにした。

修正内容:

- `analyze_structure()` で `dataset["equivalent_atoms"]` を取得
- `asymmetric_unit_from_equivalent_atoms()` を追加
- 通常 CIF では `read_asymmetric_unit_sites()` を呼ばない
- R 系 fallback のように loader が明示的に `asymmetric_atoms` を返す場合は既存経路を維持
- `generation_operation_index` は代表原子から該当する操作だけ探索する

検証:

- Halite の asymmetric index / generation operation index を固定
- Cadmoselite で `read_asymmetric_unit_sites()` が呼ばれないことを mock で確認

### atom mapping の候補絞り込み

`find_matching_crystal_atom()` は以前、全原子を走査して atomic number が一致するものを探していた。  
KDTree 化も検討したが、`scipy` 依存追加と周期境界込みの検証が必要になるため、まずは影響範囲の小さい改善として atomic number ごとに候補を事前グループ化した。

これにより、同じ atomic number の原子だけを探索するようになった。

検証:

- Halite の identity mapping
- Halite の代表的な face translation mapping
- mapping complete と max_distance

## Review 対応

Claude レビューで指摘された内容のうち、影響範囲が小さいものから対応した。

### glide 表記・セル変換コード

修正済み:

- `glide_translation_frac` を同一 plane に 2 回呼ぶ無駄を削減
- `integer_index_vector` を `geometry.py` に共通化
- cached な周期シフト配列を read-only 化
- `periodic_shift_vectors` / `periodic_shifts` を共通実装へ統一
- `handle_cell_setting` で変換完了後に session 変化を再チェック
- `lattice_inverse()` を lattice 値ベースの `lru_cache` に変更

保留:

- KDTree 化は依存追加と周期境界テストが必要なため、atomic number グループ化までに留めた
- `RHOMBOHEDRAL_SETTING_OPS` の `SpaceGroup.symmetry_ops` 置換は、操作数・setting が違うためそのまま置換しない

### PyVista glyph actor 置き換え

前回までは PyVista 側で glyph actor に置き換える高速化案があった。  
しかし、今後は Web 上で描画する方針になったため、PyVista 固有の actor 最適化は優先度を下げた。

今後 WebGL / Three.js などへ移行する場合は、以下のデータ層だけを流用する方針がよい。

- `display_atom_instances()`
- `element_instance_batches()`
- render_data / atom_mappings / operation summaries

描画最適化そのものは Web backend 側で設計する。

## 検証コマンド

代表的に使った検証コマンド。

```bash
.venv/bin/python -m unittest discover -s tests
```

```bash
.venv/bin/python -m py_compile \
  crystal_viewer/viewer/operation_labels.py \
  crystal_viewer/viewer/pyvista_controller.py \
  crystal_viewer/viewer/scene_rendering.py \
  crystal_viewer/viewer/symmetry_elements.py \
  crystal_viewer/structure_analysis.py \
  crystal_viewer/atom_mapping.py
```

```bash
git diff --check -- . ':!.claude' ':!exports/gifs'
```

```bash
.venv/bin/python - <<'PY'
import pyvista as pv
from crystal_viewer.viewer.scene_rendering import add_orientation_axes
p = pv.Plotter(off_screen=True)
add_orientation_axes(p, unit_cell={'lattice': [[1,0,0],[0,1,0],[0,0,1]]})
print('ok')
p.close()
PY
```

## 代表的な確認結果

```text
Ran 54 tests in 20.414s
OK
```

BaTiO3 / Halite / Cadmoselite の operation summary を直接出力し、標準表示と ITC-like 表示が例外なく生成されることも確認した。

例:

```text
BaTiO3:
m x, y, x
g(1/6,-1/6,1/3) x+1/2, -x, z

Halite:
n(1/2,1/2,0) x, y, 0
a(1/2,0,0) x, 1/4, z

Cadmoselite:
c(0,0,1/2) x, x, z
```

## 残っている課題

### Web描画バックエンド

今後の大きな作業は、PyVista ではなく Web 上で描画する仕組みを作ること。  
このとき、既存の PyVista actor 最適化をそのまま移植するのではなく、WebGL / Three.js などの前提で、以下を整理する必要がある。

- render_data から Web 用 scene data への変換
- atom instance の batching
- operation animation の補間データ
- symmetry element の geometry 表示
- atom selection / hidden / color state
- GIF あるいは動画出力をどう扱うか

### ITC-like 表記の限界

現在の ITC-like 表記は、完全な ITC operation table matching ではない。  
報告書では、以下のように説明するのが安全。

```text
ITC-like mode は、spglib の (W,t) から固定集合と固有並進を計算して、
ITC に近い読みやすい表記を生成する近似モードである。
空間群ごとの ITC 表そのものと照合しているわけではない。
```

将来的に完全一致を目指すなら、以下が必要。

- space group number
- setting
- origin choice
- ITC operation table data
- spglib operation `(W,t)` との対応付け

### R-setting fallback

`RHOMBOHEDRAL_SETTING_OPS` は現時点ではハードコードを維持する。  
pymatgen `SpaceGroup.symmetry_ops` は H setting / centering を含む操作数を返すため、今回の R primitive fallback にはそのまま使えない。

## 次に進めること

ここまでの修正で、対称操作ビューアーとしての基本的な解析・表示・アニメーションはかなり安定した。  
一方で、パズル化を見据えると、まだ以下の作業が残っている。

### Custom operation sequence

次に優先度が高いのは、ユーザーが複数の対称操作を選び、それらを段階的にアニメーションできる仕組みである。

想定している用途は以下。

- グライドした後に回転するなど、複数操作の合成結果がどの既存操作に対応するか確認する
- パズルで、ユーザーが選択した操作から別の操作を作れることを、複数回のアニメーションで示す
- 将来的に、生成元や選択済み操作から対象操作を作れるか自動判定する

最初に作るべきなのは UI ではなく、`(W,t)` の合成を扱う独立したロジックである。  
操作 A の後に操作 B を適用する場合、分数座標では以下で合成できる。

```text
W = W_B @ W_A
t = W_B @ t_A + t_B
```

この `t` を格子並進 modulo 1 で正規化し、既存の operation list の `(W,t)` と照合すれば、合成結果がどの操作に対応するか判定できる。

実装順は以下が安全。

1. 現在の未追跡テストを含めて commit / push するか判断する
2. operation composition 用の純粋ロジックを追加する
3. 合成、照合、単位元、非可換性、translation modulo 1 の単体テストを追加する
4. ブラウザ UI に operation sequence editor を追加する
5. 既存のアニメーション処理を使って、sequence を 1 step ずつ再生できるようにする
6. 選択済み操作から対象操作を作れるかを BFS などで探索する機能を追加する

この順番なら、パズル機能の核になる群演算部分を UI から独立して検証できる。

### 表示仕様の設計メモ

通常表記、ITC-like 表記、glide vector 表示、PyVista 上の glide 補助線の意味を短い設計メモとして固定しておくとよい。

特に ITC-like 表記は完全な ITC table matching ではないため、UI とドキュメントの両方で以下を明記する。

```text
ITC-like mode は、spglib の (W,t) から固定集合と固有並進を計算して、
ITC に近い読みやすい表記を生成する近似モードである。
空間群ごとの ITC 表そのものと照合しているわけではない。
```

### 代表 CIF の回帰確認

これまで実際に問題が出た CIF を、軽い回帰確認セットとして使えるようにしておくとよい。

候補:

- BaTiO3: Bravais cell 変換後の screw / glide / translation 表示
- Halite: n glide と glide vector 表示
- Cadmoselite: c glide 表示
- ReciPro 由来の rhombohedral CIF: 空 loop fallback

最低限確認したいこと:

- 解析が例外なく完了する
- operation count が期待から大きく外れない
- 代表 operation のラベルが壊れない
- atom mapping が成立する

### Web 描画バックエンド

Web 描画へ進む場合、PyVista の actor 最適化をそのまま移植するより、WebGL / Three.js 向けの scene model を先に決める方がよい。

整理対象:

- atom instance / element batch
- symmetry element geometry
- operation transform
- animation path
- selection / hidden / color state
- GIF または動画出力

### 生成元・合成探索

最終的には、ある操作が他の操作の合成で作れるかを求めるプログラムも必要になる。

ただし、完全な数学的最小生成元を最初から求めるより、パズル用途ではまず以下で十分。

- ユーザーが選択済みの操作集合を generator とみなす
- operation list の有限集合上で BFS する
- target operation に一致する最短列を探す
- 見つかった列を sequence animation として再生する

これにより、「この操作はすでに選択した操作から作れる」という説明を視覚的に示せる。

## 次セッションの開始手順

次セッションでは、まず以下を確認する。

```bash
git status --short --branch
git diff --stat -- . ':!.claude' ':!exports/gifs'
.venv/bin/python -m unittest discover -s tests
```

`.claude/` と `exports/gifs/` は別作業・ローカル出力として扱い、通常レビューでは無視してよい。

その後、Web 描画へ進む場合は、PyVista 側の actor 構造ではなく、`render_data` と `atom_mappings` を入力にした Web scene model を先に設計する。
