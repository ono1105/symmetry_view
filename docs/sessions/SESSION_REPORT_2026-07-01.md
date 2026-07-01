# Session Report 2026-07-01

## 今回の到達点

- ブラウザUIを`Beginner` / `Advanced`に分離した。
- Beginnerには構造選択、操作一覧、アニメーション、カメラ、Projection、Cell Range、Structure Infoを整理して表示する。
- Beginnerの操作表記を`Hermann–Mauguin記号 (読み):動作説明`にした。
- 回反の記号次数と行列位数を分離した。`-3`は`order=6`でも`notation_order=3`として、`3̅ (3回回反):120°回転+反転`と表示する。
- Structure Infoに結晶系、格子定数、元素別原子数、スクロール可能な原子位置を追加した。
- 構造切替時はCell Rangeを必ずUnit cellへ戻す。
- 黄色の開始位置マーカーは再生開始後からResetまで保持する。反転中心は赤い八面体で表示する。
- テストは90件成功。

## UI統合の方針

詳細とClaudeレビューは`docs/UI_INTEGRATION_REVIEW_REQUEST.md`を参照。

第一候補は、解析とアニメーション経路計算をPythonに残し、描画・入力・再生をThree.jsへ移す方式。PyVistaは比較、デバッグ、GIF出力用として当面残す。

次の実装順序:

1. 既存`animation_path.py`のpath dictをJSON化するAPIを追加する。
2. path schemaに`schema_version`と`coordinate_space: "cartesian"`を明記する。
3. `evaluate_path()`のゴールデンJSONを作り、JavaScript版補間器を描画なしで実装・検証する。
4. 現行UI内にThree.jsの静的3D表示を追加し、PyVistaと並存させる。
5. アニメーション、周期像、マウス選択を順に移す。

Pythonを計算の唯一の真実とし、fractional/Cartesian変換、回転符号、行列規約をJavaScript側で再解釈しないこと。

## 作業状態

変更は未push。`gh`は一時CLIを用意できたがGitHub認証がないため、公開には`gh auth login`が必要。
