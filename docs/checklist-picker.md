# 実機確認チェックリスト：Picker ほか（v0.5.0）

ブランチ `wip-picker-collab-bridge`（5080 の `~/.freebird/plugins/vr_studio` から保全）のうち、
v0.5.0 に入れる分。`collab_bridge.py`（とその起動タイマー）、`pudding_icon_user.png` は含めない
（wip ブランチに残す）。

## 範囲
- PICKER パネル：色相×明るさマップ（トリガーを引いて滑らせ、離すと適用）、彩度 8 段、
  Paint（選択に今の色）、Pick（スポイト：掴み球で触れた物の色を取る）
- Freebird のメニューを閉じると VR Studio のパネルも隠れる（開くと戻る。閉じている間も A で COLOR は出る）
- New プリン：カスタード＋カラメルの 2 オブジェクトを 1 グループに（Solid の Object 色でもカラメルが茶色）
- 握って複製した後、選択されるのは複製の方
- Blender 5：自分は動いていないグループのメンバーもぷるぷるする（jiggle の再評価）

## 実機確認の結果
- [x] 5080 実機確認済み（2026-10-21）
  - 実機フォルダは v0.4.0 ＋ 透け表示 ＋ Picker の組み合わせで確認
- [x] Picker：マップ（色相×明るさ）
- [x] Picker：彩度
- [x] Picker：スポイト（Pick）
- [x] Picker：Paint
- [x] メニューを閉じると VR Studio のパネルも隠れる
- [x] New Pudding がグループになる
- [x] 握って複製した後は、複製の方が選択される
- [x] プリンの揺れ

## 既知の制限
- Picker のオブジェクト色は部屋に同期しない（マテリアル色は同期する）
