# Puddinger VR

[日本語](README_JA.md)

> **Unofficial plugin for Freebird XR.** Puddinger VR is an independent project and is not made or endorsed by
> the Freebird XR team. It was **formerly called "Freebird VR Studio" / "VR Studio"** and was renamed at the request
> of Freebird's developer, so new users don't confuse it with Freebird XR itself.

**"Blender is powerful but hard in VR" → "in VR you just touch it."**

Puddinger VR is an unofficial plugin for [Freebird XR](https://freebirdxr.com) (the VR modeling add-on for Blender).
It adds a small panel area next to Freebird's VR menu where you can colour objects, give them a
material look, and switch how the scene is shaded — all with one press of the trigger.

> Early public version (alpha). Feedback is welcome on the [issues page](https://github.com/niwanotorico/Puddinger-VR/issues).

## Features

| Button | What it does |
|---|---|
| **Color** | 32-colour palette. Select objects, point at a colour, pull the trigger. |
| **Picker** | Any colour: hue × lightness map + saturation strip. **Pick** = eyedropper (touch something with the grab sphere to take its colour). |
| **Look** | 8 material looks: Clay, Matte, Glossy, Plastic, Metallic, Glass, Emission, Toon. Independent of Color. |
| **View** | Switches how *your headset* shows the scene: Wireframe / Solid / Material Preview / Rendered. Overlays on / off, Controller Normal / See-through (faint controllers, so the grab sphere and what is behind them stay visible). |
| **Grab** | Gravity Sketch style grab: a sphere on your middle finger grabs what it touches (reach Off / 3 / 5 / 8 cm). Squeeze + B deletes, squeeze + trigger duplicates, left X groups. The sphere's position on the hand can be fine-tuned in 0.5 cm steps. |
| **Edit** | Object / Edit / Pose Mode, Vert / Edge / Face, proportional editing. In Edit Mode the sphere grabs vertices. |
| **Pudding** | Makes things jiggle: Off / Soft / Wobbly / Jelly. **New** puts a pudding in your hand. |

Freebird's own Undo / Redo cover Color and Look.

## Install

Download `puddinger_vr-v<version>.zip` from [Releases](https://github.com/niwanotorico/Puddinger-VR/releases)
and install it like any Blender add-on (**Edit › Preferences › Add-ons › ⌄ › Install from Disk…**, don't unzip).
The add-on sets the plugin up for Freebird XR; then open the Freebird menu in VR → **Plugins** → Color / Picker / Look / View / Grab / Edit / Pudding.

Full instructions, updating and uninstalling: [release/vr_studio/README.md](release/vr_studio/README.md).

Requirements: Blender 5.2 (tested; 4.2+ expected to work), Freebird XR 2.15.0 or newer.

## Using it with FreebirdCollabo (optional)

Puddinger VR works on its own. Together with [FreebirdCollabo](https://github.com/niwanotorico/FreebirdCollabo)
(shown as *Freebird Collaboration Layer* in Blender's add-on list), Color / Look changes reach everyone in
the room through its material sync. View is never shared.
Known limitation: Picker's object colour (Solid view's "Object" colour) does not sync to the room; the material colour does.

## Repository layout

```
freebird_plugin/vr_studio/     the Freebird plugin itself (what ends up in ~/.freebird/plugins/vr_studio)
release/vr_studio_installer/   the Blender add-on that installs / updates / removes the plugin
release/vr_studio/             end-user README and release notes (templates, filled in by the build)
tools/                         build_vr_studio_release.py (release zip), make_vr_studio_icons.py
tests/                         test_vr_studio.py (unit / ui), test_vr_studio_release.py (install scenarios)
docs/                          development notes per version (Japanese)
```

## Development

```
# build dist/puddinger_vr-v<version>.zip (+ release notes, .sha256) - standard library only
python tools/build_vr_studio_release.py

# tests (need the bpy module, or run them through Blender)
python3 tests/test_vr_studio.py unit
FREEBIRD_XR_DIR=<...>/scripts/addons/freebird_xr python3 tests/test_vr_studio.py ui
blender --background --factory-startup --python tests/blender_runner.py -- tests/test_vr_studio.py ui
FREEBIRD_XR_DIR=<...> python3 tests/test_vr_studio_release.py
```

The two-instance sync test (Puddinger VR changes travelling through the collab room) stays in FreebirdCollabo.

## License

GPL-2.0-or-later (same as Freebird XR). See [LICENSE](LICENSE).
Puddinger VR is an unofficial, independent plugin and is not affiliated with or endorsed by the Freebird XR team.

## Thanks

Huge thanks to **cmdr2**, the developer of [Freebird XR](https://freebirdxr.com), for building Freebird and its
plugin API — and for kindly suggesting the new name so both projects are easier to tell apart. Puddinger VR
would not exist without Freebird.
