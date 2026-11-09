#!/usr/bin/env python3
"""Edge hunt 2 (GAMMA/EXP), AFTER an idea's freeze commit only: copy one HOLD file from the derive run's artifact
(downloaded by hunt2.yml into art/<run_id>/...) into the repo, unchanged, so the HOLD read uses exactly the file the
pre-freeze derive run produced.

usage: python scripts/hunt2/gamma/copy_hold.py <art_dir> <file name> <destination path>
"""
import glob
import hashlib
import os
import shutil
import sys

art, name, dest = sys.argv[1:4]
fs = glob.glob(os.path.join(art, "**", "hold_out", name), recursive=True)
assert len(fs) == 1, fs
os.makedirs(os.path.dirname(dest), exist_ok=True)
shutil.copy(fs[0], dest)
print("copied", fs[0], "->", dest, os.path.getsize(dest), "bytes, sha256", hashlib.sha256(open(dest, "rb").read()).hexdigest())
