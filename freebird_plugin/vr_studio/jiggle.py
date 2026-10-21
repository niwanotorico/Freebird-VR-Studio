# SPDX-License-Identifier: GPL-2.0-or-later
"""Pudding: Puddinger's "ぷるぷる", ported from Puddinger/01_pudding/pudding_jiggle.py.

Same feel as the Puddinger pudding: a probe near the top follows the object; every change of
its velocity (moving, turning, stopping) kicks a stiff, lightly damped 3-axis spring
(k 240, c 7.5, 240 Hz sub-steps). The spring's offset drives two deformations taken from the
Puddinger pudding's shape keys:
  * Wobble: the top slides sideways, weighted (height from the base)^2, so the base stays put
  * Squish: shorter (z * 0.76) and fatter towards the top (xy * 1.2)
Here they are a Geometry Nodes modifier instead of shape keys, so any mesh / stroke works, the
real mesh is never touched, and FreebirdCollabo (which syncs meshes, not these modifiers) sends
nothing extra. Everything is scaled to the object's height, so big and small things wobble alike.
The grab sphere bumping into a pudding kicks it too. A VR group is one pudding: every member
deforms in the group's space around the group's base.
Levels 1/2/3 = Puddinger's "Jiggle strength" 1 (normal) / 2 / 3.
"""

import math
import time

import bpy
from mathutils import Matrix, Vector

PROP = "puddinger_jiggle"
MOD = "Puddinger Jiggle"
OLD_MODS = ("Puddinger Squash", "Puddinger Lean X", "Puddinger Lean Y")
SUPPORTED = ("MESH", "CURVE", "FONT", "SURFACE")

LEVELS = {
    # gain = Puddinger's Jiggle strength; room = how far it may swing (1 = Puddinger's pudding,
    # whose top moves at most 18.7 % of its height)
    1: {"name": "Soft", "gain": 1.2, "room": 1.5},
    2: {"name": "Wobbly", "gain": 2.0, "room": 2.0},
    3: {"name": "Jelly", "gain": 3.0, "room": 2.6},
}

# Puddinger pudding_jiggle.py, for a pudding 0.134 m tall
REF_H = 0.134
PROBE = 0.10 / REF_H  # probe height (fraction of the height)
K, C = 240.0, 7.5
SUB_DT = 1.0 / 240.0
LIMIT, BOUNCE = 0.034, 0.25
KICK, MAX_DV = 0.6, 2.0
WOBBLE_FULL, WOBBLE_TOP = 0.025, 0.025 / REF_H  # shape key value 1 = top moved 18.7 % of height
SQUISH_FULL = 0.032
JUMP = 0.35  # probe jumps more than this (in pudding units) in one frame: teleport, no wobble
TOUCH_SPEED = 0.08  # m/s: slower hands just rest on it
TOUCH_GAIN = 0.6
REST = 1e-5

_state = {}
_list = {"bodies": {}, "t": 0.0}
_clock = {"t": None}
_geo = {}


# -- the deformer (Geometry Nodes) ----------------------------------------------------------------
GROUP = "Puddinger Jiggle v1"


