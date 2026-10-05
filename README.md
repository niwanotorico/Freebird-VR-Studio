# Freebird VR Studio

[日本語](README_JA.md)

**"Blender is powerful but hard in VR" → "in VR you just touch it."**

VR Studio is a plugin for [Freebird XR](https://freebirdxr.com) (the VR modeling add-on for Blender).
It adds a small panel area next to Freebird's VR menu where you can colour objects, give them a
material look, and switch how the scene is shaded — all with one press of the trigger.

> Early public version (alpha). Feedback is welcome on the [issues page](https://github.com/niwanotorico/Freebird-VR-Studio/issues).

## Features

| Button | What it does |
|---|---|
| **Color** | 32-colour palette. Select objects, point at a colour, pull the trigger. |
| **Look** | 8 material looks: Clay, Matte, Glossy, Plastic, Metallic, Glass, Emission, Toon. Independent of Color. |
| **View** | Switches how *your headset* shows the scene: Wireframe / Solid / Material Preview / Rendered. |

Freebird's own Undo / Redo cover Color and Look.

## Install

Download `vr_studio-v<version>.zip` from [Releases](https://github.com/niwanotorico/Freebird-VR-Studio/releases)
and install it like any Blender add-on (**Edit › Preferences › Add-ons › ⌄ › Install from Disk…**, don't unzip).
The add-on sets the plugin up for Freebird XR; then open the Freebird menu in VR → **Plugins** → Color / Look / View.

Full instructions, updating and uninstalling: [release/vr_studio/README.md](release/vr_studio/README.md).

Requirements: Blender 5.2 (tested; 4.2+ expected to work), Freebird XR 2.15.0 or newer.

## Using it with FreebirdCollabo (optional)

VR Studio works on its own. Together with [FreebirdCollabo](https://github.com/niwanotorico/FreebirdCollabo)
(shown as *Freebird Collaboration Layer* in Blender's add-on list), Color / Look changes reach everyone in
the room through its material sync. View is never shared.

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
# build dist/vr_studio-v<version>.zip (+ release notes, .sha256) - standard library only
python tools/build_vr_studio_release.py

# tests (need the bpy module, or run them through Blender)
python3 tests/test_vr_studio.py unit
FREEBIRD_XR_DIR=<...>/scripts/addons/freebird_xr python3 tests/test_vr_studio.py ui
blender --background --factory-startup --python tests/blender_runner.py -- tests/test_vr_studio.py ui
FREEBIRD_XR_DIR=<...> python3 tests/test_vr_studio_release.py
```

The two-instance sync test (VR Studio changes travelling through the collab room) stays in FreebirdCollabo.

## License

GPL-2.0-or-later (same as Freebird XR). See [LICENSE](LICENSE).
VR Studio is an independent project and is not affiliated with the Freebird XR team.
