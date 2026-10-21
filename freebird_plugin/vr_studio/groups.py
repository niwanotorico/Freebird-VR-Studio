# SPDX-License-Identifier: GPL-2.0-or-later
"""Groups (GLOBAL: synced through FreebirdCollabo's parent/child + object sync).

A group is an Empty named "VRGroup..." that the grouped objects are parented to (world
transforms kept). Grabbing any member grabs the whole group; delete / duplicate act on the
whole group. Left X tap: 2+ things selected (or held) -> group them; one group -> ungroup.
Holding X (Freebird's "select while held") keeps working: only a short tap without the
trigger counts.
"""

import time

import bpy

PREFIX = "VRGroup"
TAP_SECONDS = 0.35

_x = {"down_at": None, "trigger_used": False}


def is_group(ob):
    return ob is not None and ob.type == "EMPTY" and (ob.name.startswith(PREFIX) or ob.get("vr_studio_group"))


def group_root(ob):
    """Outermost VR group containing ob (or ob itself)."""
    top = ob
    p = ob.parent if ob is not None else None
    while p is not None:
        if is_group(p):
            top = p
        p = p.parent
    return top


def with_descendants(obs):
    out, seen = [], set()

    def add(o):
        if o.name in seen:
            return
        seen.add(o.name)
        out.append(o)
        for c in o.children:
            add(c)

    for o in obs:
        add(o)
    return out


def _link_like(ob, ref):
    cols = list(ref.users_collection) or [bpy.context.scene.collection]
    for c in cols:
        if ob.name not in c.objects:
            c.objects.link(ob)


def make_group(obs):
    roots = []
    names = {o.name for o in obs}
    for o in obs:
        p, inside = o.parent, False
        while p is not None:
            if p.name in names:
                inside = True
                break
            p = p.parent
        if not inside:
            roots.append(o)
    if len(roots) < 2:
        return None
    from mathutils import Vector

    pts = [o.matrix_world.translation for o in roots]
    center = sum(pts, Vector()) / len(pts)
    g = bpy.data.objects.new(PREFIX, None)
    g.empty_display_type = "PLAIN_AXES"
    g.empty_display_size = 0.02
    g["vr_studio_group"] = True
    g.location = center
    _link_like(g, roots[0])
    bpy.context.view_layer.update()
    inv = g.matrix_world.inverted()
    for o in roots:
        mw = o.matrix_world.copy()
        o.parent = g
        o.matrix_parent_inverse = inv
        o.matrix_world = mw
    for o in bpy.context.view_layer.objects:
        if o.select_get():
            o.select_set(False)
    g.select_set(True)
    bpy.context.view_layer.objects.active = g
    return g


def ungroup(g):
    kids = list(g.children)
    for c in kids:
        mw = c.matrix_world.copy()
        c.parent = g.parent
        if g.parent is not None:
            c.matrix_parent_inverse = g.parent.matrix_world.inverted()
        c.matrix_world = mw
    for o in bpy.context.view_layer.objects:
        if o.select_get():
            o.select_set(False)
    for c in kids:
        c.select_set(True)
    if kids:
        bpy.context.view_layer.objects.active = kids[0]
    bpy.data.objects.remove(g, do_unlink=True)
    return kids


def duplicate_group(g):
    """Copy a group with all its members; returns the new group (placed where g is)."""
    mapping = {}
    for o in with_descendants([g]):
        c = o.copy()
        if o.data is not None:
            c.data = o.data.copy()
        if c.animation_data and c.animation_data.action:
            c.animation_data.action = None
        _link_like(c, o)
        mapping[o.name] = c
    for name, c in mapping.items():
        src = bpy.data.objects[name]
        if src.parent is not None and src.parent.name in mapping:
            c.parent = mapping[src.parent.name]
            c.matrix_parent_inverse = src.matrix_parent_inverse.copy()
    return mapping[g.name]


def toggle(targets):
    """Group / ungroup. Returns a short message."""
    roots = []
    for o in targets:
        r = group_root(o)
        if r not in roots:
            roots.append(r)
    if len(roots) == 1 and is_group(roots[0]):
        kids = ungroup(roots[0])
        msg = f"Ungrouped ({len(kids)})"
    elif len(roots) >= 2:
        g = make_group(roots)
        msg = f"Grouped ({len(roots)})" if g else "Nothing to group"
        if g is not None:
            _share_pudding(g)
    else:
        return "Select 2+ to group"
    try:
        from . import jiggle

        jiggle.refresh()
    except Exception:
        pass
    try:
        bpy.ops.ed.undo_push(message=f"VR {msg}")
    except Exception:
        pass
    return msg


def _share_pudding(g):
    """Grouping a pudding with other things: the whole group becomes one pudding."""
    try:
        from . import jiggle

        members = [o for o in with_descendants([g]) if o.type in jiggle.SUPPORTED]
        lv = max((jiggle.level(o) for o in members), default=0)
        if lv:
            for o in members:
                if jiggle.level(o) != lv:
                    jiggle.make_jiggly(o, lv)
    except Exception as e:
        print(f"[vr_studio] group pudding: {e}")


def _targets():
    from . import grab

    held = grab.held_objects()
    if held:
        return held
    vl = bpy.context.view_layer
    ob = vl.objects.active
    if ob is not None and ob.mode != "OBJECT":
        return []
    return [o for o in vl.objects if o.select_get()]


def _haptic(kind):
    try:
        from bl_xr.utils import apply_haptic_feedback

        apply_haptic_feedback(hand="alt", type=kind)
    except Exception:
        pass


def on_x_start(self, event_name, event):
    _x["down_at"] = time.time()
    _x["trigger_used"] = False


def on_x_end(self, event_name, event):
    t0 = _x["down_at"]
    _x["down_at"] = None
    if t0 is None or _x["trigger_used"] or time.time() - t0 > TAP_SECONDS:
        return  # a hold = Freebird's "select while held"
    try:
        targets = _targets()
        msg = toggle(targets)
        from .grab import debug

        debug(f"X tap on {[o.name for o in targets]}: {msg}")
        _haptic("SHORT_STRONG" if not msg.startswith(("Select", "Nothing")) else "TINY_LIGHT")
    except Exception as e:
        import traceback

        print(f"[vr_studio] group failed: {e}\n{traceback.format_exc()}")


def watch_trigger():
    """Every frame: a trigger used while X is held means it was a select, not a tap."""
    if _x["down_at"] is None:
        return
    try:
        from bl_xr.events.make_events import controller

        if controller.input_state.get("trigger_main_press", False):
            _x["trigger_used"] = True
    except Exception:
        pass


def enable():
    from bl_xr import root

    root.add_event_listener("button_a_alt_start", on_x_start)
    root.add_event_listener("button_a_alt_end", on_x_end)


def disable():
    from bl_xr import root

    root.remove_event_listener("button_a_alt_start", on_x_start)
    root.remove_event_listener("button_a_alt_end", on_x_end)
