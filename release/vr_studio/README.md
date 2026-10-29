# Puddinger VR — v@VERSION@

> **Unofficial plugin for Freebird XR.** Puddinger VR is an independent project, not made or endorsed by
> the Freebird XR team. **Formerly called "VR Studio" / "Freebird VR Studio"** — renamed at the request of
> Freebird's developer so it isn't confused with Freebird XR itself. Existing installs update normally.

**"Blender is powerful but hard in VR" → "in VR you just touch it."**

Puddinger VR is a plugin for [Freebird XR](https://freebirdxr.com) (the VR modeling add-on for Blender).
It adds a small panel area next to Freebird's VR menu where you can colour objects, give them a
material look, and switch how the scene is shaded — all with one press of the trigger.

It installs like any other Blender add-on: no Git, no code, no copying files by hand.
It does **not** modify Blender, Freebird XR or any other add-on.

> Early public version (alpha). Feedback is welcome on the
> [GitHub issues page](https://github.com/niwanotorico/Puddinger-VR/issues).

---

## Requirements

| | Version |
|---|---|
| **Blender** | **5.2** (tested). Blender 4.2+ is expected to work but has not been tested yet. |
| **Freebird XR** | **2.15.0** or newer (tested with 2.15.0), installed and enabled. |
| **VR** | A PC VR headset that already works with Freebird XR. |

---

## Installation

1. Download **`puddinger_vr-v@VERSION@.zip`**. **Do not unzip it.**
2. In Blender: **Edit › Preferences › Add-ons**, click the **⌄** menu at the top right → **Install from Disk…**,
   and choose `puddinger_vr-v@VERSION@.zip`.
3. Make sure **Puddinger VR** is ticked (enabled).
   It sets the plugin up for Freebird automatically — expand the add-on to see
   *Puddinger VR plugin: Installed @VERSION@ - up to date*.
4. Start VR with Freebird XR → open the Freebird menu → **Plugins** → **Color**, **Picker**, **Look**, **View**, **Grab**, **Edit**, **Pudding**.
   (If they are not there yet, restart Blender once.)

### Updating

Install the newer zip the same way (Install from Disk). When the add-on is enabled it replaces the old
plugin, after moving the old copy to a backup folder (`~/.freebird/plugin_backups/`). Nothing is deleted.
If a *newer* Puddinger VR is already installed, it is left alone.
If the add-on still says *update available* afterwards (e.g. after a failed copy), press **Update Puddinger VR** in its preferences.
(Coming from VR Studio: the add-on is the same one, now shown as **Puddinger VR**.)

### What the add-on shows

Expand **Puddinger VR** in the Add-ons list:

- the installed plugin version and whether it is up to date
- **Install / Update** — copies the bundled plugin again (an existing copy is backed up first)
- **Remove Puddinger VR Plugin** — deletes the plugin (asks first)
- **Open Plugins Folder / Open Backups Folder**

---

## How to use

Open the Freebird menu in VR → **Plugins**, then press a button to show or hide its panel.
The panels appear in the Puddinger VR area right next to the main menu and follow your hand.

| Button | What it does |
|---|---|
| **Color** | 32-colour palette. Select objects, point at a colour, pull the trigger — done. |
| **Picker** | Any colour: a hue × lightness map (pull the trigger, slide, let go) and a saturation strip. **Pick** = eyedropper: touch something with the grab sphere and its colour becomes your pen's / current colour; **Paint** colours the selection with it. |
| **Look** | 8 material looks: **Clay, Matte, Glossy, Plastic, Metallic, Glass, Emission, Toon**. Independent of Color: a blue Matte object turned Metallic stays blue, and a new colour keeps the look. |
| **View** | Switches how *your headset* shows the scene: **Wireframe / Solid / Material Preview / Rendered**, Overlays on / off, and **Controller: Normal / See-through** (faint controllers, so the grab sphere and what is behind them stay visible). It only changes your own view. |
| **Grab** | Gravity Sketch style grab: a sphere on your middle finger grabs what it touches (reach Off / 3 / 5 / 8 cm). Squeeze + B deletes, squeeze + trigger duplicates, left X groups. The sphere's position on your hand can be fine-tuned in 0.5 cm steps (Axis / - / + / Reset). |
| **Edit** | Object / Edit / Pose Mode, Vert / Edge / Face, proportional editing. In Edit Mode the sphere grabs vertices. |
| **Pudding** | Makes things jiggle: Off / Soft / Wobbly / Jelly. **New** puts a pudding in your hand. |

- **Undo / Redo** are Freebird's own (they cover Color and Look changes).
- Colour and look are ordinary Blender materials, so they are saved in the .blend and render normally.
- If an object has no material, Puddinger VR creates one (`VR <object name>`). A material shared with an
  object you did *not* select is copied first, so the other object keeps its look.
- If Base Color is driven by an image texture, pressing a colour unplugs that texture (the image node
  stays in the material; Undo plugs it back in).

### Using it together with FreebirdCollabo (optional)

Puddinger VR works on its own. If you also use the
[FreebirdCollabo](https://github.com/niwanotorico/FreebirdCollabo) add-on (shown as
*Freebird Collaboration Layer* in Blender's add-on list), colour and look changes reach everyone
in the room through its material sync. **View** is never shared — each
person keeps their own shading.
**Known limitation:** Picker's object colour (Solid view's "Object" colour) does not sync to the room; the material colour does.

---

## Uninstall

1. **Edit › Preferences › Add-ons** → expand **Puddinger VR** → **Remove Puddinger VR Plugin** → confirm.
2. Then remove the add-on itself (**⌄** next to it → **Uninstall**), and restart Blender.

Disabling or removing only the add-on does **not** remove the plugin — Puddinger VR keeps working in Freebird
until you press *Remove Puddinger VR Plugin* (or delete `~/.freebird/plugins/vr_studio` yourself).
Backups in `~/.freebird/plugin_backups/` are never deleted automatically.
Materials you already made stay in your .blend files.

---

## Troubleshooting

| Problem | What to check |
|---|---|
| Color / Look / View are not in the Plugins menu | Restart Blender. Check the add-on says *Installed … up to date*. Is Freebird XR 2.15.0 or newer? |
| The add-on says *Freebird XR was not found* | Install and enable Freebird XR, then press **Install Puddinger VR**. |
| Nothing happens when I press a colour | Select one or more objects first (the panel says *Select an object first*). |
| **Rendered** view is very slow | Rendered uses the scene's render engine. EEVEE is fine in VR; Cycles is very heavy for two eyes. |
| **Glass** does not look transparent | In EEVEE, enable Raytracing in Render Properties. |

*Window › Toggle System Console* shows messages starting with `[vr_studio]` or `[Puddinger VR setup]` —
please include them when reporting an issue.

Where things go (for reference): the plugin lives in `C:\Users\<you>\.freebird\plugins\vr_studio`
(macOS/Linux: `~/.freebird/plugins/vr_studio`), which is where Freebird XR loads plugins from.

---

## License

GPL-2.0-or-later (same as Freebird XR). See `LICENSE.txt`.
Puddinger VR is an unofficial, independent plugin and is not affiliated with or endorsed by the Freebird XR team.

Thank you to **cmdr2**, the developer of Freebird XR, for building Freebird and its plugin API — Puddinger VR
would not exist without it.
