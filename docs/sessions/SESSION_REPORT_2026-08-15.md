# Session Report 2026-08-15

このメモは、新しいマシンにクローンして開発を再開したセッションの記録です。コードを書き進めるより先に、
セットアップ経路の穴とテストの偽陽性・偽陰性を潰しました。前回のレポートは`SESSION_REPORT_2026-07-08.md`で、
その後の`a1fe146`（合成・移り先クイズ）と`026b606`（ブラウザテスト）はレポート化されておらず、
経緯は`docs/REVIEW_NOTES.md`に残っています。

## 今回の到達点

- **`identify_generation_operation()`の非決定性を修正**。特殊位置の原子は席対称群のすべての操作で生成されるため
  複数の操作が厳密に一致する。距離の最小値で選んでいたので、勝者を1e-16の丸め誤差が決めていた。
- 結果、spglibのバージョンが上がると答えが変わり、`test_normal_cif_analysis_does_not_reparse_asymmetric_unit_loop`が落ちていた。
- **`scripts/setup.sh`に`npm ci`を追加**。Three.jsは生成物で、無くてもページは開くが構造が一切描画されない。
  この手順は`docs/VIEWER_GUIDE.md`にしか書かれておらず、READMEの最短セットアップから漏れていた。
- ブラウザテスト5件が全滅していたのはこれが原因だった。修正後は6件成功、**452秒 → 52秒**。
- 依存バージョンの検証済みセットを`requirements.txt` / `requirements-dev.txt`に記録した。
- テストは**222件成功**（ブラウザ6件を含む、skip 0）。

## 関連コミット

```text
bfdfad6 fix: make generation operation lookup deterministic; install Three.js in setup
```

## 1. テスト失敗の原因：浮動小数点ノイズがタイブレークを決めていた

Cadmoselite (CdSe, P6_3mc) の Cd は `3m.` の席対称（位数6）を持つ特殊位置にある。
つまり**12個の空間群操作のうち6個が、同じ代表原子を同じ標的原子へ厳密に写す**。
「どの操作で生成されたか」に唯一の正解は無い。

`identify_generation_operation()`は距離の最小値で選んでいた。6候補はすべて数学的に距離0だが、
spglibの並進ベクトルの丸め誤差で差がつく。

```text
op 8: 0.0000e+00   ← spglib 2.7.0 ではこれが勝つ
op 1: 5.5511e-17   ← 以前のspglibではこれが勝っていた
op 3: 2.2204e-16 / op 6: 2.2888e-16 / op 5,10: 2.7756e-16
```

**1e-16の差が勝者を決めていた**ため、spglibを上げると答えが 1 → 8 に反転した。

### 修正

距離比較をやめ、**許容誤差内で最初に一致した操作を採用**する。どの一致も等しく正しく、最小indexは
spglibのリリース間で動かない。同じ脆弱性があった`identify_asymmetric_source()`も揃えた。

- Cadmoselite `[0,8,0,8]` → `[0,1,0,1]`（期待値通り）
- Halite `[0,144,96,48,...]` は不変

`generation_operation_index`はデータ構造を経由してJSON出力されるだけで、パズル判定やアニメーションには
使われていないため、表示・判定への影響は無い。

### テストの意図について

`git show d42edb9`の通り、このテストの本来の意図は「通常CIFで`read_asymmetric_unit_sites()`を
再パースしないこと」の確認で、`generation_operation_index`の値はその副産物のスナップショットだった。
一意に決まらない値を1つの答えに固定していたのが、テストが壊れやすかった理由。

## 2. セットアップの穴：Three.jsが最短経路から漏れていた

READMEの「最短セットアップ」は`scripts/setup.sh` → `scripts/serve.sh --mode puzzle`だが、
`setup.sh`は`npm ci`を実行していなかった。`crystal_viewer/web/node_modules`はgitignore対象の生成物なので、
クローン直後は存在しない。

```text
HTTP 503 /vendor/three/three.module.js
CONSOLE[error]: Three.js module load failed
```

**ページのHTMLは200で返るのでサーバは起動したように見えるが、構造は何も描画されない。**
`npm ci`は`docs/VIEWER_GUIDE.md:205`にのみ記載されていた。

`setup.sh`に追加し、READMEの手動セットアップにも明記した。`node_modules`を削除してから
`setup.sh`を再実行し、復元されることを確認済み。

### npmが無い環境への対応

