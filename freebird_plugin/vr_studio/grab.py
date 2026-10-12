# SPDX-License-Identifier: GPL-2.0-or-later
"""Easy grab (LOCAL: only this person's hands, never synced).

Freebird v2.15 grabs an object only when the controller tip is within 1 cm of its *surface*
(bl_xr.selection_size = 0.01), so a hand inside a big object, or a few cm away, grabs nothing.
Gravity Sketch feels easier because the grab reach is bigger and "hand inside = grab".

The grab sphere sits on the hand (grip pose, middle finger) like Gravity Sketch, is always
shown (faint white; red when a squeeze would grab something), and while the grab button
(squeeze) is held in Object Mode, this swaps Freebird's
bl_xr.intersections.get_intersecting_objects for one that
  * reaches REACH_CM (scaled with the world like Freebird's own cursor),
  * counts the hand as touching when it is inside a closed mesh,
  * returns only one object: the nearest surface within reach; with none in reach, the
    smallest object the hand is inside (so a room / big shell never steals the grab).
Everything else (trigger / select tool / Edit & Pose Mode / gizmos) goes to Freebird's own
function untouched. Freebird's files are never edited: the swap is done at runtime, undone on
unregister, and if anything unexpected happens it falls back to Freebird's function.
The transform itself is Freebird's, so FreebirdCollabo syncs the move as usual.
"""

import json
import os

CHOICES = (0, 3, 5, 8)  # cm; 0 = OFF (Freebird's own grab)
DEFAULT_CM = 5
SETTINGS_PATH = os.path.join(os.path.expanduser("~"), ".freebird", "vr_studio_settings.json")

DEBUG_LOG = os.path.join(os.path.expanduser("~"), ".freebird", "vr_studio_debug.log")

_orig = None
_reach_cm = None


def debug(msg):
    """Console + ~/.freebird/vr_studio_debug.log (kept under ~1 MB), to see what happened in VR."""
    import time

    line = f"{time.strftime('%H:%M:%S')} {msg}"
    print(f"[vr_studio] {msg}")
    try:
        if os.path.exists(DEBUG_LOG) and os.path.getsize(DEBUG_LOG) > 1_000_000:
            os.replace(DEBUG_LOG, DEBUG_LOG + ".old")
        with open(DEBUG_LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


# -- settings (local file, per person) -------------------------------------
def get_reach_cm():
    global _reach_cm
    if _reach_cm is None:
        _reach_cm = DEFAULT_CM
        try:
            with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
                v = json.load(f).get("grab_reach_cm", DEFAULT_CM)
            if isinstance(v, (int, float)) and 0 <= v <= 30:
                _reach_cm = v
        except Exception:
            pass
    return _reach_cm


def set_reach_cm(cm, save=True):
    global _reach_cm
    if not isinstance(cm, (int, float)) or cm < 0:
        return
    _reach_cm = round(cm, 2)
    if not save:
        return
    try:
        data = {}
        if os.path.exists(SETTINGS_PATH):
            with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
        data["grab_reach_cm"] = _reach_cm
        os.makedirs(os.path.dirname(SETTINGS_PATH), exist_ok=True)
        with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"[vr_studio] could not save grab setting: {e}")


# -- geometry ----------------------------------------------------------------
def _mesh_distance(ob, center):
    """(distance from the surface in world units, inside?) or None when not applicable."""
    if ob.type not in ("MESH", "CURVE", "FONT", "SURFACE", "META"):
        return None
    if ob.type == "MESH" and len(ob.data.polygons) == 0:
        return None
    m = ob.matrix_world
    local = m.inverted() @ center
    ok, loc, normal, _ = ob.closest_point_on_mesh(local)
    if not ok:
        return None
    d = ((m @ loc) - center).length
    inside = ob.type == "MESH" and (local - loc).dot(normal) < 0.0
    return d, inside


def _near_bounds(ob, center, reach):
    """Is `center` within `reach` of the object's bounding box? (object space, scale-aware)
    Objects without a box (empties, lights ...) always pass to Freebird's own test."""
    try:
        bb = ob.bound_box
        xs = [c[0] for c in bb]
        ys = [c[1] for c in bb]
        zs = [c[2] for c in bb]
        if max(xs) - min(xs) == 0 and max(ys) - min(ys) == 0 and max(zs) - min(zs) == 0:
            return True
        local = ob.matrix_world.inverted() @ center
        s = ob.matrix_world.to_scale()
        smin = min(abs(s.x), abs(s.y), abs(s.z)) or 1e-6
        r = reach / smin
        return (min(xs) - r <= local.x <= max(xs) + r and min(ys) - r <= local.y <= max(ys) + r
                and min(zs) - r <= local.z <= max(zs) + r)
    except Exception:
        return True


