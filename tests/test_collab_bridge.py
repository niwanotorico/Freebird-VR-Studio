# SPDX-License-Identifier: GPL-2.0-or-later
"""
Two-instance test of collab_bridge.py: Pudding level, late grouping and object colour ride on a
FreebirdCollabo room (no VR needed).

    FREEBIRD_COLLAB_DIR=<FreebirdCollabo checkout> python3 tests/test_collab_bridge.py
    blender --background --factory-startup --python tests/blender_runner.py -- tests/test_collab_bridge.py

HOST and GUEST are separate bpy processes joined in a direct-mode room. Checks:
  1  host makes a Cube jiggly (Wobbly) -> the guest's Cube gets the same level and the jiggle modifier
  2  guest changes it to Jelly, then Off -> the host follows (both directions)
  3  host groups two existing objects under a new Empty -> the guest gets the same parent, positions unchanged
  4  host sets ob.color -> the guest gets it
  5  a FreebirdCollabo reload (new session object) -> the bridge re-hooks the new session
Skipped (exit 0) when FREEBIRD_COLLAB_DIR is not set or does not hold freebird_collab/.
"""

import glob
import json
import os
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
COLLAB = os.environ.get("FREEBIRD_COLLAB_DIR", "")
PORT = 7811
STATE = os.path.join(tempfile.gettempdir(), "vrs_bridge_test_state")


def _put(**kw):
    for k, v in kw.items():
        tmp = f"{STATE}.{k}.tmp"
        with open(tmp, "w") as f:
            json.dump(v, f)
        os.replace(tmp, f"{STATE}.{k}")


def _get(k):
    try:
        with open(f"{STATE}.{k}") as f:
            return json.load(f)
    except Exception:
        return None


def _wait(cond, timeout, s, what):
    t0 = time.time()
    while time.time() - t0 < timeout:
        s.tick()
        try:
            if cond():
                return
        except Exception:
            pass
        time.sleep(0.02)
    raise AssertionError(f"timeout waiting for {what}")


def _idle(s, secs):
    t0 = time.time()
    while time.time() - t0 < secs:
        s.tick()
        time.sleep(0.02)


def _near(a, b, eps=1e-3):
    return all(abs(x - y) < eps for x, y in zip(a, b))


