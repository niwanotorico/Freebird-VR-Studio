# Puddinger VR

[English](README.md)

> **Freebird XR 用の非公式プラグインです。** Puddinger VR は個人の独立したプロジェクトで、Freebird XR チームが作ったもの・公認したものではありません。
> **旧名称は「Freebird VR Studio」／「VR Studio」** です。Freebird 本体と混同されないよう、Freebird の開発者からの依頼を受けて改名しました。

**「Blender は強力だけど VR だと難しい」→「VR なら触るだけ」**

Puddinger VR は [Freebird XR](https://freebirdxr.com)（Blender 用の VR モデリングアドオン）用の非公式プラグインです。
Freebird の VR メニューの横に小さなパネルエリアを追加し、オブジェクトの色・マテリアルの質感・シーンの表示方法を、
トリガーひと押しで切り替えられます。

> 初期の公開版（アルファ）です。ご意見は [Issues](https://github.com/niwanotorico/Puddinger-VR/issues) へどうぞ。

## できること

| ボタン | 内容 |
|---|---|
| **Color** | 32 色パレット。オブジェクトを選んで、色を指してトリガーを引くだけ。 |
| **Picker** | 好きな色を作れる：色相×明るさのマップ＋彩度の列。**Pick** はスポイト（掴み球で触れたものの色を取る）。 |
| **Look** | 8 種類の質感：Clay / Matte / Glossy / Plastic / Metallic / Glass / Emission / Toon。Color とは独立。 |
| **View** | **自分のヘッドセット**の表示を切り替え：Wireframe / Solid / Material Preview / Rendered。Overlay のオン/オフ、コントローラーの通常／透け（コントローラーを薄くして、掴み球や奥の物が見えるようにする）。 |
| **Grab** | Gravity Sketch 風のつかみ。中指の球が触れたものをつかむ（届く距離 Off / 3 / 5 / 8 cm）。握って B で削除、握ってトリガーで複製、左 X でグループ化。手に対する球の位置は 0.5 cm 刻みで微調整できる。 |
| **Edit** | Object / Edit / Pose Mode、Vert / Edge / Face、プロポーショナル編集。Edit Mode では球で頂点をつかむ。 |
| **Pudding** | ものをぷるぷる揺らす：Off / Soft / Wobbly / Jelly。**New** で手元にプリンを出す。 |

Color と Look は Freebird 標準の Undo / Redo で戻せます。

## インストール

[Releases](https://github.com/niwanotorico/Puddinger-VR/releases) から `puddinger_vr-v<バージョン>.zip` をダウンロードし、
普通の Blender アドオンと同じように入れます（**Edit › Preferences › Add-ons › ⌄ › Install from Disk…**。zip は解凍しない）。
アドオンが Freebird XR 用にプラグインを配置するので、VR で Freebird メニュー → **Plugins** → Color / Picker / Look / View / Grab / Edit / Pudding を開きます。

詳しい手順・更新・アンインストール（英語）：[release/vr_studio/README.md](release/vr_studio/README.md)

動作環境：Blender 5.2（確認済み。4.2 以降も動く想定）、Freebird XR 2.15.0 以降。

## FreebirdCollabo と一緒に使う（任意）

Puddinger VR は単体で動きます。[FreebirdCollabo](https://github.com/niwanotorico/FreebirdCollabo) と併用すると、
Color / Look の変更はそのマテリアル同期で部屋の全員に届きます。View は共有されません（各自の表示のまま）。
既知の制限：Picker のオブジェクト色は部屋に同期しません（マテリアル色は同期します）。

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
# dist/puddinger_vr-v<バージョン>.zip（+ リリースノート、.sha256）を作る。標準ライブラリのみ
python tools/build_vr_studio_release.py

# テスト（bpy モジュールが必要。無ければ Blender 経由で実行）
python3 tests/test_vr_studio.py unit
FREEBIRD_XR_DIR=<...>/scripts/addons/freebird_xr python3 tests/test_vr_studio.py ui
blender --background --factory-startup --python tests/blender_runner.py -- tests/test_vr_studio.py ui
FREEBIRD_XR_DIR=<...> python3 tests/test_vr_studio_release.py
```

2 インスタンスの同期テスト（Puddinger VR の変更が共同編集の部屋で相手に届くか）は FreebirdCollabo 側に残しています。

## ライセンス

GPL-2.0-or-later（Freebird XR と同じ）。[LICENSE](LICENSE) を参照。
Puddinger VR は非公式の独立したプラグインで、Freebird XR チームとは関係がなく、公認も受けていません。

## 謝辞

Freebird と、そのプラグイン API を作ってくださった [Freebird XR](https://freebirdxr.com) の開発者 **cmdr2** さんに心から感謝します。
両プロジェクトを見分けやすくするための改名も、丁寧に提案していただきました。Freebird がなければ Puddinger VR は生まれていません。