この環境は`nodejs` 22.22.1 は入っているが`npm`パッケージが無い（Ubuntuでは別パッケージ）。
`corepack`は`/usr/bin/corepack`にあるので、`npm` → `corepack npm@10` の順にフォールバックし、
どちらも無ければ警告して続行する。

## 3. Playwright環境の再利用

`~/.cache/ms-playwright/`（chromium-1234 / 151.0.7922.34、656MB）は**ユーザー単位の共有キャッシュ**で、
このマシンの別プロジェクト（書籍整理ワークベンチ）の`.browser-automation/venv`も同じ場所を使っている。

このプロジェクトの`.venv`に`playwright==1.62.0`を入れるだけで、**ブラウザの再ダウンロードなしに**
同じバイナリを共有できた。バージョンを合わせる必要がある（chromium-1234とペア。
新しいplaywrightだと別のビルド番号を要求してダウンロードが走る）。

WebGLはheadless Chromiumで動作した（`GPU stall due to ReadPixels`の警告は出るが描画は成功）。

## 4. 依存バージョンの記録

ハードピン（`==`）は採らなかった。今日の失敗の根本原因は「操作順序という偶然の性質に依存していたこと」で、
それはコード側で直したため。またPython 3.11環境などで`==`固定は導入を壊す。

代わりに検証済みセットをコメントとして記録し、将来の破損時に比較できるようにした。

```text
Python 3.14.4 / numpy 2.5.2 / pymatgen 2026.5.4 (pymatgen-core 2026.8.13)
spglib 2.7.0 / pyvista 0.48.4 / imageio 2.37.4 / scipy 1.18.0 / vtk 9.6.2
three 0.185.1 / node 22.22.1 / playwright 1.62.0 (chromium-1234)
```

**spglibの操作順序に依存してはいけない**という注意書きも`requirements.txt`に残した。

## 検証

```text
.venv/bin/python -m unittest discover -s tests
Ran 222 tests in 60.003s
OK

node --check crystal_viewer/web/puzzle.js
node --check crystal_viewer/web/three_view.js
```

`rm -rf crystal_viewer/web/node_modules` → `bash scripts/setup.sh` でThree.jsが復元されることを確認。

## 次の方針

セッション中、`docs/PUZZLE_CONCEPT.md`§3.3で「いちばん易しい」とされたレベル1の○×クイズが
未実装であることを次の作業として提案したが、**これは既に見送りが決まっていた**（記録漏れ）。
偽要素の生成則を汎用に作るコストが高く、二択で当てずっぽうが効くため面白くならない、という判断。
同じ提案が繰り返されないよう`PUZZLE_SPEC.md`§0・§6・§7・§10 と `PUZZLE_CONCEPT.md`§3.3・§5 に記録した。

**クイズの追加は4つ（回転軸・操作あて・合成・移り先）で打ち切り、これを完成形とする。**
残るのは機能追加ではなく、完成と報告書に向けた締めの作業。

1. **PyVista/VTKを任意依存へ分離**。web経路は`pyvista`を遅延importしており、
   `pyvista`と`vtk`をimport不能にしても構造読込・render_data・アニメ・パズル出題まで全て動くことを確認済み。
   にもかかわらず`requirements.txt`が`pyvista`を必須にしているため、**vtkが668MB**入る。
   既定インストールをWebのみにし、PyVistaは`requirements-pyvista.txt`等へ分離する。
2. 代表構造で4クイズを通し確認する（§6-6は調整済みだが、最終確認として）。
3. 旧アプローチの整理（`archive/old_gui_attempt` 64KB、`crystal_viewer/legacy` 100KB の扱いを決める）。
4. 報告書の作成。

`docs/REVIEW_NOTES.md`末尾に未対応の所見が1件ある。移り先クイズで青のguessリングと
C2軸の線が近い色になる（形が違うので実用上は区別できる）。

## 次セッションの開始手順

```bash
git status --short --branch
scripts/setup.sh          # venv と node_modules の両方を用意する
.venv/bin/python -m unittest discover -s tests
node --check crystal_viewer/web/puzzle.js
node --check crystal_viewer/web/three_view.js
```

ブラウザテストを走らせる場合:

```bash
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m unittest tests.test_puzzle_browser -v
```

---

# 追記：通し確認と図版取得（同日・後続セッション）

上の「次の方針」の 2 番目、**通し確認と報告書用スクリーンショットの取得**をやった。
機能の追加・変更はしていない。

## やったこと

- `tools/capture_report_figures.py` を新設。headless Chromium で実際のビューアーを操作し、
  4 クイズを人と同じ手順で遊びながら `docs/REPORT_OUTLINE.md` の図表リストを保存する。
