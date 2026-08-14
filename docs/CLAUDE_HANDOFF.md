# Claude Handoff

新しいセッションで作業を再開するときの依頼プロンプトと、渡すべき前提。
最終更新: 2026-08-15

---

## 再開用プロンプト（このままコピーして貼る）

```text
symmetry_view プロジェクトの作業を再開します。

まず docs/CLAUDE_HANDOFF.md と docs/sessions/SESSION_REPORT_2026-08-15.md を読んでください。
プロジェクトは機能追加を終えて「完成させて報告書にまとめる」段階です。新しいクイズや
新機能は追加しません。docs/PUZZLE_SPEC.md §10 に見送り決定が記録されているので、
そこに「見送り」と書かれているものを実装候補として提案しないでください。

環境構築:
  scripts/setup.sh          # venv と crystal_viewer/web/node_modules の両方を用意する
  .venv/bin/python -m unittest discover -s tests    # 222件 OK が期待値

残っている作業は docs/REPORT_OUTLINE.md の「残作業」に書いてあります。
次は「通し確認とスクリーンショット取得」からお願いします。
```

---

## 現在地（2026-08-15 時点）

**機能は完成。残るのは完成確認と報告書。**

- クイズ4種（回転軸・操作あて・合成・移り先）で打ち切り確定。○×＋偽要素は**見送り**（`PUZZLE_SPEC.md`§10 に理由を記録）
- `PUZZLE_SPEC.md`§10 が「未決定なし」。有効コードに TODO/FIXME は 0 件
- テスト 222 件 OK（うち headless Chromium の実機テスト 6 件）
- `main` は `origin/main` より進んでいる。**push はまだしていない**

### このセッションで入れた変更

```text
9b56747 build: make PyVista an optional extra so the default install drops VTK
e6801b3 docs: record that the maru-batsu quiz was dropped, and close the quiz set at four
4e0f1d6 docs: record verified dependency versions and the 2026-08-15 session
bfdfad6 fix: make generation operation lookup deterministic; install Three.js in setup
```

---

## 環境で先に知っておくこと

このプロジェクトは**クローンしただけでは3D表示が動かない**。過去に一度これで丸1セッション溶かしている。

1. **Three.js が必要**。`crystal_viewer/web/node_modules` は生成物で git に入っていない。
   無いと HTML は 200 で返るのに `/vendor/three` が 503 になり、構造が一切描画されない。
   `scripts/setup.sh` が `npm ci` まで面倒を見る。
2. **npm が無い環境がある**。Ubuntu では `nodejs` と `npm` が別パッケージ。
   `setup.sh` は `npm` → `corepack npm@10` の順にフォールバックする。
3. **PyVista は既定で入らない**（2026-08-15 以降）。Web ビューアーだけで全機能が動く。
   テストは PyVista を要求するので、開発時は `requirements-dev.txt` を入れる。

```bash
.venv/bin/python -m pip install -r requirements-dev.txt   # テスト実行に必要
```

4. **ブラウザテスト**は playwright とブラウザバイナリが無ければモジュールごと skip する。
   `~/.cache/ms-playwright/` はユーザー単位の共有キャッシュで、**別プロジェクトと
   playwright のバージョンを合わせれば再ダウンロード不要**（2026-08-15 時点では 1.62.0 / chromium-1234）。

---

## 踏んではいけない地雷

- **spglib の対称操作の順序に依存しない**。バージョンで変わる。
  `identify_generation_operation()` が「最も近い操作」を選んでいたため、1e-16 の丸め誤差が
  勝者を決めており、spglib 2.7.0 で答えが変わってテストが落ちた（`bfdfad6` で修正済み）。
  特殊位置の原子は席対称群のすべての操作で生成されるので、**どれが正解かは一意に決まらない**。
- **`.claude/settings.json` はコミットしない**（ユーザー側の設定）。
- **`crystal_viewer/legacy/` は現役**。結晶解析が使っているので消さない。
  消してよい候補は `archive/old_gui_attempt/` のほう。

---

## 未解決として報告書に載せるもの

隠さずに「既知の限界」として書く方針。

1. **ブラウザ E2E が 4 クイズ中 2 つ止まり**。`mapping` と `composition` にはあるが、
   回転軸クイズと操作あてクイズは単体テストのみ。`tests/test_puzzle_browser.py` の
   `open_quiz()` ヘルパーが使えるので追加は安価。
2. **ITC 表記の端ケース 2 件**（`REVIEW_NOTES.md` の「未対応の既知問題」）。
   同梱 32 例・601 操作のうち 583 件（97%）は ITC テーブル参照で解決し、
   計算経路に落ちる 18 件（4 例）は中心並進とその剰余類。出力は妥当に見えるが
   **ITC 原典との照合はしていない**。
3. **移り先クイズの色**。青の guess リングと C2 軸の線が近い色になることがある
   （形が違うので実用上は区別できる）。`REVIEW_NOTES.md` 末尾。

---

## 主要ドキュメントの読む順

1. `docs/PROJECT_SPEC.md` — 目的・優先順位・スコープ
2. `docs/PUZZLE_SPEC.md` — パズルの確定仕様と決定事項（§10 が重要）
3. `docs/REPORT_OUTLINE.md` — 報告書の構成案と残作業
4. `docs/sessions/` — セッション履歴（新しいものから）
5. `docs/VIEWER_GUIDE.md` — JSON スキーマ・ビューアー操作（開発者向け・英語）
6. `docs/REVIEW_NOTES.md` — レビュー履歴。必要になったときだけ

`docs/PUZZLE_CONCEPT.md` は**構想メモ**であって仕様ではない。実装しなかった案が
そのまま残っているので、ここを読んで「未実装だから次はこれ」と判断しないこと。
