#!/usr/bin/env python3
"""Red team: the off switch (research policy must reproduce fsim.book exactly) and the claim's base numbers.
usage: python scripts/ladder_v5/redteam/rt_check.py [era ...]"""
import os
import sys
import time

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import rt_live as RL  # noqa: E402
import fsim  # noqa: E402


def main(eras):
    t0 = time.time()
    for era in eras:
        tag = fsim.ERAS[era][0]
        A = RL.era_arrays(tag, era, 0.5, 250e3, False)
        print(f"{era}: arrays {time.time() - t0:.0f}s, parents {A['NP']}", flush=True)
        P = RL.inputs(tag)["P"]
        dref, outref = fsim.book(P, era, theta=0.5, C=250e3)
        d1, out, _ = RL.book(tag, era, policy="research", A=A, detail=True)
        for b, drop in (("minute", True), ("instant", False)):
            ref = outref[b][1]
            got = out[b][0]
            print(f"  research {b}: max daily diff vs fsim {float(np.abs(ref - got).max()):.2e}; "
                  f"fill check {RL.check_fills(A, out[b][1], out[b][2], 0.5):.2e}", flush=True)
        print(f"  research blend: max diff {float(np.abs(dref - d1).max()):.2e}", flush=True)
        for pol in ("nocash", "engine"):
            d1, out, _ = RL.book(tag, era, policy=pol, A=A, detail=True)
            st = fsim.stats(d1, 250e3, era)
            R = out["minute"][1]
            why = pd.Series(R["why4"]).value_counts().to_dict()
            print(f"  {pol}: {st['ret_yr']:.4f} / {st['sharpe']:.3f}  minute why {why}  "
                  f"fill check {RL.check_fills(A, R, out['minute'][2], 0.5):.2e} / "
                  f"{RL.check_fills(A, out['instant'][1], out['instant'][2], 0.5):.2e}  ({time.time() - t0:.0f}s)",
                  flush=True)


if __name__ == "__main__":
    main(sys.argv[1:] or ["chk"])
