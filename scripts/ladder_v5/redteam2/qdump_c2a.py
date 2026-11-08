#!/usr/bin/env python3
"""Red team 2 (ladder v5): C2a's per-tranche results in every gate configuration (as qdump.py does for the
incumbent), so C2a can be re-scored with the print-measured exit costs. Writes reports/ladder_v5/redteam2/q_c2a/."""
import os
import sys
import time

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)
import gates  # noqa: E402
import fsim  # noqa: E402
import hsim  # noqa: E402
import c2a  # noqa: E402
import qdump  # noqa: E402

OUT = os.path.join(fsim.OUT, "redteam2", "q_c2a")


def main(configs):
    os.makedirs(OUT, exist_ok=True)
    fns = {tag: c2a.make_fn(tag, gates.data(tag)[1], "c2a") for tag in ("main", "early")}
    rows = []
    for cfg in configs:
        kw = gates.CONFIGS[cfg]
        for era in fsim.ERAS:
            t0 = time.time()
            tag = fsim.ERAS[era][0]
            P, pan = gates.data(tag)
            d, out = hsim.book(P, era, pan=pan, adv=gates.adv(tag, era), size_fn=fns[tag], **kw)
            for name in ("minute", "instant"):
                Q, dd, info, st = out[name]
                Q[[c for c in qdump.COLS if c in Q]].to_parquet(os.path.join(OUT, f"inc_{cfg}_{era}_{name}.parquet"),
                                                                index=False)
                rows.append(dict(cfg=cfg, era=era, bound=name, maker_bp=info["maker_bp"], taker_bp=info["taker_bp"],
                                 v30=info["v30"], lat_share=fsim.lat_share(era, kw["theta"]),
                                 bought=float(Q.fill.sum()), rem=float((Q.fill - Q.tp_fill).sum()), **st))
            print(f"c2a {cfg} {era}: {time.time() - t0:.0f}s", flush=True)
    pd.DataFrame(rows).to_csv(os.path.join(OUT, "summary.csv"), index=False)


if __name__ == "__main__":
    main(sys.argv[1].split(",") if len(sys.argv) > 1 else list(gates.CONFIGS))