def _size(ob):
    dims = ob.dimensions
    return dims.x * dims.y * dims.z


def find_grab_targets(center, reach, fallback_intersects):
    """Everything the grab sphere touches (Gravity Sketch: grab all of it), nearest first.
    A member of a group stands for its whole group. With nothing touching, the smallest
    object the hand is deep inside (so a room / big shell never steals the grab)."""
    import bpy

    from .groups import group_root

    touching = []  # (rank, distance, ob)
    enclosing = []  # (size, ob)
    for ob in bpy.context.view_layer.objects:
        if not ob.visible_get() or ob.hide_select:
            continue
        if getattr(ob, "mode", "OBJECT") != "OBJECT":
            continue
        if not _near_bounds(ob, center, reach):
            continue  # cheap box test first: most objects are far from the hand
        try:
            r = _mesh_distance(ob, center)
        except Exception:
            r = None
        if r is None:  # lights, cameras, empties, armatures, edge-only meshes: Freebird's test
            try:
                hit = fallback_intersects(ob, center, reach)
            except Exception:
                hit = None
            if hit:
                touching.append((1, 0.0, ob))
            continue
        d, inside = r
        if d <= reach:
            touching.append((0, d, ob))
        elif inside:
            enclosing.append((_size(ob), ob))
    if touching:
        picked = [ob for _r, _d, ob in sorted(touching, key=lambda t: t[:2])]
    elif enclosing:
        picked = [min(enclosing, key=lambda t: t[0])[1]]
    else:
        return []
    out = []
    for ob in picked:
        root = group_root(ob)
        if root not in out:
            out.append(root)
    return out


def find_grab_target(center, reach, fallback_intersects):
    """The nearest of find_grab_targets(), or None."""
    obs = find_grab_targets(center, reach, fallback_intersects)
    return obs[0] if obs else None


def grab_center():
    """Gravity Sketch style: the grab sphere sits on the hand (grip pose, around the middle
    finger), not on the controller tip where Freebird's laser starts."""
    from bl_xr import xr_session

    return xr_session.controller_main_grip_position


def edit_elements(active, reach):
    """Vertices / edges / faces (Edit Mode) or bones (Pose Mode) inside the grab sphere."""
    import bl_xr
    from bl_xr.utils import intersects

    return intersects(active, grab_center(), bl_xr.selection_shape, reach) or []


def _fallback_intersects(ob, c, size):
    import bl_xr
    from bl_xr.utils import intersects

    return intersects(ob, c, bl_xr.selection_shape, size)


_prof = {"t": 0.0, "n": 0, "max": 0.0, "since": None}
PROFILE_EVERY = 10.0  # seconds


def _profile(dt):
    """Log VR Studio's own per-frame cost every 10 s (to see if it is what makes VR heavy)."""
    import time

    p = _prof
    p["t"] += dt
    p["n"] += 1
    p["max"] = max(p["max"], dt)
    now = time.time()
    if p["since"] is None:
        p["since"] = now
    elif now - p["since"] >= PROFILE_EVERY and p["n"]:
        try:
            import bpy

            n_obj = len(bpy.data.objects)
        except Exception:
            n_obj = "?"
        debug(f"perf: VR Studio {p['t'] / p['n'] * 1000:.2f} ms/frame avg, {p['max'] * 1000:.1f} ms max, "
              f"{p['n'] / (now - p['since']):.0f} updates/s, {n_obj} objects")
        p.update(t=0.0, n=0, max=0.0, since=now)


def _outline(names):
    try:
        from bl_xr import xr_session

        from . import outline

        outline.set_targets(names)
        outline.update(xr_session.viewer_scale)
    except Exception as e:
        print(f"[vr_studio] outline: {e}")