def node_group():
    ng = bpy.data.node_groups.get(GROUP)
    if ng is not None:
        return ng
    ng = bpy.data.node_groups.new(GROUP, "GeometryNodeTree")
    io = ng.interface
    io.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    io.new_socket("Frame", in_out="INPUT", socket_type="NodeSocketObject")
    io.new_socket("Use Frame", in_out="INPUT", socket_type="NodeSocketBool")
    io.new_socket("Base", in_out="INPUT", socket_type="NodeSocketFloat")
    s = io.new_socket("Height", in_out="INPUT", socket_type="NodeSocketFloat"); s.default_value = 1.0
    io.new_socket("Center", in_out="INPUT", socket_type="NodeSocketVector")
    io.new_socket("Wobble", in_out="INPUT", socket_type="NodeSocketVector")
    io.new_socket("Squish", in_out="INPUT", socket_type="NodeSocketFloat")
    io.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    N, L = ng.nodes, ng.links
    gi = N.new("NodeGroupInput"); go = N.new("NodeGroupOutput")

    def math(op, a, b=None, clamp=False):
        n = N.new("ShaderNodeMath"); n.operation = op; n.use_clamp = clamp
        for i, v in enumerate((a, b)):
            if v is None:
                continue
            if isinstance(v, (int, float)):
                n.inputs[i].default_value = v
            else:
                L.new(v, n.inputs[i])
        return n.outputs[0]

    def vmath(op, a, b=None, scale=None):
        n = N.new("ShaderNodeVectorMath"); n.operation = op
        L.new(a, n.inputs[0])
        if b is not None:
            L.new(b, n.inputs[1])
        if scale is not None:
            L.new(scale, n.inputs[3]) if not isinstance(scale, (int, float)) else setattr(n.inputs[3], "default_value", scale)
        return n.outputs[0]

    info = N.new("GeometryNodeObjectInfo"); info.transform_space = "RELATIVE"
    L.new(gi.outputs["Frame"], info.inputs["Object"])
    sw = N.new("GeometryNodeSwitch"); sw.input_type = "MATRIX"
    L.new(gi.outputs["Use Frame"], sw.inputs["Switch"])
    L.new(info.outputs["Transform"], sw.inputs["True"])
    m = sw.outputs[0]
    inv = N.new("FunctionNodeInvertMatrix"); L.new(m, inv.inputs[0])
    pos = N.new("GeometryNodeInputPosition")
    tp = N.new("FunctionNodeTransformPoint"); L.new(pos.outputs[0], tp.inputs[0]); L.new(inv.outputs[0], tp.inputs[1])
    pf = tp.outputs[0]
    rel = vmath("SUBTRACT", pf, gi.outputs["Center"])
    sep = N.new("ShaderNodeSeparateXYZ"); L.new(rel, sep.inputs[0])
    sepf = N.new("ShaderNodeSeparateXYZ"); L.new(pf, sepf.inputs[0])
    zr = math("SUBTRACT", sepf.outputs["Z"], gi.outputs["Base"])
    t = math("DIVIDE", zr, gi.outputs["Height"], clamp=True)
    t2 = math("MULTIPLY", t, t)
    # wobble: the top slides sideways, the base stays (t^2 from the bottom)
    wob = vmath("SCALE", gi.outputs["Wobble"], scale=math("MULTIPLY", t2, gi.outputs["Height"]))
    # squish: shorter and fatter towards the top
    k = math("MULTIPLY", math("MULTIPLY", t, 0.20), gi.outputs["Squish"])
    sq = N.new("ShaderNodeCombineXYZ")
    L.new(math("MULTIPLY", sep.outputs["X"], k), sq.inputs[0])
    L.new(math("MULTIPLY", sep.outputs["Y"], k), sq.inputs[1])
    L.new(math("MULTIPLY", math("MULTIPLY", zr, -0.24), gi.outputs["Squish"]), sq.inputs[2])
    moved = vmath("ADD", pf, vmath("ADD", wob, sq.outputs[0]))
    back = N.new("FunctionNodeTransformPoint"); L.new(moved, back.inputs[0]); L.new(m, back.inputs[1])
    setp = N.new("GeometryNodeSetPosition")
    L.new(gi.outputs["Geometry"], setp.inputs["Geometry"])
    L.new(back.outputs[0], setp.inputs["Position"])
    L.new(setp.outputs[0], go.inputs[0])
    return ng


def sockets(ng):
    return {it.name: it.identifier for it in ng.interface.items_tree if getattr(it, "in_out", "") == "INPUT"}


def set_input(md, ident, value):
    try:
        sock = getattr(md.properties.inputs, ident)
    except AttributeError:  # Blender 4.x: modifier ID properties
        md[ident] = value
        return
    sock.value = value


def get_input(md, ident):
    try:
        return getattr(md.properties.inputs, ident).value
    except AttributeError:
        return md.get(ident)


_ids = {}


def _sock(name):
    if not _ids:
        _ids.update(sockets(node_group()))
    return _ids[name]


# -- on / off ------------------------------------------------------------------------------------
def refresh():
    """Re-read which objects / groups are puddings on the next frame (after (un)grouping)."""
    _list["t"] = 0.0


