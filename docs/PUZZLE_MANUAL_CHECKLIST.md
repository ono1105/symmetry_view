# Puzzle Manual Check List

パズルモードは描画・非同期操作・ユーザー体験の確認が必要なので、単体テストだけでなく代表構造で手動確認する。

## 起動

```bash
.venv/bin/python tools/view_json_server.py --mode puzzle --port 8799 --no-browser
```

ブラウザで `http://localhost:8799/` を開く。

## 共通確認

- 解析モードからパズルへ移動しても、前の原子選択や表示範囲でパズルのアニメが1原子だけになることがない。
- パズル滞在中、解析ビューのポーリングでパズル表示が上書きされない。
- パズルから戻った後、解析ビューが最新の構造へ再同期する。
- 「もう一度」「別の物質」「クイズを選ぶ」を連打しても、前問の結果・対称要素・アニメが混入しない。
- 回答後に「再生」を押しても、操作あてクイズの対称要素表示が消えたままにならない。
- 結晶では境界原子が表示され、アニメも表示中の全原子に適用される。

## 回転軸クイズ

| 難易度 | 構造 | 確認点 |
|---|---|---|
| やさしい | water | C2軸のみが自然に見える。正解は2回。 |
| やさしい | ammonia | C3軸が出る。正解は3回。 |
| ふつう | benzene | 主軸C6と別種C2軸が出題される。表示軸とリビールアニメの軸が一致する。 |
| ふつう | xenon_tetrafluoride | C4/C2の見分けができる。正解表示が最高次数1つになっている。 |
| ふつう | carbon_dioxide | C∞軸が出題される場合、選択肢に無限回があり、リビールなしで破綻しない。 |
| むずかしい | sulfur_hexafluoride | 高対称分子で複数種類の軸が出る。等価軸の重複が冗長でない。 |
| むずかしい | MgHPO3(H2O)6 | 結晶の表示軸と回転アニメ軸の位置が一致する。 |
| むずかしい | halite | 境界原子込みでも表示・リビールが破綻しない。 |

## 操作あてクイズ（普通）

| 構造 | 確認点 |
|---|---|
| water | 回転・鏡映が出題される。動かない面は出題されない。 |
| carbon_dioxide | 反転と垂直鏡映が同じ見た目の1問に統合され、どちらでも正解になる。 |
| methane | 回映S4が出題され、次数4を要求する。 |
| benzene | CnとSnが同じ見た目になる問題で複数正解表示が自然に読める。 |
| halite | 回反-3/-4、回転、鏡映、反転が出る。回答後に軸・面・中心が表示される。 |

## 操作あてクイズ（難しい）

| 構造 | 確認点 |
|---|---|
| water | 出題なしメッセージになる。 |
| halite | らせん・映進だけが出題される。映進面の矢印が回答後に表示される。 |
| tellurium | らせん軸が出る。次数が結晶の操作次数と一致する。 |
| NbP / Ge Hf O4 | 4回らせん・2回らせん・映進が選択肢として破綻しない。 |

## APIスポット確認

```text
/api/puzzle/axis_orders
/api/puzzle/axis_orders/check
/api/puzzle/operations?difficulty=normal
/api/puzzle/operations?difficulty=hard
/api/puzzle/operations/check
/api/animation_path?operation_index=N&scope=displayed
/api/symmetry_elements?operation_index=N
/api/render_data?boundary_images=1
```

確認点:

- `difficulty=hard` は screw/glide のみを返す。
- `group` は公開されるが `answers` は公開されない。
- `scope=displayed` と `boundary_images=1` は shared state を書き換えない。