def run(role):
    import bpy

    sys.path.insert(0, COLLAB)
    sys.path.insert(0, os.path.join(ROOT, "freebird_plugin"))
    import freebird_collab
    from vr_studio import collab_bridge, jiggle

    s = freebird_collab.get_session()
    other = "guest" if role == "host" else "host"
    if role == "host":
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.5, location=(3, 0, 0))
        bpy.context.object.name = "Ball"
        assert s.create_room("DIRECT", "Host", (1, 0.5, 0.2), direct_port=PORT)
        _wait(lambda: s.uid is not None, 5, s, "welcome")
        _put(host_up=True)
        _wait(lambda: len(s.peers) == 1, 30, s, "guest join")
    else:
        _wait(lambda: _get("host_up"), 30, s, "host")
        assert s.join_room("DIRECT", "Guest", (0.2, 0.6, 1), direct_host="127.0.0.1", direct_port=PORT)
        _wait(lambda: s._scene_loaded_from_host, 30, s, "scene from host")
    collab_bridge.ensure()
    assert getattr(s.tick, "_vr_studio", False), "bridge did not hook the session"
    _idle(s, 0.5)
    _put(**{f"{role}_ready": True})
    _wait(lambda: _get(f"{other}_ready"), 30, s, f"{other} ready")
    _idle(s, 0.5)
    cube = lambda: bpy.data.objects["Cube"]  # noqa: E731

    # 1 / 2: pudding level both ways
    if role == "host":
        jiggle.make_jiggly(cube(), 2)
        _wait(lambda: _get("g1"), 15, s, "guest saw Wobbly")
        _wait(lambda: jiggle.level(cube()) == 3, 15, s, "guest's Jelly")
        print("HOST 2 OK: guest's Jelly arrived")
        _put(h2=True)
        _wait(lambda: jiggle.level(cube()) == 0 and not jiggle.is_jiggly(cube()), 15, s, "guest's Off")
        print("HOST 2 OK: guest's Off arrived")
    else:
        _wait(lambda: jiggle.level(cube()) == 2 and jiggle.is_jiggly(cube()), 15, s, "host's Wobbly")
        print("GUEST 1 OK: Cube is Wobbly with the jiggle modifier")
        _put(g1=True)
        jiggle.make_jiggly(cube(), 3)
        _wait(lambda: _get("h2"), 15, s, "host saw Jelly")
        jiggle.remove_jiggle(cube())
    _idle(s, 1.0)

    # 3 / 4: late grouping + object colour, from the host
    if role == "host":
        before = {n: tuple(bpy.data.objects[n].matrix_world.translation) for n in ("Cube", "Ball")}
        grp = bpy.data.objects.new("VRGroup", None)
        grp.location = (1, 1, 0)
        bpy.context.scene.collection.objects.link(grp)
        _idle(s, 1.0)  # the Empty goes out (obj_add) first
        for n in ("Cube", "Ball"):
            ob = bpy.data.objects[n]
            mw = ob.matrix_world.copy()
            ob.parent = grp
            ob.matrix_parent_inverse = grp.matrix_world.inverted()
            ob.matrix_world = mw
        bpy.data.objects["Ball"].color = (1.0, 0.2, 0.1, 1.0)
        _put(host_grouped=before)
        _wait(lambda: _get("g3"), 20, s, "guest saw the group")
    else:
        _wait(lambda: _get("host_grouped"), 20, s, "host grouped")
        before = _get("host_grouped")
        _wait(lambda: all(bpy.data.objects[n].parent is not None and bpy.data.objects[n].parent.name == "VRGroup"
                          for n in ("Cube", "Ball")), 20, s, "parent VRGroup")
        for n in ("Cube", "Ball"):
            assert _near(bpy.data.objects[n].matrix_world.translation, before[n]), (n, bpy.data.objects[n].matrix_world.translation)
        print("GUEST 3 OK: late grouping arrived, positions unchanged")
        _wait(lambda: _near(bpy.data.objects["Ball"].color, (1.0, 0.2, 0.1, 1.0)), 15, s, "object colour")
        print("GUEST 4 OK: object colour arrived")
        _put(g3=True)

    # 5: FreebirdCollabo reloaded -> a new session object; the bridge must hook it
    if role == "host":
        old = s
        new = freebird_collab.session.CollabSession()
        freebird_collab._session = new
        collab_bridge.ensure()
        assert getattr(new.tick, "_vr_studio", False), "bridge stayed on the old session"
        assert "tick" not in old.__dict__, "old session still wrapped"
        print("HOST 5 OK: bridge re-hooked a reloaded FreebirdCollabo")
        freebird_collab._session = old
        collab_bridge.ensure()
        _put(h5=True)
        _wait(lambda: _get("guest_done"), 20, s, "guest done")
    else:
        _put(guest_done=True)
        _wait(lambda: _get("h5"), 20, s, "host done")
    _idle(s, 0.3)
    s.leave()
    print(f"{role.upper()} PASS")


def _child(role):
    try:
        import bpy

        blender = bpy.app.binary_path
    except ImportError:
        blender = ""
    if blender:
        return [blender, "--background", "--factory-startup", "--python", os.path.abspath(__file__), "--", role]
    return [sys.executable, os.path.abspath(__file__), role]


def main():
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    if not COLLAB or not os.path.isdir(os.path.join(COLLAB, "freebird_collab")):
        print("SKIP: set FREEBIRD_COLLAB_DIR to a FreebirdCollabo checkout")
        return
    if args and args[0] in ("host", "guest"):
        try:
            run(args[0])
            code = 0
        except BaseException:
            import traceback

            traceback.print_exc()
            code = 1
        sys.stdout.flush()
        os._exit(code)  # the bpy wheel can hang in its exit handlers
    for f in glob.glob(STATE + ".*"):
        os.remove(f)
    host = subprocess.Popen(_child("host"))
    guest = subprocess.Popen(_child("guest"))
    rc_h, rc_g = host.wait(240), guest.wait(240)
    print(f"\n=== COLLAB BRIDGE: host rc={rc_h} guest rc={rc_g} ===")
    sys.exit(0 if rc_h == 0 and rc_g == 0 else 1)


if __name__ == "__main__":
    main()
