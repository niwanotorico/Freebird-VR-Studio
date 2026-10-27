# SPDX-License-Identifier: GPL-2.0-or-later
"""Shade Flat / Smooth for the selection (meshes and Freebird strokes / curves). GLOBAL: FreebirdCollabo
syncs the per-face smooth flags with the geometry (its Issue #14), so everyone in the room sees the same.
With an older FreebirdCollabo the others keep seeing their own shading."""

import bpy


def _faces_smooth(ob):
    """True / False when all faces agree, None when mixed (or nothing to shade)."""
    if ob.type == "MESH":
        me = ob.data
        if ob.mode == "EDIT":
            import bmesh

            flags = {f.smooth for f in bmesh.from_edit_mesh(me).faces}
        else:
            flags = {p.use_smooth for p in me.polygons}
    elif ob.type == "CURVE":
        flags = {sp.use_smooth for sp in ob.data.splines}
    else:
        return None
    return flags.pop() if len(flags) == 1 else None


def can_shade(ob):
    return ob.type in ("MESH", "CURVE") and not getattr(ob.data, "library", None)


def current(targets):
    """"SMOOTH" / "FLAT" when every target agrees, else None."""
    states = {_faces_smooth(ob) for ob in targets if can_shade(ob)}
    if states == {True}:
        return "SMOOTH"
    if states == {False}:
        return "FLAT"
    return None


def set_shading(targets, smooth):
    """Returns the number of objects changed. Shared mesh data is changed once."""
    done, seen = 0, set()
    for ob in targets:
        if not can_shade(ob) or ob.data.as_pointer() in seen:
            continue
        seen.add(ob.data.as_pointer())
        if ob.type == "MESH":
            me = ob.data
            if ob.mode == "EDIT":  # the bmesh owns the faces while editing
                import bmesh

                bm = bmesh.from_edit_mesh(me)
                for f in bm.faces:
                    f.smooth = smooth
                bmesh.update_edit_mesh(me)
            elif smooth:
                me.shade_smooth()
            else:
                me.shade_flat()
            me.update()
        else:
            for sp in ob.data.splines:
                sp.use_smooth = smooth
            ob.data.update_tag()
        done += 1
    return done
