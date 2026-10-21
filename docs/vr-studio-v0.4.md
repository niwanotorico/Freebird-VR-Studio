# VR Studio v0.4 — Grab / Edit / Pudding（Puddinger のぷるぷる）

v0.3（Color / Look / View）は実機確認済み。v0.4 は Gravity Sketch 風の **GRAB**・ボタン割り当て・グループ・**EDIT**、
そして Puddinger の揺れを移植した **PUDDING** を追加。

確定版：test25（2026-10-13、ちきんさんが「最高」と確認）＋ コントローラー透け表示・掴み球オフセット（2026-10-21 実機確認、
`docs/checklist-controller-see-through.md`）。どちらも v0.4.0 に含める。

リポジトリの `freebird_plugin/vr_studio/` は 5080 の `~/.freebird/plugins/vr_studio` と同じではない。
実機フォルダには、その後の未確認の作業（Picker、collab_bridge、メニュー連動、プリンの 2 パーツ化など。
ブランチ `wip-picker-collab-bridge` に保全）も入っているため。v0.4.0 にはそれらを含めない。

## 1. 追加・変更したもの

| 区分 | ファイル |
|---|---|
| 新規 | `grab.py` `controls.py` `groups.py` `outline.py` `brush.py` `editmode.py` `edit_section.py` `grab_section.py` `jiggle.py` `play_section.py` `spawn.py` |
| 新規アイコン | grab / trash / group / edit / view_overlay / play / play_jiggle / pud_off / pud_soft / pud_wobbly / pud_jelly / pud_new |
| 変更 | `__init__.py`（fb_info 0.4.0、Grab / Edit / Pudding ボタン）、`area.py`（パネルの並べ替え・下にも伸ばせる・GLOBAL/LOCAL バッジ）、`view.py` / `view_section.py`（Overlay のオン/オフ、重いモードの表示）、`materials.py`（グループを展開して色を付ける）、`color_section.py` / `look_section.py`（選んだ色・質感がペンにも付く） |
| 使わない | `floating.py`（浮かせるパネル。失敗して手元の並べ替えに置き換えた）→ リポジトリには入れない |

各機能の概要は `freebird_plugin/vr_studio/__init__.py` の docstring を参照。

## 2. PUDDING（jiggle.py / spawn.py）

### 揺れ方
- Puddinger の `01_pudding/pudding_jiggle.py` を移植。
- **きっかけ**：プローブ（高さの 75% の位置）の速度変化。動かす・回す・止めるで揺れる。
- **バネ**：k=240、c=7.5、240Hz のサブステップ。
- **変形**は 2 つ（どちらも Puddinger のシェイプキーと同じ形）
  - **Wobble**：根元は動かず上だけズレる。高さ² に比例。
  - **Squish**：z×0.76、xy×1.2。
- **実装**：シェイプキーではなくジオメトリノードのモディファイア（ノード `Puddinger Jiggle v1` / モディファイア名 `Puddinger Jiggle`）。
  - 元のメッシュは変更しない。
  - FreebirdCollabo は Armature 以外のモディファイアを同期しないので、通信は増えない。
- **大きさ**：オブジェクトの高さに合わせて揺れ量を調整するので、大きさに関係なく同じ揺れ方。
- **触ったとき**：中指の球で触ると、手の向きに揺れる。
- **グループ**：VR グループはグループの空間でまとめて変形する（1 つのプリンとして揺れる）。プリンを含めてグループ化すると全員に同じ段階が付く。
- **旧方式からの移行**：SimpleDeform を使っていた旧版のプリンは自動で新方式に切り替わる。

### 段階（オブジェクトのプロパティ `puddinger_jiggle`）

| 値 | 名前 | 強さ | 振れ幅 | てっぺんの最大振れ幅（8cm を 0.3 秒で動かす、高さ比） |
|---|---|---|---|---|
| 1 | Soft | 1.2 | 1.5 | 13% |
| 2 | Wobbly | 2.0 | 2.0 | 21% |
| 3 | Jelly | 3.0 | 2.6 | 32% |
| — | 元の Puddinger | | | 10% |

### 重さ
揺れている間だけ増える。止まっていればほぼ 0。
- 小物 10 個が揺れているとき：約 3ms/フレーム
- 10 万頂点のメッシュが揺れているとき：約 4.5ms/フレーム

### パネル（PUDDING、GLOBAL）
- **1 段目**：Off / Soft / Wobbly / Jelly。選択中のものが同じ段階なら、そのボタンが光る。
- **2 段目**：New。中指の球の位置に、Puddinger の `create_pudding.py` と同じ形のプリンを出す（spawn.py）。
  VR 内で見て約 13cm、カスタードとカラメルの色、最初から Wobbly。
- **アイコン**：ちきんさんの手描きのプリンをもとに、段階ごとの違いと New 用の＋マークを付けた。

## 3. テスト

- Freebird のフェイクモジュール＋ bpy 5.2.2 で確認済み（Cowork VM）。
  - Pudding は Puddinger と同じテスト（8cm/0.3 秒、30/60/90Hz）で、揺れの最大値が一致。
  - グループの揺れが、1 つにくっつけたメッシュの揺れと一致。
  - これらの揺れのテストは `tests/` には入れていない（VM 上の検証用）。
- リポジトリの `tests/` は v0.4 の仕様に合わせて期待値を更新（Blender 5.2.1 で unit / ui / release すべて PASS）
  - View の Rendered のメッセージが「Rendered - very heavy in VR (エンジン名)」になった
  - 何も選んでいないときの Look は「Select an object first」ではなく、ペンの質感を変える（`Pen: …`）
  - Plugins メニューのセクションに grab / edit / play が増えた
  - 配布 zip のアイコン数 15 → 27、「新しい版は上書きしない」テストの仮の版を 0.5.0 に

## 4. 開発メモ

- **device_commit_files のキャッシュ**：同じ stagedPath 名で送り直すと、古い中身が届くことがある。
  毎回別のファイル名（`*_vNN.py` など）にしてから送り、送ったあと md5 で確認する。
- **PNG**：転送するときに保存し直される。ピクセルは同じ。
- Freebird / FreebirdCollabo の本体は変更しない（実行中に置き換えて、終了時に元に戻す方式のみ）。
