#!/usr/bin/env python3
"""Edge hunt 2, WHO (reports/hunt2/who/SPEC.md): who sold into our bid? Skip R2-08 parent fills whose pre-fill
aggressive selling looks informed (blocks, concentration, low aggressor share, slow drift). Path A, builder "flow".
The machinery (features, threshold rule, trials, HOLD read) is shared with EXH: scripts/hunt2/who/flowfilt.py.

usage: python scripts/hunt2/who/who.py dev sel | select | hold
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import flowfilt  # noqa: E402

if __name__ == "__main__":
    flowfilt.main("who", sys.argv[1:])
