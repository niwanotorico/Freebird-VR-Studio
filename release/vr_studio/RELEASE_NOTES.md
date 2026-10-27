# VR Studio v@VERSION@ — Picker (alpha)

**Tag:** `vr-studio-v@VERSION@` · **Pre-release** · Asset: `vr_studio-v@VERSION@.zip`

VR Studio is a plugin for **Freebird XR** that lets you colour, restyle and re-shade your Blender
scene from inside VR with one trigger press. It is a separate download from the
[FreebirdCollabo](https://github.com/niwanotorico/FreebirdCollabo) add-on and works without it.

## Install (like any Blender add-on)

1. Download **`vr_studio-v@VERSION@.zip`** below — don't unzip it.
2. Blender → **Edit › Preferences › Add-ons › ⌄ › Install from Disk…** → pick the zip → make sure
   **VR Studio for Freebird XR** is enabled.
3. Start VR → Freebird menu → **Plugins** → **Color / Picker / Look / View / Grab / Edit / Pudding** (restart Blender once if they're not there yet).

The add-on only sets up the plugin for Freebird XR (install / update / remove). Updating = installing a
newer zip the same way; the old plugin is backed up to `~/.freebird/plugin_backups/` first.
Uninstall: add-on preferences → **Remove VR Studio Plugin**, then remove the add-on.

## Requirements

- **Blender 5.2** (tested). Blender 4.2+ expected to work, not yet tested.
- **Freebird XR 2.15.0** or newer.

## New in v0.5.1

- **Room sync for Pudding, groups and object colour** — with FreebirdCollabo, the Pudding level
  (Off / Soft / Wobbly / Jelly), grouping / ungrouping done after an object exists, and the object colour
  (Solid view "Object" mode, Freebird strokes) now reach everyone in the room. Everyone in the room needs
  v0.5.1 or newer for this; people on older versions simply don't see it. The wobble itself is computed
  on each PC. FreebirdCollabo itself is not changed.

## New in v0.5

- **Picker** — any colour, not just the 32 swatches: a hue × lightness map (pull the trigger, slide,
  let go) and an 8-step saturation strip. **Pick** is an eyedropper: touch something with the grab sphere
  and its colour becomes your pen's / current colour; **Paint** colours the selection with it.
- **Menu** — closing Freebird's menu hides the VR Studio panels too; opening it brings them back
  (A still opens the Color panel while the menu is closed).
- **Pudding** — **New** makes the pudding as two objects (custard + caramel) in one group, so the caramel
  stays brown in Solid view's "Object" colour mode; the group wobbles as one.
- **Grab** — after squeeze + trigger (duplicate), the copies are what ends up selected, not the originals.
- **Pudding (Blender 5)** — a group member that is not moving itself now wobbles too.

## New in v0.4

- **Grab** — Gravity Sketch style grab: a sphere on your middle finger (reach Off / 3 / 5 / 8 cm) grabs
  everything it touches; touched / held things get a red outline. Squeeze + B = delete, squeeze + trigger = duplicate.
  The sphere's position on your hand can be fine-tuned in 0.5 cm steps (Axis / - / + / Reset).
- **Buttons** — B = undo, A = Color panel, left X tap = group / ungroup, right stick = grab sphere size.
- **Groups** — grabbing a member grabs the whole group; Color / Look colour every member.
- **Edit** — Object / Edit / Pose Mode, Vert / Edge / Face, proportional editing. In Edit Mode the grab sphere grabs vertices.
- **Pudding** — make things jiggle like a pudding (Off / Soft / Wobbly / Jelly), and **New** puts a pudding
  in your hand. Move it or bump it and it wobbles. The mesh itself is not changed.
- **Pen** — the colour and look you pick are also what you draw next (works with nothing selected).
- **View** — Overlays on / off; heavy modes are shown in amber. **Controller: Normal / See-through** makes
  Freebird's controller cards faint, so the grab sphere and what is behind them stay visible (just you).
- Panel headers show **GLOBAL** (synced to the room) or **LOCAL** (just you).

## Features

- **Color** — 32-colour palette. Select objects, point, pull the trigger.
- **Look** — 8 material presets: Clay / Matte / Glossy / Plastic / Metallic / Glass / Emission / Toon.
  Look and Color are independent of each other.
- **View** — headset shading switch: Wireframe / Solid / Material Preview / Rendered. Local to you only.
- Panels live in a VR Studio area to the right of Freebird's main menu and follow your hand.
- Freebird's Undo / Redo work for Color and Look.
- With FreebirdCollabo: Color / Look changes sync to everyone; View never syncs.

## Known limitations

- **Rendered** with Cycles is very heavy in VR — use EEVEE.
- **Glass** transparency needs Raytracing enabled (EEVEE).
- Pressing a colour unplugs an image texture on Base Color (Undo restores it).
- Picker's object colour (Solid view's "Object" colour) does not sync to the room; the material colour does.
- Only tested on Windows with Blender 5.2 + Freebird XR 2.15.0.

## Checksums

```
@SHA256@  vr_studio-v@VERSION@.zip
```