# -- always-visible grab sphere ---------------------------------------------
SPHERE_IDLE = ((1.0, 1.0, 1.0), 0.12)  # faint white ghost
SPHERE_TOUCH = ((1.0, 0.15, 0.15), 0.35)  # red: squeeze now grabs something
HOVER_EVERY = 6  # frames between "what would I grab" checks
EDIT_HOVER_EVERY = 12  # Edit Mode: the vertex test walks every vertex in Python
EDIT_HOVER_MAX_VERTS = 20000  # bigger meshes: no red-sphere preview in Edit Mode (grab still works)

_sphere = None


def _make_sphere():
    from bl_xr import Node, Sphere

    holder = Node(id="vr_studio_grab_sphere", intersects=None, style={"fixed_scale": True})
    ball = Sphere(radius=1, intersects=None)
    ball.style["color"], ball.style["opacity"] = SPHERE_IDLE
    holder.append_child(ball)
    holder._ball = ball
    holder._frame = 0
    holder._touch = None

    def update():
        import time as _t

        t0 = _t.perf_counter()
        try:
            _update()
        finally:
            _profile(_t.perf_counter() - t0)

    def _update():
        try:
            import bpy
            from bl_xr import xr_session

            if not xr_session.is_running:
                return
            if not get_reach_cm():  # GRAB OFF = everything back to plain Freebird
                _gs_mode(False)
                ball.style["visible"] = False
                _outline([])
                return
            _gs_mode(True)
            _jiggle_step()
            if _reselect["frames"] > 0:  # Freebird restores its old selection on release too
                _reselect["frames"] -= 1
                _apply_selection(_reselect["names"], log=_reselect["frames"] == 0)
            squeezing = _squeeze_held()
            if squeezing and not _session.get("was_squeezing") and not held_objects():
                _start_panel_grip(get_reach_cm() / 100.0)
            _session["was_squeezing"] = squeezing
            if not squeezing:
                if _session["started"]:
                    _select_last_held()
                _session["started"] = _session["on_object"] = False
                _session["last_held"] = []
            else:
                names = [o.name for o in held_objects()]
                if names:
                    _session["last_held"] = names
            ensure_b_hook()
            ensure_trigger_hook()
            cm = get_reach_cm()
            active = bpy.context.view_layer.objects.active
            mode = getattr(active, "mode", "OBJECT")
            show = bool(cm) and mode in ("OBJECT", "EDIT", "POSE")
            _check_clone_trigger()
            try:
                from . import controls

                controls.ensure()
                controls.update_labels(bool(held_objects()))
                from . import brush

                brush.ensure()
                brush.update()
            except Exception as e:
                if holder._frame % 300 == 0:
                    print(f"[vr_studio] controls: {e}")
            from . import groups

            groups.watch_trigger()
            ball.style["visible"] = show
            if not show:
                _outline([])
                return
            holder.position = grab_center()
            ball.scale = cm / 100.0
            holder._frame += 1
            held = held_objects()
            if mode != "OBJECT":  # Edit / Pose: red when vertices / bones are inside, no outline
                if holder._frame % EDIT_HOVER_EVERY == 0:
                    reach = cm / 100.0 * xr_session.viewer_scale
                    try:
                        big = active.type == "MESH" and len(active.data.vertices) > EDIT_HOVER_MAX_VERTS
                        touch = _squeeze_held() or (not big and bool(edit_elements(active, reach)))
                    except Exception:
                        touch = False
                    if touch != holder._touch:
                        holder._touch = touch
                        ball.style["color"], ball.style["opacity"] = SPHERE_TOUCH if touch else SPHERE_IDLE
                _outline([])
                return
            if holder._frame % HOVER_EVERY == 0:
                reach = cm / 100.0 * xr_session.viewer_scale
                on_panel = arranging() or panel_under_grip(cm / 100.0) is not None
                targets = [] if on_panel else find_grab_targets(grab_center(), reach, _fallback_intersects)
                holder._hover = [t.name for t in targets]
                touch = bool(targets) or bool(held) or on_panel
                if touch != holder._touch:
                    holder._touch = touch
                    ball.style["color"], ball.style["opacity"] = SPHERE_TOUCH if touch else SPHERE_IDLE
            from .groups import with_descendants

            if held:
                shown = []  # holding it: no outline in the way (the red sphere says you hold something)
            else:
                shown = [bpy.data.objects[n] for n in getattr(holder, "_hover", None) or []
                         if n in bpy.data.objects]
            _outline([o.name for o in with_descendants(shown)])
        except Exception as e:
            if holder._frame % 300 == 0:
                print(f"[vr_studio] grab sphere: {e}")

    holder.update = update
    return holder


