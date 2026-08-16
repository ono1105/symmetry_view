# Test Fixtures

## `cif/` — 32 結晶類のカバレッジセット

もとは `examples/cif/` に置いていた「32 の結晶類を 1 件ずつ」のセット。
実在の構造ではあるが、128 原子の `C12H14N4` や 64 原子 P1 の `Babefphite`、
`Ho2Rh12As7` のように**大きすぎるか馴染みがない**ため、対称性の教材としては
不適だった。2026-08-15 に `examples/` から外し、ここへ移した。

捨てないのは、**このセットだけが 32 の結晶類すべてを踏む**から。
`tests/test_fixture_cif_coverage.py` が全 30 件を解析して
(空間群番号, 記号, 結晶類, 原子数) を照合する。残り 2 類（m-3m と 3m）は
教材側に残した `Halite.cif` と `BaTiO3.cif` が担当する。

ここの CIF は `examples/` 直下ではないので、`resolve_example_path()` が弾く。
つまりブラウザからは開けない＝ユーザーには見えない。

## `json/` — 上の一部のエクスポート

テストが実際に読む 5 件だけを置いている（全件置くと 7MB 増えるだけで誰も読まない）。

| ファイル | 読んでいるテスト |
|---|---|
| `agcl.json` | `test_cell_settings.py`, `test_view_json_server.py` |
| `antimony.json` | `test_operation_labels.py`（3 回回転の回転方向） |
| `cadmoselite.json` | `test_operation_labels.py`, `test_itc_tables.py` |
| `nbp.json` | `test_cell_settings.py`（primitive 変換） |
| `sio2.json` | `test_animation_api.py` |

再生成:

```bash
.venv/bin/python tools/regenerate_example_assets.py --no-catalog --json-dir tests/fixtures/json \
  --source tests/fixtures/cif/AgCl.cif --source tests/fixtures/cif/Antimony.cif \
  --source tests/fixtures/cif/Cadmoselite.cif --source tests/fixtures/cif/NbP.cif \
  --source tests/fixtures/cif/SiO2.cif
```

`--no-catalog` を付けないと `examples/example_catalog.json` をこの 5 件で上書きしてしまう。

テストからは `tests/support.py` の `load_export()` / `load_render_data()` で読む。
このディレクトリを先に見て、無ければ `exports/json/` へ落ちるので、
構造がどちら側にあるかをテストが気にしなくてよい。

## その他

`animation_path_golden.json` と `boundary_wrap_golden.json` は
アニメーション経路のゴールデンデータで、上とは無関係。