- 図版 26 枚 ＋ テスト出力を `docs/figures/` に取得。対応表は `docs/figures/README.md`。
- 残るのはアーキテクチャ図（#1）だけで、これは作図なので TeX 執筆時に作る。

**手で撮らなかった理由**は、UI を直したら撮り直しになるから。スクリプトにしておけば
1 コマンドで撮り直せるし、「通し確認をやった」証拠が実行ログとして残る。

## 通し確認の結果

4 クイズすべてが最後まで通り、未捕捉の JS 例外は 0 件だった。

| クイズ | 構造 | 到達した判定 |
|---|---|---|
| 回転軸 | ベンゼン | 正解 |
| 操作あて（普通） | ベンゼン | `正解（3回回転（C3） または 回映（S3） のいずれも正解）` |
| 操作あて（難しい） | halite | `正解（映進、並進成分 1/4（g(-1/4,1/4,1/2)））` |
| 合成 | ベンゼン | `正解（反転（i））` |
| 移り先 | メタン | 正解 |

報告書に使える収穫が 3 つあった。

1. **「どちらでも正解」が実機で出た**。`PUZZLE_SPEC` で決めた「見分けられない操作は
   除外ではなく統合」が画面上の文言として確認できた。§I-5 の実例に使える。
2. **正解がクライアントに渡っていない**。`/api/puzzle/*` の出題データに答えは無く、
   取得スクリプトも当てずっぽうで答えるしかなかった。§I-3 の「判定はサーバー側」の裏付け。
3. **クイズ間で状態が漏れない**。難しいモード（らせん・映進の語彙）の直後に合成クイズへ
   移っても選択肢は点操作に戻る。`beginCompositionRound()` が明示的に戻していた。

## 取得スクリプトで引っかかった点

いずれもアプリ側の不具合ではなく、**画面の作りをスクリプトが知らなかった**だけ。
同じところで詰まらないように残す。

- **ベンゼンは既定カメラだと真横**。環が潰れて回転が動いて見えない。「軸方向から見る」で
  正面にしてから 25° 傾けた。図 3 はこの視点。
- **映進矢印が出るのは一般映進 `g` だけ**。`a`/`b`/`c`/`n` は ITC 記号自体が並進成分を
  表すので矢印を描かない。最初の映進を選ぶと矢印の無い図になる。
- **難しいモードは並進成分が必須**。種類だけ選んで回答すると
  「並進成分も選んでください。」が出て判定に進まない（仕様どおり）。
- **遊んでいる最中は「← 戻る」が隠れる**。モードを抜けるにはクイズ一覧まで戻る必要がある
  （誤って抜けないための作り）。
- **移り先クイズをベンゼンでやると当たらない**。答えは 12 原子のクリックで、
  当てずっぽうでは 40 ラウンドでも正解に届かなかった。メタン（5 原子）に変えて 8 回目で正解。

## 検証

```text
.venv/bin/python -m unittest discover -s tests
Ran 222 tests in 60.321s
OK
```

図版取得の実行ログは `docs/figures/walkthrough.log`。

## 次の作業

`docs/REPORT_OUTLINE.md`「残作業」の 3 番（旧コード整理）以降。

---

# 追記：収録物質の見直しと残バグ修正（同日・後続セッション）

報告書の執筆を後ろ倒しにして、**収録物質の入れ替え**と**記録済みの残バグ**を先に片付けた。

## 1. 収録物質はテスト都合の選定だった

`examples/cif/` の 32 件は「32 の結晶類を 1 件ずつ」という**テストのための**選定で、
128 原子の `C12H14N4`、64 原子 P1 の `Babefphite`、`Ho2Rh12As7`、`Pharmacosiderite` のように
**原子数が多いか馴染みのない物質**が並んでいた。対称操作を動かして学ぶ教材としては不適。

パズル側は `puzzle.js` にハードコードした 12 件の許可リストでしのいでいたが、
解析モードでは 32 件すべてが出ていた。

### 入れ替えた内容

**結晶 15 件**: 岩塩・CsCl・銅(fcc)・α鉄(bcc)・Mg(hcp)・ダイヤモンド・黒鉛・閃亜鉛鉱・
ウルツ鉱・蛍石・ルチル・ペロブスカイト・α石英・黄鉄鉱・BaTiO3。
らせん・映進を含むもの（ダイヤモンド 66 問、ルチル、石英の 3₁）を意識して選んだ。