_hand = {"p": None, "t": None}


def _jiggle_step():
    """Puddinger jiggle: feed it the grab sphere (position, velocity, size) every frame."""
    import time

    try:
        from bl_xr import xr_session
        from mathutils import Vector

        from . import jiggle

        p = Vector(grab_center())
        now = time.perf_counter()
        vel = None
        if _hand["p"] is not None and now > _hand["t"]:
            vel = (p - _hand["p"]) / (now - _hand["t"])
        _hand["p"], _hand["t"] = p, now
        reach = (get_reach_cm() or 3) / 100.0 * xr_session.viewer_scale
        held = {o.name for o in held_objects()}
        jiggle.update(p, vel, reach, held)
    except Exception as e:
        if int(time.time()) % 10 == 0:
            print(f"[vr_studio] jiggle: {e}")


_gs = {"on": None}


def _gs_mode(on):
    """Gravity Sketch style controls on/off (GRAB panel OFF = plain Freebird, for comparing)."""
    if _gs["on"] == on:
        return
    _gs["on"] = on
    from . import brush, controls, groups

    if on:
        install()
        groups.enable()
        controls.set_labels_active(True)
    else:
        uninstall()
        remove_b_hook()
        remove_trigger_hook()
        controls.uninstall_hooks()
        controls.set_labels_active(False)
        brush.uninstall()
        groups.disable()
    debug(f"Gravity Sketch style controls {'ON' if on else 'OFF (plain Freebird)'}")


def show_sphere():
    global _sphere
    try:
        from bl_xr import root

        if _sphere is None:
            _sphere = _make_sphere()
        if _sphere.parent is None:
            root.append_child(_sphere)
        from . import groups, outline

        outline.enable()
        groups.enable()
        from . import controls

        controls.build_labels()
    except Exception as e:
        print(f"[vr_studio] grab sphere not shown: {e}")


def hide_sphere():
    if _sphere is not None and _sphere.parent is not None:
        _sphere.parent.remove_child(_sphere)
    remove_b_hook()
    remove_trigger_hook()
    try:
        from . import groups, outline

        outline.disable()
        groups.disable()
        from . import brush, controls

        controls.uninstall()
        brush.uninstall()
        _gs["on"] = None
    except Exception:
        pass


# -- runtime swap ------------------------------------------------------------
def _is_grabbing(intersections):
    from bl_xr.events.make_events import controller

    st = controller.input_state
    return getattr(intersections, "allow_squeeze", False) and st.get("squeeze_main_press", False)


def _make_wrapper(intersections, orig):
    def get_intersecting_objects(pointer_location):
        result = _grab_query(intersections, orig, pointer_location)
        try:
            if _is_grabbing(intersections) and not _session["started"]:
                _session["started"] = True  # first frame of this squeeze: did it land on something?
                objects = result[0] if result else None
                _session["on_object"] = bool(objects)
        except Exception:
            pass
        return result

    get_intersecting_objects._vr_studio_orig = orig
    return get_intersecting_objects


def _studio_area():
    import sys

    return getattr(sys.modules.get(__package__), "_area", None)


def panel_under_grip(reach):
    area = _studio_area()
    if area is None:
        return None
    try:
        return area.panel_at(grab_center(), reach)
    except Exception:
        return None


def arranging():
    area = _studio_area()
    return area is not None and area._dragging is not None


def _start_panel_grip(reach):
    """Grip on a VR Studio panel: move the panel (and grab nothing in the scene)."""
    if arranging():
        return True
    section = panel_under_grip(reach)
    if section is None:
        return False
    _studio_area().start_arrange(section, source="grip")
    debug(f"panel grip: {section.title}")
    return True


