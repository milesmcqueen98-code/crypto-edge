#!/usr/bin/env python3
"""Edge hunt 2, EXH (reports/hunt2/exh/SPEC.md): is the forced selling spent? Skip R2-08 parent fills that arrive
while aggressive selling is at its peak, before much forced volume has traded, or while sellers are still gaining
ground. Path A, builder "flow". The machinery is shared with WHO: scripts/hunt2/who/flowfilt.py.

usage: python scripts/hunt2/exh/exh.py dev sel | select | hold
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "who"))
import flowfilt  # noqa: E402

if __name__ == "__main__":
    flowfilt.main("exh", sys.argv[1:])