**分子 19 件**: 既存 11 件に C1・C2・Cs・Ci・C2h・C4v・D3d・三方両錐の D3h を追加。
点群の穴を埋めつつ、教科書に出る分子から選んでいる。

### 生成にした理由

`tools/generate_example_structures.py` に空間群・格子定数・Wyckoff 位置・**出典**を表として書き、
`Structure.from_spacegroup` → `CifWriter` で書き出す。ダウンロードした CIF を集めるのに比べて:

- 素性が追える（どの文献のどの値か、コードを見れば分かる）
- 実験由来の余計なもの（温度因子・部分占有）が入らない
- 生成後に**空間群番号・記号・原子数・組成を読み直して照合**するので転記ミスが落ちる

実際、この照合が 2 件の誤りを捕まえた。ダイヤモンドの 8a を (1/8,1/8,1/8) に置くと
pymatgen の Fd-3m 設定では 16 原子になり、α石英を P3_221 + (0.4697,0,1/3) にすると
12 原子・組成 SiO になる。どちらも書いた本人には気づけない。

### 分子は「緩い許容誤差で過剰対称化する」

`PointGroupAnalyzer` の許容誤差は 0.3 Å と緩い。trans-ジクロロエチレンの幾何を
作り損ねたとき、**C2h ではなく D2h と報告された**。手書き XYZ が黙って上位の点群に
化ける経路なので、検証は 0.3 Å（アプリの既定）と 0.05 Å の**両方で同じ点群**を要求している。

### 旧 32 件は捨てずに `tests/fixtures/cif/` へ

このセットだけが 32 結晶類すべてを踏むので、捨てると点群カバレッジを失う。
`tests/test_fixture_cif_coverage.py` が全 30 件を解析して
(空間群番号, 記号, 結晶類, 原子数) を照合する。残る 2 類（m-3m と 3m）は教材側に残した
Halite と BaTiO3 が担当し、テストがその対応も検証する。**眠っていたファイルが回帰テストになった。**

`Halite.cif` と `BaTiO3.cif` を残したのは教材価値だけでなく:

- `Halite.cif` は `generation_operation_index` の実値列をテストが固定している
- `BaTiO3.cif` は**同梱で唯一 `_symmetry_equiv_pos_as_xyz` ループが空**で、
  菱面体フォールバック経路を実データで踏む唯一のサンプル

再生成すると両方失うので `PROTECTED` で守った。

## 2. 選別のハードコードをカタログへ集約した

散らばっていた 3 つを消した。

| 消したもの | 場所 | 置き換え |
|---|---|---|
| パズル許可リスト（12 件の Set） | `puzzle.js:40-53` | カタログの `puzzle_counts` |
| 分子式テーブル（11 件） | `puzzle.js:139-151` | 解析層が出す `display_formula` |
| 「移り先＝分子のみ／難しい＝結晶のみ」 | `puzzle.js:227-241` | 同じく `puzzle_counts` から導出 |

`tools/regenerate_example_assets.py` がエクスポート時に 4 つの出題モジュールを実際に走らせ、
構造ごとの問題数を `examples/example_catalog.json` に記録する（全 34 構造で 0.2 秒）。
ピッカーは 0 の組合せを出さない。

**副産物として `REVIEW_NOTES` #5（出題ゼロ構造）が構造的に解消した。** 水の合成クイズや
HCl の移り先で「問題がありません」に到達する経路が無くなった。分子は必ず
`operation_hard` が 0、結晶は必ず `mapping` が 0 なので、種別の制限も同じ仕組みで表現できる。

`display_formula` は `Composition.iupac_formula` から空白と `1` を落として作る。
簡約式では benzene が `HC`、Hill 式では ammonia が `H3N` になる。11 件すべてで
手書きテーブルと一致することを確認してから消した。

## 3. 残バグ 4 件

- **移り先クイズの色**: guess リングが `0x3d9be9`、対称軸が `0x38bdf8` で**色相差 9°**。
  ピンク `0xf472b6`（色相差 130°）へ。**RGB 距離で測ると失敗する**ことに途中で気づいた。
  緑のリング(`0x35c46a`)と空色の軸はチャンネル差が小さいのに混同しない。
  静的テストは色相距離で 40° 以上を要求する。
- **ブラウザ E2E**: 回転軸・操作あて（普通/難しい）を追加して 6 件 → 8 件。
  ピッカーが出す構造の集合とカタログの問題数が一致することも実機で検証する。
  難しいモードの追加で `answer_operation_quiz()` の穴が見つかった（並進成分を選んでおらず、
  「並進成分も選んでください。」で判定に進まない）。