def is_jiggly(ob):
    return ob is not None and bool(ob.get(PROP))


def level(ob):
    """0 = not pudding, 1..3 (older files stored True = 1)."""
    if ob is None:
        return 0
    try:
        return max(0, min(3, int(ob.get(PROP) or 0)))
    except (TypeError, ValueError):
        return 1


def _ensure_mod(ob):
    for name in OLD_MODS:  # the first Pudding (Simple Deform) -> this one
        md = ob.modifiers.get(name)
        if md is not None:
            ob.modifiers.remove(md)
    md = ob.modifiers.get(MOD)
    if md is None or md.type != "NODES":
        md = ob.modifiers.new(MOD, "NODES")
        md.show_in_editmode = False
        md.show_expanded = False
    ng = node_group()
    if md.node_group is not ng:
        md.node_group = ng
        _ids.clear()
    return md


def anchor_stroke(ob):
    """Strokes: put the origin on the stroke's end point (where you finished drawing) and turn
    the object so its local +Z runs from there along the stroke. The bend modifiers then pin
    that end and wobble the rest like a fishing rod. Done once (visually nothing moves)."""
    from mathutils import Matrix

    if ob.get(PROP + "_anchored"):
        return
    pts = [p for sp in ob.data.splines for p in (sp.points if len(sp.points) else sp.bezier_points)]
    if len(pts) < 2:
        return
    sp = ob.data.splines[-1]
    last = sp.points[-1] if len(sp.points) else sp.bezier_points[-1]
    anchor = Vector(last.co[:3])
    far = max((Vector(p.co[:3]) for p in pts), key=lambda c: (c - anchor).length)
    direction = far - anchor
    if direction.length < 1e-6:
        return
    q = direction.normalized().rotation_difference(Vector((0, 0, 1)))  # stroke direction -> +Z
    m = q.to_matrix().to_4x4() @ Matrix.Translation(-anchor)  # old local -> new local
    for s in ob.data.splines:
        for p in s.points:
            co = m @ Vector(p.co[:3])
            p.co = (co.x, co.y, co.z, p.co[3])
        for p in s.bezier_points:
            p.co = m @ p.co
            p.handle_left = m @ p.handle_left
            p.handle_right = m @ p.handle_right
    ob.matrix_world = ob.matrix_world @ m.inverted()
    ob[PROP + "_anchored"] = True


def make_jiggly(ob, lv=1):
    if ob.type not in SUPPORTED:
        return False
    if ob.type == "CURVE":
        anchor_stroke(ob)
    ob[PROP] = int(lv)
    _ensure_mod(ob)
    return True


def remove_jiggle(ob):
    for name in (MOD,) + OLD_MODS:
        md = ob.modifiers.get(name)
        if md is not None:
            ob.modifiers.remove(md)
    if PROP in ob.keys():
        del ob[PROP]


def _expand(targets):
    from .groups import is_group, with_descendants

    obs = []
    for t in targets:
        for o in (with_descendants([t]) if is_group(t) else [t]):
            if o.type in SUPPORTED and o not in obs:
                obs.append(o)
    return obs


def _undo():
    _list["t"] = 0.0
    try:
        bpy.ops.ed.undo_push(message="VR pudding")
    except Exception:
        pass


def set_level(targets, lv):
    """Panel buttons: 0 = Off, 1 Soft, 2 Wobbly, 3 Jelly. Groups go in whole."""
    obs = _expand(targets)
    if not obs:
        return "Select (or hold) something first"
    if lv == 0:
        n = sum(1 for o in obs if is_jiggly(o))
        for o in obs:
            if is_jiggly(o):
                remove_jiggle(o)
        msg = f"No more pudding ({n})"
    else:
        n = sum(1 for o in obs if make_jiggly(o, lv))
        msg = f"{LEVELS[lv]['name']} pudding! ({n}) move or touch it"
    _undo()
    return msg


def toggle(targets):
    """Cycle Off -> Soft -> Wobbly -> Jelly -> Off."""
    obs = _expand(targets)
    if not obs:
        return "Select (or hold) something first"
    return set_level(obs, (min(level(o) for o in obs) + 1) % 4)