def _grab_query(intersections, orig, pointer_location):
    try:
        from bl_xr import xr_session as _xs

        if _is_grabbing(intersections) and get_reach_cm():
            if _start_panel_grip(get_reach_cm() / 100.0):
                return [], None
    except Exception:
        pass
    try:
        import bpy
        from bl_xr import xr_session

        cm = get_reach_cm()
        active = bpy.context.view_layer.objects.active
        mode = getattr(active, "mode", "OBJECT")
        if cm and mode == "OBJECT" and _is_grabbing(intersections):
            reach = cm / 100.0 * xr_session.viewer_scale
            obs = find_grab_targets(grab_center(), reach, _fallback_intersects)
            if obs:
                debug(f"grab {[o.name for o in obs]}")
            return obs, None
        if cm and mode in ("EDIT", "POSE") and _is_grabbing(intersections):
            # Edit / Pose Mode: Freebird's own vertex / edge / face / bone test, from the hand
            # sphere with its size (same result shape as Freebird: [object], {elements})
            reach = cm / 100.0 * xr_session.viewer_scale
            elements = edit_elements(active, reach)
            if elements:
                debug(f"grab {len(elements)} {mode.lower()} elements of {active.name}")
                return [active], set(elements)
            return [], None
    except Exception as e:
        print(f"[vr_studio] easy grab fell back to Freebird: {e}")
    return orig(pointer_location)


# -- squeeze + B = delete (Gravity Sketch) ------------------------------------
# Freebird uses B (main hand) for its quick tools. While you hold something with the grip,
# B deletes what you hold instead; with empty hands B is Freebird's quick tools as before.
_session = {"started": False, "on_object": False, "last_held": []}


_reselect = {"names": [], "frames": 0}


def _select_last_held():
    """Gravity Sketch: what you just grabbed stays selected (ready for X = group, Color ...)."""
    names = list(_session.get("last_held") or [])
    if names:
        _reselect["names"], _reselect["frames"] = names, 4


def _apply_selection(names, log=False):
    import bpy

    names = [n for n in names if n in bpy.data.objects]
    if not names:
        return
    try:
        vl = bpy.context.view_layer
        for o in vl.objects:
            if o.select_get() and o.name not in names:
                o.select_set(False)
        for n in names:
            bpy.data.objects[n].select_set(True)
        vl.objects.active = bpy.data.objects[names[0]]
        if log:
            debug(f"selected after grab {names}")
    except Exception as e:
        debug(f"select after grab failed: {e}")
_b_consumed = False
_qt_patched = []  # (event name, callback, original options) to restore on uninstall
_fallback_b = False


def _squeeze_held():
    from bl_xr.events.make_events import controller

    return controller.input_state.get("squeeze_main_press", False)


def _alive(ob):
    try:
        ob.name
        return True
    except Exception:
        return False


def held_objects():
    """Objects in your grip right now (Object Mode), or [] when the hand is empty."""
    import bpy
    from bpy.types import Object

    if not _squeeze_held():
        return []
    try:
        from freebird.tools.transform_common import T
    except Exception:
        return []
    if not _session["on_object"]:
        try:  # Freebird's own record of "an object is in the grip"
            from freebird.tools import clone

            if not clone.object_being_held:
                return []
        except Exception:
            return []
    ob = T.get("object_to_transform")
    if ob is None or not _alive(ob) or getattr(ob, "mode", "OBJECT") != "OBJECT":
        return []
    elements = T.get("transform_elements") or {ob}
    obs = [e for e in elements if isinstance(e, Object) and _alive(e)]
    if ob not in obs:
        obs.append(ob)
    names = {o.name for o in obs}
    return [bpy.data.objects[n] for n in names if n in bpy.data.objects]


def delete_held():
    """Delete what the grip holds. Returns the number of deleted objects."""
    import bpy

    from .groups import with_descendants

    obs = held_objects()
    if not obs:
        return 0
    obs = with_descendants(obs)  # a group goes with all its members
    names = [o.name for o in obs]
    try:  # Freebird is mid-grab: end it cleanly, its drag events lose their (deleted) targets
        from freebird.tools.transform_common import reset_transform_state
        from freebird.utils import enable_bounds_check

        reset_transform_state()
        enable_bounds_check()
    except Exception as e:
        print(f"[vr_studio] delete: could not reset Freebird's grab: {e}")
    for ob in obs:
        try:
            bpy.data.objects.remove(ob, do_unlink=True)
        except Exception as e:
            print(f"[vr_studio] delete {ob}: {e}")
    _session["on_object"] = False
    try:
        bpy.ops.ed.undo_push(message="VR delete")
    except Exception:
        pass
    try:
        from bl_xr.utils import apply_haptic_feedback

        apply_haptic_feedback(hand="main", type="SHORT_STRONG")
    except Exception:
        pass
    debug(f"deleted {names}")
    return len(names)


