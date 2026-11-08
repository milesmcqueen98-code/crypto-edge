#!/usr/bin/env python3
"""Red team 2 (ladder v5): how much the frozen cash rule flatters C3 (sensitivity, not a trial).

hsim frees a remainder's cash at minute 60; under C3 the remainder rests up to N more minutes. This builds an in-memory
variant of the frozen hsim (scripts/ladder_v5/hsim.py is read, not changed) in which every remainder releases its
cash at minute 60 + N instead of 60, an upper bound on C3's extra hold (in the model about half the remainder dollars
sell in minute 61). The one changed line is asserted. It reruns the incumbent's allocation with that hold and writes
per-tranche tables like qdump.py to reports/ladder_v5/redteam2/q_hold<N>/, so c3.py can score C3 on them.
usage: python scripts/ladder_v5/redteam2/hold.py <N> [configs comma-separated]
"""
import os
import sys
import time
import types

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
LV5 = os.path.dirname(HERE)
sys.path.insert(0, LV5)
import gates  # noqa: E402
import fsim  # noqa: E402

OLD = "            pos.append((i + sim.H, f))\n"
NEW = "            pos.append((i + sim.H + HOLD_EXTRA, f))\n"


def hsim_hold(extra):
    src = open(os.path.join(LV5, "hsim.py")).read()
    assert src.count(OLD) == 1, "frozen hsim changed"
    m = types.ModuleType("hsim_hold")
    m.__file__ = os.path.join(LV5, "hsim.py")
    exec(compile(src.replace(OLD, NEW), "hsim_hold", "exec"), m.__dict__)
    m.HOLD_EXTRA = int(extra)
    return m


def main(N, configs):
    import qdump
    h = hsim_hold(N)
    out_dir = os.path.join(fsim.OUT, "redteam2", f"q_hold{N}")
    os.makedirs(out_dir, exist_ok=True)
    rows = []
    for cfg in configs:
        kw = gates.CONFIGS[cfg]
        for era in fsim.ERAS:
            t0 = time.time()
            tag = fsim.ERAS[era][0]
            P, pan = gates.data(tag)
            d, out = h.book(P, era, pan=pan, adv=gates.adv(tag, era), **kw)
            inc = gates.incumbent_cached(era, cfg)
            for name in ("minute", "instant"):
                Q, dd, info, st = out[name]
                Q[[c for c in qdump.COLS if c in Q]].to_parquet(os.path.join(out_dir, f"inc_{cfg}_{era}_{name}.parquet"),
                                                                index=False)
                rows.append(dict(cfg=cfg, era=era, bound=name, hold_extra=N,
                                 diff_vs_frozen_mean=float((d.reindex(inc.index, fill_value=0.0) - inc).mean()),
                                 maker_bp=info["maker_bp"], taker_bp=info["taker_bp"], v30=info["v30"],
                                 lat_share=fsim.lat_share(era, kw["theta"]), bought=float(Q.fill.sum()),
                                 rem=float((Q.fill - Q.tp_fill).sum()), **st))
            print(f"hold +{N}: {cfg} {era} {time.time() - t0:.0f}s", flush=True)
    pd.DataFrame(rows).to_csv(os.path.join(out_dir, "summary.csv"), index=False)


if __name__ == "__main__":
    sys.path.insert(0, HERE)
    main(int(sys.argv[1]), sys.argv[2].split(",") if len(sys.argv) > 2 else list(gates.CONFIGS))