def common_level(targets):
    """The level all the targets share, None when mixed / nothing selected."""
    levels = {level(o) for o in _expand(targets)}
    return levels.pop() if len(levels) == 1 else None


# -- bodies: one pudding = one object, or one whole VR group -------------------------------------
def _body_key(ob):
    from .groups import group_root, is_group

    r = group_root(ob)
    return r.name if (r is not ob and is_group(r)) else ob.name


def _bodies():
    """[(key, frame_object, members, is_group)]. Rescanned once a second."""
    now = time.time()
    if now - _list["t"] > 1.0:  # new / deleted / synced / (un)grouped objects
        bodies = {}
        for o in bpy.data.objects:
            if o.get(PROP) and o.type in SUPPORTED:
                bodies.setdefault(_body_key(o), []).append(o.name)
        _list["bodies"] = bodies
        _list["t"] = now
    out = []
    for key, names in _list.get("bodies", {}).items():
        frame = bpy.data.objects.get(key)
        members = [bpy.data.objects[n] for n in names if n in bpy.data.objects]
        if frame is not None and members:
            out.append((key, frame, members, frame.name not in names))
    return out


def _points(ob, m):
    """Points of ob in the body's space (m: ob -> body space): all vertices for meshes,
    the bounding box otherwise."""
    if ob.type == "MESH" and 0 < len(ob.data.vertices) <= 400000:
        try:
            import numpy as np

            n = len(ob.data.vertices)
            co = np.empty(n * 3, dtype=np.float32)
            ob.data.vertices.foreach_get("co", co)
            co = co.reshape(-1, 3)
            mm = np.array(m, dtype=np.float32)
            return co @ mm[:3, :3].T + mm[:3, 3]
        except Exception:
            pass
    import numpy as np

    return np.array([tuple(m @ Vector(c)) for c in ob.bound_box], dtype=np.float32)


def _body_geo(key, frame, members, group):
    """Base height, height and centre of the body in its own space (cached for a second)."""
    g = _geo.get(key)
    if g is not None and (time.time() - g["t"] < 1.0 or not _st(key)["awake"]):
        return g  # resting puddings keep their numbers: no vertex reads while nothing moves
    import numpy as np

    inv = frame.matrix_world.inverted()
    pts = np.concatenate([_points(m, (inv @ m.matrix_world) if group else Matrix.Identity(4))
                          for m in members])
    lo, hi = pts.min(axis=0), pts.max(axis=0)
    height = max(float(hi[2] - lo[2]), 1e-6)
    scale = max(frame.matrix_world.to_scale())
    g = _geo[key] = {"t": time.time(), "base": float(lo[2]), "height": height,
                     "center": Vector((float(lo[0] + hi[0]) / 2, float(lo[1] + hi[1]) / 2, 0.0)),
                     "world_h": height * scale}
    return g


# -- simulation (Puddinger's advance()) -----------------------------------------------------------
def _st(key):
    s = _state.get(key)
    if s is None:
        s = _state[key] = {"point": None, "velocity": Vector(), "offset": Vector(), "speed": Vector(),
                           "awake": True, "touch": False, "written": None}
    return s


def kick(key, impulse_local):
    """Push the spring (pudding units / s, in the body's space)."""
    if not isinstance(key, str):
        key = _body_key(key)
    s = _st(key)
    s["speed"] += impulse_local
    s["awake"] = True


def _advance(s, frame, g, dt, gain):
    mw = frame.matrix_world
    probe_local = Vector((g["center"].x, g["center"].y, g["base"] + PROBE * g["height"]))
    point = mw @ probe_local
    to_units = REF_H / max(g["world_h"], 1e-6)  # world metres -> metres on a Puddinger pudding
    if s["point"] is None:
        s["point"] = point
        return
    delta = (point - s["point"]) * to_units
    s["point"] = point
    if dt > 0.12 or delta.length > JUMP:  # hitch / teleport / undo / room sync jump
        s["velocity"] = Vector()
        return
    velocity = delta / max(dt, 1e-3)
    dv = velocity - s["velocity"]
    s["velocity"] = velocity
    local_dv = mw.to_3x3().normalized().inverted_safe() @ dv
    if local_dv.length > MAX_DV:
        local_dv = local_dv.normalized() * MAX_DV
    if local_dv.length > 1e-4:
        s["awake"] = True
        s["speed"] -= local_dv * KICK * gain


