# SPDX-License-Identifier: GPL-2.0-or-later
"""Run an existing bpy test role through Blender's --python entry point."""

import os
import runpy
import sys
import traceback


args = sys.argv[sys.argv.index("--") + 1:]
if not args:
    raise SystemExit("usage: blender ... --python blender_runner.py -- TEST [ARGS...]")

script = os.path.abspath(args[0])
sys.argv = [script, *args[1:]]
try:
    runpy.run_path(script, run_name="__main__")
except SystemExit:
    raise
except BaseException:
    # Blender prints a Python error from --python and still exits 0: make a failing test fail
    traceback.print_exc()
    sys.exit(1)
