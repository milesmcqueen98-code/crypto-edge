#!/usr/bin/env python3
"""Wick v4: per-rung precompute with a 10-sigma rung added (4/6/8/10), for the rung-weight candidates W1-W4
(reports/wick_v4_prereg.md). Same code as scripts/wick1m/sim.py precompute, with sim.LADDER extended; no Bitstamp,
as in the 17-coin main and early books. Writes reports/wick1m/pre_v4_<tag>.pkl (regenerable, not committed)."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "wick1m"))
import sim  # noqa: E402

sim.LADDER = (4.0, 6.0, 8.0, 10.0)
for tag in sys.argv[1:]:
    sim.precompute(tag, bitstamp=False, out_tag=f"v4_{tag}")
