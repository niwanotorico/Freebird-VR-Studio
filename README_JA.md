# Freebird VR Studio

[English](README.md)

**「Blender は強力だけど VR だと難しい」→「VR なら触るだけ」**

VR Studio は [Freebird XR](https://freebirdxr.com)（Blender 用の VR モデリングアドオン）のプラグインです。
Freebird の VR メニューの横に小さなパネルエリアを追加し、オブジェクトの色・マテリアルの質感・シーンの表示方法を、
トリガーひと押しで切り替えられます。

> 初期の公開版（アルファ）です。ご意見は [Issues](https://github.com/niwanotorico/Freebird-VR-Studio/issues) へどうぞ。

## できること

| ボタン | 内容 |
|---|---|
| **Color** | 32 色パレット。オブジェクトを選んで、色を指してトリガーを引くだけ。 |
| **Look** | 8 種類の質感：Clay / Matte / Glossy / Plastic / Metallic / Glass / Emission / Toon。Color とは独立。 |
| **View** | **自分のヘッドセット**の表示を切り替え：Wireframe / Solid / Material Preview / Rendered。Overlay のオン/オフ、コントローラーの通常／透け（コントローラーを薄くして、掴み球や奥の物が見えるようにする）。 |
| **Grab** | Gravity Sketch 風のつかみ。中指の球が触れたものをつかむ（届く距離 Off / 3 / 5 / 8 cm）。握って B で削除、握ってトリガーで複製、左 X でグループ化。手に対する球の位置は 0.5 cm 刻みで微調整できる。 |
| **Edit** | Object / Edit / Pose Mode、Vert / Edge / Face、プロポーショナル編集。Edit Mode では球で頂点をつかむ。 |
| **Pudding** | ものをぷるぷる揺らす：Off / Soft / Wobbly / Jelly。**New** で手元にプリンを出す。 |

Color と Look は Freebird 標準の Undo / Redo で戻せます。

## インストール

[Releases](https://github.com/niwanotorico/Freebird-VR-Studio/releases) から `vr_studio-v<バージョン>.zip` をダウンロードし、
普通の Blender アドオンと同じように入れます（**Edit › Preferences › Add-ons › ⌄ › Install from Disk…**。zip は解凍しない）。
アドオンが Freebird XR 用にプラグインを配置するので、VR で Freebird メニュー → **Plugins** → Color / Look / View / Grab / Edit / Pudding を開きます。

詳しい手順・更新・アンインストール（英語）：[release/vr_studio/README.md](release/vr_studio/README.md)

動作環境：Blender 5.2（確認済み。4.2 以降も動く想定）、Freebird XR 2.15.0 以降。

## FreebirdCollabo と一緒に使う（任意）

VR Studio は単体で動きます。[FreebirdCollabo](https://github.com/niwanotorico/FreebirdCollabo) と併用すると、
Color / Look の変更はそのマテリアル同期で部屋の全員に届きます。View は共有されません（各自の表示のまま）。

## リポジトリ構成

```
freebird_plugin/vr_studio/     Freebird プラグイン本体（~/.freebird/plugins/vr_studio に入るもの）
release/vr_studio_installer/   プラグインを入れる / 更新する / 外す Blender アドオン
release/vr_studio/             利用者向け README とリリースノート（ビルド時に埋め込むテンプレート）
tools/                         build_vr_studio_release.py（配布 zip）、make_vr_studio_icons.py
tests/                         test_vr_studio.py（unit / ui）、test_vr_studio_release.py（インストールの各シナリオ）
docs/                          バージョンごとの開発記録
```

## 開発

```
# dist/vr_studio-v<バージョン>.zip（+ リリースノート、.sha256）を作る。標準ライブラリのみ
python tools/build_vr_studio_release.py

# テスト（bpy モジュールが必要。無ければ Blender 経由で実行）
python3 tests/test_vr_studio.py unit
FREEBIRD_XR_DIR=<...>/scripts/addons/freebird_xr python3 tests/test_vr_studio.py ui
blender --background --factory-startup --python tests/blender_runner.py -- tests/test_vr_studio.py ui
FREEBIRD_XR_DIR=<...> python3 tests/test_vr_studio_release.py
```

2 インスタンスの同期テスト（VR Studio の変更が共同編集の部屋で相手に届くか）は FreebirdCollabo 側に残しています。

## ライセンス

GPL-2.0-or-later（Freebird XR と同じ）。[LICENSE](LICENSE) を参照。
VR Studio は独立したプロジェクトで、Freebird XR チームとは関係ありません。
