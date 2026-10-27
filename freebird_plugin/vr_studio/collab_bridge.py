# SPDX-License-Identifier: GPL-2.0-or-later
"""Room sync for what FreebirdCollabo does not carry (yet), riding on its open session:

  * parent changes after an object exists (VR groups: Grouping / Ungrouping)
    Collabo sends `parent` only inside obj_add, so a group made later stayed a pile of loose
    objects (and a loose pudding) for everyone else.
  * Pudding level (custom property `puddinger_jiggle`): Collabo does not sync custom properties.
  * object colour (ob.color: what Solid view shows in "Object" colour mode, and Freebird strokes)
  * taps on a pudding (touching it with the grab sphere): the push goes out as "kick" so it wobbles
    on every PC (a pudding that is MOVED wobbles everywhere already: its motion is synced)

How: a small "vrs" message through the same session (the hub forwards any message type; peers
without VR Studio simply ignore it). Nothing in Freebird / FreebirdCollabo is changed: we only
wrap the running session's `tick` (send before it, so a parent change goes out before the
obj_del of an ungrouped Empty) and `_handle` (catch "vrs", pass everything else through).
The wobble itself stays local: each Blender animates its own puddings from the synced motion.
"""

import sys
import time

import bpy
from mathutils import Matrix

MSG = "vrs"
SEND_EVERY = 0.15  # seconds
KICK_EVERY = 0.05  # taps: summed and sent at most 20 times a second (relay requests stay low)
PENDING_TTL = 10.0  # wait this long for a parent that has not arrived yet

_state = {"session": None, "orig_tick": None, "orig_handle": None, "t": 0.0, "t_kick": 0.0, "snap": None}
_pending = {}  # child name -> (item, first seen)


def _find_session():
    for name, mod in list(sys.modules.items()):
        if not name.endswith("freebird_collab") or not hasattr(mod, "get_session"):
            continue
        try:
            return mod.get_session()
        except Exception:
            return None
    return None


def _snapshot():
    from . import jiggle

    snap = {}
    for ob in bpy.context.scene.objects:
        snap[ob.name] = (ob.parent.name if ob.parent is not None else None, jiggle.level(ob),
                         tuple(round(c, 3) for c in ob.color))
    return snap


def _mat(ob):
    return [round(v, 6) for row in ob.matrix_world for v in row]


# -- install: wrap the live session ---------------------------------------------------------
def ensure():
    """Every frame (cheap): hook the collab session once it exists (it may be created later)."""
    s = _find_session()
    hooked = _state["session"]
    if s is not None and s is hooked and getattr(s.tick, "_vr_studio", False):
        return
    if hooked is not None and hooked is not s:
        uninstall()  # FreebirdCollabo was reinstalled / reloaded: let go of its old session
    if s is None:
        return
    orig_tick, orig_handle = s.tick, s._handle

    def tick():
        try:
            _send_changes(s)
        except Exception as e:
            print(f"[vr_studio] collab bridge send: {e}")
        return orig_tick()

    def handle(msg):
        if msg.get("t") == MSG:
            try:
                _apply(msg)
            except Exception as e:
                print(f"[vr_studio] collab bridge apply: {e}")
            return None
        return orig_handle(msg)

    tick._vr_studio = True
    s.tick, s._handle = tick, handle
    _state.update(session=s, orig_tick=orig_tick, orig_handle=orig_handle, snap=None)
    print("[vr_studio] collab bridge: groups + pudding ride on the room")


def uninstall():
    s = _state["session"]
    if s is not None:
        for attr in ("tick", "_handle"):  # back to the class methods
            if attr in s.__dict__:
                del s.__dict__[attr]
    _state.update(session=None, orig_tick=None, orig_handle=None, snap=None)
    _pending.clear()


# -- send -------------------------------------------------------------------------------------
def _send_changes(s):
    if not getattr(s, "active", False) or getattr(s, "uid", None) is None:
        _state["snap"] = None  # (re)joining starts from the scene as it is: the .blend carries it
        from . import jiggle

        jiggle.take_touches()  # taps made while not in a room are nobody else's business
        return
    now = time.time()
    if now - _state["t_kick"] >= KICK_EVERY:
        from . import jiggle

        _state["t_kick"] = now
        touches = jiggle.take_touches()
        if touches:
            s._send({"t": MSG, "objs": {}, "kick": touches})
    if now - _state["t"] < SEND_EVERY:
        return
    _state["t"] = now
    _retry_pending()
    snap = _snapshot()
    old = _state["snap"]
    _state["snap"] = snap
    if old is None:
        return
    objs = {}
    for name, (parent, lv, col) in snap.items():
        before = old.get(name)
        if before is None:
            # brand-new object: Collabo's obj_add carries the parent; we only add the pudding
            item = {}
            if lv:
                item["pud"] = lv
            if col != (1.0, 1.0, 1.0, 1.0):
                item["col"] = col
            if item:
                objs[name] = item
            continue
        item = {}
        if before[0] != parent:
            ob = bpy.context.scene.objects.get(name)
            item["par"] = parent
            item["m"] = _mat(ob)  # where it is now, so the peer never sees a jump
        if before[1] != lv:
            item["pud"] = lv
        if before[2] != col:
            item["col"] = col
        if item:
            objs[name] = item
    if objs:
        s._send({"t": MSG, "objs": objs})


# -- receive ----------------------------------------------------------------------------------
def _apply(msg):
    from . import jiggle

    if msg.get("kick"):
        jiggle.apply_touches(msg["kick"])
    changed = False
    for name, item in (msg.get("objs") or {}).items():
        ob = bpy.data.objects.get(name)
        if ob is None or name not in bpy.context.scene.objects:
            _pending[name] = (item, time.time())  # its obj_add is still on the way
            continue
        if _apply_one(ob, item):
            changed = True
        else:
            _pending[name] = (item, time.time())
    if changed:
        jiggle.refresh()
    if _state["snap"] is not None:  # what we just applied is not ours to send back
        _state["snap"].update(_snapshot())


def _apply_one(ob, item):
    from . import jiggle

    if "par" in item:
        pname = item["par"]
        parent = bpy.data.objects.get(pname) if pname else None
        if pname and (parent is None or pname not in bpy.context.scene.objects):
            return False  # parent not here yet: retried
        mw = Matrix([item["m"][i:i + 4] for i in range(0, 16, 4)]) if item.get("m") else ob.matrix_world.copy()
        ob.parent = parent
        if parent is not None:
            ob.matrix_parent_inverse = parent.matrix_world.inverted()
        ob.matrix_world = mw
    if "col" in item:  # object colour (Solid view "Object" mode, Freebird strokes): Collabo skips it
        ob.color = tuple(item["col"])
    if "pud" in item:
        lv = int(item["pud"] or 0)
        if lv:
            if ob.type == "CURVE":  # the sender already moved the stroke's origin (synced as data)
                ob[jiggle.PROP + "_anchored"] = True
            jiggle.make_jiggly(ob, lv)
        elif jiggle.is_jiggly(ob):
            jiggle.remove_jiggle(ob)
    return True


def _retry_pending():
    if not _pending:
        return
    from . import jiggle

    now = time.time()
    done = False
    for name, (item, t0) in list(_pending.items()):
        ob = bpy.data.objects.get(name)
        if ob is not None and name in bpy.context.scene.objects and _apply_one(ob, item):
            del _pending[name]
            done = True
        elif now - t0 > PENDING_TTL:
            del _pending[name]
    if done:
        jiggle.refresh()
        if _state["snap"] is not None:
            _state["snap"].update(_snapshot())
