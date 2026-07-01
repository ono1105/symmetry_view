# Claudeへのレビュー依頼: UIと3D表示の統合方式

## プロジェクトの目的

結晶・分子の対称性を題材にした教育パズルを開発しています。最終的には、中学生でも構造を見ながら対称操作を試し、点群の閉包や操作の合成を直感的に学べるものにしたいです。

現在はパズル実装の前段階として、CIF/XYZを解析し、原子、単位胞、対称軸、鏡映面、反転中心を3D表示し、対称操作をアニメーションするビューアーを開発しています。

## 現在の構成

### Python側

- `spglib` + `pymatgen` + 既存の自作`/home/ken/work/kouzoukaiseki/symmetry_core.py`で解析
- `RenderData` / `AtomMapping`をJSONへexport
- 対称操作の合成、閉包探索、原子対応を実装済み
- 回転、鏡映、反転、らせん、映進、回反などのアニメーション経路生成を実装済み
- PyVistaで原子、対称要素、アニメーションを描画

### ブラウザ側

- `tools/view_json_server.py`がstdlib HTTP APIとUIを配信
- `crystal_viewer/web/browser_ui.py`の単一HTML/JSが操作盤
- CIF/XYZ/JSON/Exampleの読込、操作選択、Start/Stop/Reset、カメラ、Cell Rangeなどを操作
- BeginnerとAdvancedを分離済み

### 現在の問題

- 操作盤はブラウザ、3D表示は別のPyVistaウィンドウで、画面が分離している
- PyVistaQt埋込みはWSL/X11で`BadWindow`が発生したため廃止した経緯がある
- PyVistaではWSL/Mesaの透明描画や深度ソートに制約がある
- 最終的なパズルでは、同じ画面内で3D構造を直接クリック・操作したい

## 現在考えている統合案

### 案A: 計算はPython、描画だけブラウザのVTK.jsへ移す

Pythonに残すもの:

- CIF/XYZ解析
- 対称操作・対称要素計算
- AtomMapping
- 操作の合成と閉包探索
- アニメーション経路の構築

JavaScriptに移すもの:

- 原子、単位胞、軸、面、中心の描画
- カメラ操作とProjection
- Cell Rangeによる周期像の表示
- Pythonが返した経路記述の補間・再生
- マウス選択

Pythonから毎フレームの座標を送るのではなく、次のような描画・経路記述JSONを返し、JavaScript側で補間する想定です。

```json
{
  "type": "rotation",
  "axis_point": [0, 0, 0],
  "axis_direction": [0, 0, 1],
  "angle_deg": 120,
  "atoms": [{"index": 0, "start": [1, 0, 0]}]
}
```

PyVistaは当面、デバッグ、比較、GIF出力用として残します。

### 案B: TrameでPyVistaをブラウザへ埋め込む

既存PyVista描画を活用し、1画面化を早く実現する案です。ただし、サーバー描画、WebSocket、WSL/Mesa依存が残り、最終的な教育パズルの配布・操作性には不安があります。

### 案C: 解析・経路計算も含めてJavaScriptへ移植する

完全なクライアントアプリにできますが、既存の解析・幾何計算の再実装量が大きく、Python版との数値差や機能差が生じるリスクが高いと考えています。

## 現時点の第一候補

案Aです。既存Pythonを計算エンジンとして維持し、ブラウザは描画と入力を担当させます。難しいアニメーション経路計算を二重実装しないため、Python側に共通の「描画・アニメーション記述JSON」を追加し、PyVistaとVTK.jsの両方がそれを利用する構造を考えています。

## Claudeに確認したいこと

1. このプロジェクトでは案Aが最適でしょうか。Trameや別方式の方が適切でしょうか。
2. VTK.jsとThree.jsのどちらが、原子の大量描画、半透明面、軸、周期像、マウス選択、アニメーションに適していますか。
3. PythonとJavaScriptの責務境界はどこに置くべきですか。
4. Pythonが返すアニメーション経路JSONは、どのようなschemaにすると拡張しやすいですか。
5. 回転方向、fractional/Cartesian変換、周期境界、行列の掛け方などで想定される不具合は何ですか。
6. PyVista版との描画・アニメーション一致をどうテストすべきですか。
7. 現在の単一HTML文字列とstdlib HTTP serverを段階的に移行する場合、どの実装順序が安全ですか。
8. 最終的な教育パズルまで考えたとき、今の段階で避けるべき設計上の負債はありますか。

レビューでは、推奨案、理由、段階的な移行手順、主なリスクとテスト戦略を具体的に示してください。

---

## Claude レビュー結果 (2026-07-01)

Codex への申し送り。以下は Claude による回答。実装判断の材料として参照のこと。

### 推奨: 案A（計算=Python / 描画=ブラウザ）

案Aが最適。理由と、既に案Aが8割完成している点が重要。

- 最終目標（原子を直接クリックするパズル・配布）はクライアント描画が必須。案B(Trame)はサーバ描画・WebSocket・WSL/Mesa依存を残し、最終形へ持ち越せない。ただし**開発時のパリティ検証ビューとしては残す価値あり**。
- 案C（全面JS化）は spglib/pymatgen/`symmetry_core.py` の再実装で数値差リスク大。却下。
- **重要**: 案Aの「経路記述JSON」と「参照補間器」は既に実装済み。
  - `crystal_viewer/viewer/animation_path.py` の `build_operation_path()` が経路記述dict（`{"type":"rotation","axis_point",...}`）を生成。
  - 同ファイルの `evaluate_path(path, s)` が参照補間器。JSへ移植する対象はこれ。
  - よって新規作業は「dictのnp配列→listシリアライズ」と「`evaluate_path`のJS移植」に集約される。

### 描画ライブラリ: Three.js を推奨（VTK.jsより）