def _spring(s, dt, room=1.0):
    steps = max(1, math.ceil(dt / SUB_DT))
    h = dt / steps
    off, spd = s["offset"], s["speed"]
    limit = LIMIT * room
    for _ in range(steps):
        spd += (-K * off - C * spd) * h
        off += spd * h
        for a in range(3):
            if abs(off[a]) > limit:
                off[a] = math.copysign(limit, off[a])
                spd[a] *= BOUNCE
    if off.length < REST and spd.length < REST * 10:
        off.zero()
        spd.zero()
        s["awake"] = False


def update(hand_pos=None, hand_vel=None, reach=0.0, held_names=()):
    """Every frame. hand_*: grip sphere centre / velocity (world), reach in world units."""
    now = time.perf_counter()
    dt = 0.0 if _clock["t"] is None else min(now - _clock["t"], 0.2)
    _clock["t"] = now
    if dt <= 0.0:
        return
    from .grab import _near_bounds

    for key, frame, members, group in _bodies():
        s = _st(key)
        lv = LEVELS[max(1, max(level(m) for m in members))]
        gain, room = lv["gain"], lv["room"]
        g = _body_geo(key, frame, members, group)
        _advance(s, frame, g, dt, gain)
        # touch: the grab sphere bumping into any part of it pushes the top along with the hand
        held = key in held_names or any(m.name in held_names for m in members)
        if hand_pos is not None and hand_vel is not None and not held:
            touching = any(_near_bounds(m, hand_pos, reach) for m in members)
            speed = hand_vel.length
            if touching and speed > TOUCH_SPEED and (not s["touch"] or speed > 0.4):
                hv = frame.matrix_world.to_3x3().normalized().inverted_safe() @ hand_vel
                hv = hv * (REF_H / max(g["world_h"], 1e-6))
                if s["touch"]:  # still sweeping through it: a smaller push every frame
                    hv = hv * 0.15
                if hv.length > MAX_DV:
                    hv = hv.normalized() * MAX_DV
                kick(key, hv * TOUCH_GAIN * gain)
            s["touch"] = touching
        if s["awake"]:
            _spring(s, dt, room)
        wob = Vector((max(-room, min(room, s["offset"].x / WOBBLE_FULL)) * WOBBLE_TOP,
                      max(-room, min(room, s["offset"].y / WOBBLE_FULL)) * WOBBLE_TOP, 0.0))
        sq_room = min(room, 1.6)  # squish 1.6 = 62 % of the height at most
        squish = max(-sq_room, min(sq_room, -s["offset"].z / SQUISH_FULL))
        dyn = (round(wob.x, 5), round(wob.y, 5), round(squish, 5))
        static = (_list["t"], group, g["t"])
        if (dyn, static) != s["written"]:
            full = s["written"] is None or s["written"][1] != static
            s["written"] = (dyn, static)
            for m in members:
                _write(m, frame if group else None, g, wob, squish, full)


def _write(ob, frame, g, wob, squish, full=True):
    md = _ensure_mod(ob) if full else ob.modifiers.get(MOD)
    if md is None:
        return
    if full:  # where / how big the body is: only after a rescan or a size check
        for ident, value in ((_sock("Frame"), frame), (_sock("Use Frame"), frame is not None),
                             (_sock("Base"), g["base"]), (_sock("Height"), g["height"]),
                             (_sock("Center"), g["center"])):
            set_input(md, ident, value)
    set_input(md, _sock("Wobble"), wob)
    set_input(md, _sock("Squish"), squish)
    # Blender 5: setting a Geometry Nodes input this way does not always re-evaluate the mesh
    # (a group member that is not moving itself kept its old shape). Ask for it explicitly.
    ob.update_tag(refresh={"DATA"})