def _active_mode():
    import bpy

    return getattr(bpy.context.view_layer.objects.active, "mode", "OBJECT")


def _b_start_filter(prev):
    def filt(self, event_name, event):
        global _b_consumed
        if held_objects():
            delete_held()
        elif _squeeze_held() and _active_mode() != "OBJECT":
            debug("B while holding vertices / bones: ignored (no undo mid-edit)")
        else:  # Gravity Sketch: B with an empty hand = undo (instead of Freebird's quick tools)
            from . import controls

            controls.undo()
        _b_consumed = True
        return False

    return filt


def _b_end_filter(prev):
    def filt(self, event_name, event):
        global _b_consumed
        if _b_consumed:
            _b_consumed = False
            return False
        return prev(self, event_name, event) if prev else True

    return filt


def _on_b_start_fallback(self, event_name, event):  # quick tools not found
    if held_objects():
        delete_held()
    else:
        from . import controls

        controls.undo()


def ensure_b_hook():
    """Put the 'holding something?' check in front of Freebird's quick-tools B listeners.
    Cheap; called every frame because Freebird re-adds its listeners when VR restarts."""
    global _fallback_b
    try:
        from bl_xr import root
        from freebird.ui import quicktools as qt
    except Exception:
        qt = None
        from bl_xr import root
    listeners = getattr(root, "event_listeners", {})
    found = False
    for name, cb_name, make in (("button_b_main_start", "on_qt_button_start", _b_start_filter),
                                ("button_b_main_end", "on_qt_button_end", _b_end_filter)):
        cb = getattr(qt, cb_name, None) if qt else None
        entries = listeners.get(name, [])
        for i in range(len(entries) - 1, -1, -1):
            l, opts = entries[i]
            if cb is not None and l is cb:
                found = True
                if not opts.get("_vr_studio") and any(l2 is l and o2.get("_vr_studio") for l2, o2 in entries):
                    del entries[i]  # re-added by Freebird after we wrapped it
                    continue
                if not opts.get("_vr_studio"):
                    new = dict(opts)
                    new["filter_fn"] = make(opts.get("filter_fn"))
                    new["_vr_studio"] = True
                    entries[i] = (l, new)
                    _qt_patched.append((name, l, opts))
    if not found and not _fallback_b:
        root.add_event_listener("button_b_main_start", _on_b_start_fallback)
        _fallback_b = True
    elif found and _fallback_b:
        root.remove_event_listener("button_b_main_start", _on_b_start_fallback)
        _fallback_b = False


def remove_b_hook():
    global _fallback_b
    try:
        from bl_xr import root
    except Exception:
        return
    listeners = getattr(root, "event_listeners", {})
    for name, cb, opts in _qt_patched:
        entries = listeners.get(name, [])
        for i, (l, o) in enumerate(entries):
            if l is cb and o.get("_vr_studio"):
                entries[i] = (l, opts)
    _qt_patched.clear()
    if _fallback_b:
        root.remove_event_listener("button_b_main_start", _on_b_start_fallback)
        _fallback_b = False


def install():
    """Swap in the easy-grab test. Safe to call twice."""
    global _orig
    try:
        from bl_xr import intersections
    except Exception as e:
        print(f"[vr_studio] easy grab not available (bl_xr.intersections): {e}")
        return False
    cur = getattr(intersections, "get_intersecting_objects", None)
    if cur is None:
        print("[vr_studio] easy grab not available: Freebird changed get_intersecting_objects")
        return False
    if hasattr(cur, "_vr_studio_orig"):
        return True
    _orig = cur
    intersections.get_intersecting_objects = _make_wrapper(intersections, cur)
    print(f"[vr_studio] easy grab on ({get_reach_cm()} cm)")
    return True


def uninstall():
    global _orig
    try:
        from bl_xr import intersections
    except Exception:
        return
    cur = getattr(intersections, "get_intersecting_objects", None)
    orig = getattr(cur, "_vr_studio_orig", None)
    if orig is not None:
        intersections.get_intersecting_objects = orig
    _orig = None


# -- squeeze + trigger = duplicate (Gravity Sketch) -----------------------------
# Holding something with the grip and pulling the trigger runs Freebird's own clone (the same
# one as its A button): the copy stays in your hand, the original stays where it was.
# While that trigger is down, Freebird's trigger tools (pen, select ...) don't see it.
_clone_trigger = False
_trigger_was_down = False
_trigger_patched = []  # (owner, event name, callback, original options)
TRIGGER_EVENTS = ("trigger_main_start", "trigger_main_press", "trigger_main_end", "click",
                  "drag_start", "drag", "drag_end")


