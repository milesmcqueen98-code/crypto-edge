#!/usr/bin/env python3
"""Red team 2 (ladder v5): the live incumbent's per-tranche results in every gate configuration, for the C3 re-test.

Runs hsim.book (policy engine, no candidate change) per era and configuration exactly as gates.incumbent does, checks
the daily series against the frozen cache (reports/ladder_v5/cache), and writes per-tranche tables for the minute and
instant bounds to reports/ladder_v5/redteam2/q/inc_<cfg>_<era>_<bound>.parquet plus a summary (tier, hsim counters,
parity) to reports/ladder_v5/redteam2/q/summary.csv. C3 only changes how each tranche's remainder is sold, so these
tables are all the C3 re-test needs.
usage: python scripts/ladder_v5/redteam2/qdump.py [configs comma-separated]
"""
import os
import sys
import time

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import gates  # noqa: E402
import fsim  # noqa: E402
import hsim  # noqa: E402

OUT = os.path.join(fsim.OUT, "redteam2", "q")
COLS = ["ts", "coin", "k", "lvl", "f_off", "fill_t", "fill", "tp_fill", "tp_off", "tp_t", "ex_t", "g60", "g_tp",
        "vol_d", "adv", "in_spot", "tp_spot", "pnl_tp", "pnl_rem", "entry_cost", "want", "mult"]


def main(configs):
    os.makedirs(OUT, exist_ok=True)
    rows = []
    for cfg in configs:
        kw = gates.CONFIGS[cfg]
        for era in fsim.ERAS:
            t0 = time.time()
            tag = fsim.ERAS[era][0]
            P, pan = gates.data(tag)
            d, out = hsim.book(P, era, pan=pan, adv=gates.adv(tag, era), **kw)
            inc = gates.incumbent_cached(era, cfg)
            par = float(np.abs(d.reindex(inc.index, fill_value=0.0) - inc).max())
            for name in ("minute", "instant"):
                Q, dd, info, st = out[name]
                Q[[c for c in COLS if c in Q]].to_parquet(os.path.join(OUT, f"inc_{cfg}_{era}_{name}.parquet"),
                                                          index=False)
                rows.append(dict(cfg=cfg, era=era, bound=name, parity_max_abs=par, maker_bp=info["maker_bp"],
                                 taker_bp=info["taker_bp"], v30=info["v30"], lat_share=fsim.lat_share(era, kw["theta"]),
                                 bought=float(Q.fill.sum()), rem=float((Q.fill - Q.tp_fill).sum()), **st))
            print(f"{cfg} {era}: parity {par:.2e}, {time.time() - t0:.0f}s", flush=True)
    pd.DataFrame(rows).to_csv(os.path.join(OUT, "summary.csv"), index=False)


if __name__ == "__main__":
    main(sys.argv[1].split(",") if len(sys.argv) > 1 else ["S_0.5", "S_0.25", "base_0.5", "cap_1M"])