- 原子大量描画: `InstancedMesh` で周期像込みを1ドローコール化。
- 半透明面(鏡映面): `depthWrite:false`+手動ソートの制御例が豊富で WSL/Mesa の深度問題を回避しやすい。
- 原子クリック: `Raycaster` が instanceId まで返す＝パズルに直結。
- PyVista が VTK だから VTK.js で揃える、という発想は不要（描画記述JSONを挟むので独立）。

### 責務境界

- Python(真実の源): 解析・対称要素・AtomMapping・合成/閉包・各原子の start/target(絶対Cartesian)・経路記述。**frac↔cart変換は全てPythonで確定し、JSにはCartesianだけ渡す**。
- JS(表示と入力): 描画・カメラ・Projection・Cell Range周期像展開・`evaluate_path`相当の補間再生・マウス選択（返すのは選択index）。
- 鉄則: JSに行列意味論（frac/cart, row/column, 掛け順）を持ち込ませない。**本プロジェクトはrow-vector規約**（`x_cart = x_frac @ L`, `matrix_cart = L.T @ W @ (L.T)^-1`）だが、cart空間の適用は列ベクトル左掛け（`animation_path.py` の `W @ start + t`）。この2つを混同しないよう、JSへは「補間済み前提の点」だけ渡す。

### 経路スキーマ（拡張しやすい形）

既存dictを踏襲しつつ以下を追加:
- `type`によるタグ付きユニオンを維持（新操作＝新type追加で後方互換）。
- **角度は必ず度で`angle_deg`に統一**（現dictは`"angle"`でラジアン扱い＝JS移植の事故要因）。
- `sequential`/`segments` は将来の合成操作アニメの拡張点として維持。
- `schema_version` をアニメパスJSONにも付与（export側v6とは別軸で管理）。
- `coordinate_space:"cartesian"` を明示。np→listは `json_export.to_jsonable` を流用。

### 想定不具合（移植時に必ず固定）

1. 回転符号: `signed_angle_to_target` が決めた`angle`をJSで再計算しない（そのまま使う）。
2. frac→cart: JSに渡す前にPythonでcart化して回避。
3. 行列掛け順: cart空間は列ベクトル左掛け（`W @ start + t`）に統一。
4. 周期境界: アニメ対象は元セルのみ、周期像の追従/静止を明示。
5. improper: `s<=0.5`回転/後半反転の2段補間を`evaluate_path`から忠実移植。
6. 軸/法線は非正規化で来る場合があるのでJS側でも`normalize`必須。

### パリティテスト戦略

- `evaluate_path(path, s)` を代表操作×原子×`s∈{0,0.1,…,1}`でサンプルしゴールデンJSON化（`tests/test_animation_path.py`拡張）。
- JS移植版を同じpath/同じsで評価しゴールデンと`atol=1e-6`比較（vitest等）。
- 仕上げにPyVista/Three.jsの最終フレームを数ケース目視比較。

### 段階的移行順序（安全策）

1. API先行: `GET /api/render_data`・`POST /api/path` を追加し、まず既存PyVista UIから叩けることを確認。
2. np→JSONシリアライザ一本化＋スキーマv1確定（パリティテストを先に用意）。
3. `evaluate_path`のJS移植（描画なし・純ロジック）＋ゴールデン通過。
4. 静的表示のみThree.js化（アニメなし）。旧UIと並存・切替フラグで比較。
5. アニメ再生をThree.js側へ（requestAnimationFrame駆動）。
6. マウス選択追加（Raycaster）。
7. **最後に**単一HTML文字列を分割（HTML/CSS/JS、Vite等）。今やると全機能が人質になるので最後。

原則: 各ステップで旧UIを消さず並存し、新UIで再現できてから旧を落とす。

### 今避けるべき設計負債

- JSへの幾何意味論の漏れ（Cartesian・度・正規化済みで渡す規約を今決める）。
- 3320行の単一HTML文字列を太らせ続けること（分割まで新機能は別JSファイルへ）。
- パスJSONにバージョンを付けないこと。
- アニメの「真実」を2箇所に持つこと（変更はPython→ゴールデン再生成→JS追従の一方向に固定）。
- 選択・閉包の途中状態をUIに埋めること（Python側の明示的stateに持たせる）。

### コード精査で見つけた不具合（要修正）

**[Bug] 初学者モードで回反軸のH-M記号・読み・角度が誤る（3回回反が「6̄ / 6回回反 / 60°」と表示される）**

- 箇所: `crystal_viewer/web/browser_ui.py` の `beginnerOperationSymbol` / `beginnerOperationReading` / `beginnerOperationText`。
- 原因: これらが `operation.order` を回反軸の位数として使っているが、`order` は**行列の位数**。3回回反軸は `classify_operation` により `kind=rotoinversion_or_improper_6, order=6, angle_deg=None, symbol="-3"` となる（Haliteで実測確認済み）。よって：
  - 記号 `<span class="overline">${order}</span>` → `6̄`（正: `3̄`）
  - 読み `${order}回回反` → `6回回反`（正: `3回回反`）
  - 角度 `360/order = 60°`（正: `360/3 = 120°`）
- 6回回反は order=6 と一致するため偶然正しく見えるが、立方晶・三方晶に頻出する3回回反が全滅する。
- 正: 既存 `displayOperationSymbol` と同様に `operation.symbol`（例 `"-3"`）から数字を抽出して使う（`String(operation.symbol).match(/[0-9]+/)`）。回転角も `360 / その数字`。`order` は使わない。
- 補足: 既存 `displayOperationSymbol` も `operation.order || match` と order を優先しており同じ潜在バグを持つ（ITC表記が既定のため露出していないだけ）。共通の抽出ヘルパに寄せて両方直すのが望ましい。