def _trigger_down():
    from bl_xr.events.make_events import controller

    return controller.input_state.get("trigger_main_press", False)


def _check_clone_trigger():
    """Every frame: a trigger press that starts while the grip holds something = clone."""
    global _clone_trigger, _trigger_was_down
    down = _trigger_down()
    if down and not _trigger_was_down:
        if held_objects():
            _clone_trigger = True
            clone_held()
        elif _squeeze_held():
            debug(f"trigger while squeezing but nothing held (session={_session})")
    if not down:
        _clone_trigger = False
    _trigger_was_down = down


def _clone_all(held):
    """Copy what the grip holds (groups with all members); the copies stay in the hand.
    Freebird's transform listens to "fb.clone" during a grab and switches to the copies."""
    import bpy
    from bl_xr import root

    from .groups import duplicate_group, group_root, is_group

    roots = []
    for o in held:
        r = group_root(o)
        if r not in roots:
            roots.append(r)
    copies = []
    for r in roots:
        if is_group(r):
            c = duplicate_group(r)
        else:
            c = r.copy()
            if r.data is not None:
                c.data = r.data.copy()
            if c.animation_data and c.animation_data.action:
                c.animation_data.action = None
            for col in list(r.users_collection) or [bpy.context.scene.collection]:
                col.objects.link(c)
        r.select_set(False)
        c.select_set(True)
        copies.append(c)
    bpy.context.view_layer.objects.active = copies[0]
    try:
        from freebird.tools import clone

        clone.object_being_held = copies[0].name
        clone.clone_state = "CLONED"
    except Exception:
        pass
    root.dispatch_event("fb.clone", copies)
    bpy.ops.ed.undo_push(message="clone")
    return copies


def clone_held():
    held = held_objects()
    if not held:
        debug("duplicate: nothing in the grip")
        return
    try:
        copies = _clone_all(held)
        try:
            from bl_xr.utils import apply_haptic_feedback

            apply_haptic_feedback(hand="main", type="SHORT_LIGHT")
        except Exception:
            pass
        debug(f"duplicated {[o.name for o in held]} -> {[c.name for c in copies]}")
    except Exception as e:
        import traceback

        debug(f"duplicate failed: {e}\n{traceback.format_exc()}")


def _is_trigger_event(event_name, event):
    if event_name.startswith("trigger_main"):
        return True
    return getattr(event, "button_name", None) == "trigger_main"


def _trigger_filter(prev):
    def filt(self, event_name, event):
        if (_clone_trigger or (_trigger_down() and held_objects())) and _is_trigger_event(event_name, event):
            return False
        return prev(self, event_name, event) if prev else True

    return filt


def _owners():
    from bl_xr import root
    from bpy.types import Object

    return (root, Object)


def ensure_trigger_hook():
    """Wrap every trigger listener (root and Object) once with the 'cloning?' check.
    Called every frame: Freebird adds/removes tool listeners when you switch tools."""
    for owner in _owners():
        listeners = getattr(owner, "event_listeners", {})
        for name in TRIGGER_EVENTS:
            entries = listeners.get(name, [])
            for i in range(len(entries) - 1, -1, -1):
                l, opts = entries[i]
                if opts.get("_vr_studio_trigger"):
                    continue
                if any(l2 is l and o2.get("_vr_studio_trigger") for l2, o2 in entries):
                    del entries[i]  # Freebird re-added a listener we had already wrapped
                    continue
                new = dict(opts)
                new["filter_fn"] = _trigger_filter(opts.get("filter_fn"))
                new["_vr_studio_trigger"] = True
                if "_vr_studio" in opts:
                    new["_vr_studio"] = opts["_vr_studio"]
                entries[i] = (l, new)
                _trigger_patched.append((owner, name, l, opts))


def remove_trigger_hook():
    for owner, name, cb, opts in _trigger_patched:
        entries = getattr(owner, "event_listeners", {}).get(name, [])
        for i, (l, o) in enumerate(entries):
            if l is cb and o.get("_vr_studio_trigger"):
                entries[i] = (l, opts)
    _trigger_patched.clear()