- **`operation_fixed_atom_indices` のベクトル化**: 原子ごとのループ → 一括の行列積。
  halite 全操作で 6.2ms → 2.0ms、結果は一致。
- **死んだ GIF 保存ゲート**: `syncGifSavingControls()` は**どこからも呼ばれておらず**、
  `isGifSaving()` は "writing " 状態を誰も書かないため常に false だった。
  対応する `.saving-gif` の CSS ごと削除。
- **WebM のファイル名**: `animationOperationIndex` はパス未ロード時 null なので、
  録画が毎回 `symmetry-op0.webm` になっていた。選択中の操作と構造名から作るようにした。
- **操作リストの再描画ガード**: 1 秒ポーリングと postState のたびに無条件で作り直していた。
  署名が同じなら何もしない。**署名には構造の識別（json_path とリロード ID）を必ず含める**
  ——操作 index の並びは別の構造でも一致しうるので、それだけでは古い行が残る。

## 検証

```text
.venv/bin/python -m unittest discover -s tests
Ran 238 tests in 72.860s
OK

node --test tests/js/*.mjs        # 10 pass
.venv/bin/python tools/generate_example_structures.py --check-only
```

## 次の作業

1. **図版の撮り直し**（収録構造とピッカーのラベルが変わったので `docs/figures/` は古い）
2. 報告書の執筆

## 4. 図版の撮り直しで見つかった 2 件

図版を撮り直したら通し確認スクリプトが落ちた。**どちらもこの作業で作り込んだ不具合ではなく、
以前から存在していて誰も踏んでいなかったもの**。

### (a) パズルを遊んだ後、解析モードで例題を開けない

`scripts/serve.sh --mode puzzle` で起動 → クイズを遊ぶ → 戻る → 解析モード →
例題を選んで Open。**何も起きない。** 前の構造が残ったままで、エラーも出ない。

原因は 2 つのクライアントが**別々の数列でリクエスト ID を発行していた**こと。

```text
puzzle.js      request_id: Date.now()        -> 1.76e12
browser_ui.js  request_id: ++importRequestId -> 1, 2, 3, ...
server         load_request_id = max(stored, incoming)
               load_request_is_current(id) := (id == load_request_id)
```

サーバーの `max()` は「後から来た読み込みが勝つ」ための正しい設計。壊れていたのは
クライアント側で、パズルが一度 `Date.now()` を送ると、以後の解析モードの ID は
**必ず** それより小さく、`{"ok": false, "stale": true}` で捨てられ続ける。

`beginImport()` を `Math.max(Date.now(), importRequestId + 1)` に変えて、両クライアントを
同じ時計に乗せた。回帰テストは実際の経路（クイズを遊ぶ → 戻る → 解析 → 例題を開く）を
ブラウザで踏む。修正を戻すとこのテストは落ちる（確認済み）。

### (b) 図版取得スクリプトが「静かに間違った構造」を撮っていた

`open_example()` は `.operation-row` が現れるのを待っていたが、**この行は前の構造のものが
残っている**ので何も保証しない。(a) の影響で読み込みが捨てられていても、スクリプトは
気づかずに撮り続けていた。実際、ベンゼンのつもりでメタンの操作一覧を撮っていた
（`kinds=['identity','improper_4','mirror','rotation_2','rotation_3']` = Td）。

`/api/state` の `json_path` が期待した構造になるまで待つようにした。**図版取得は通し確認を
兼ねているので、確認が確認になっていなかったのが一番の問題。**

### ついでに直した再描画ガードの落とし穴

操作リストの再描画ガードを入れたとき、署名を「操作 index の並び」だけで作ったところ、
**ベンゼンとメタンはどちらも 24 操作で index 0〜23** のため署名が衝突し、前の構造の行が
残った。`operations` と `state` は別のレスポンスで更新されるので、
「新しい json_path ＋ 古い operations」という瞬間が実在する。署名には**行に表示する記号**を
含めないといけない。

## 最終確認

```text
.venv/bin/python -m unittest discover -s tests
Ran 239 tests in 75.6s
OK

node --test tests/js/*.mjs                              # 10 pass
.venv/bin/python tools/generate_example_structures.py --check-only
Verified 13 crystal and 8 molecule examples.
.venv/bin/python tools/capture_report_figures.py        # 26 枚、JS 例外 0 件
```

## 次の作業

報告書の執筆（`docs/REPORT_OUTLINE.md`）。アーキテクチャ図はその中で作る。
