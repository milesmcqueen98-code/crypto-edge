#!/usr/bin/env python3
"""H10 (XQ): run DEV trial configurations (sim.py; prints applied wherever fetched) and write their DEV daily sleeve
returns (2x and 1x costs, $30K, theta 0.5) and trade summaries. DEV ONLY: events and days before 2026-06-01.
Outputs reports/hunt/h10xq/dev/<variant>.parquet (day, s30_2x, s30_1x) and reports/hunt/h10xq/dev/summary_<tag>.csv.
Logging into the shared trial ledger happens locally (log_trials.py).
usage: python scripts/hunt/h10xq/trials.py <tag> <k:exit:qset:H:cascade,...|core>"""
import os
import sys
import time

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
import sim  # noqa: E402
import gates  # noqa: E402

OUT = os.path.join(ROOT, "reports", "hunt", "h10xq", "dev")


def vname(k, ex, q, H, c):
    return f"k{int(k)}_{ex}_{q}" + (f"_H{H}" if ex == "a" else "") + ("_casc" if c else "")


def grid(spec):
    if spec == "core":
        return [(k, ex, q, 60, False) for q in sim.QSETS for ex in ("a", "b") for k in (3.0, 4.0, 6.0)]
    out = []
    for g in spec.split(","):
        k, ex, q, H, c = g.split(":")
        out.append((float(k), ex, q, int(H), c == "1"))
    return out


def main(tag, spec):
    os.makedirs(OUT, exist_ok=True)
    # Scoring basis: candles for every fill, costs exactly as common.py (deviation in REPORT: prints were fetched for a
    # ~1% sample only and are used to measure the candle-vs-print bias). H10_USE_PRINTS=1 applies them (information).
    P = sim.load_prints() if os.environ.get("H10_USE_PRINTS") == "1" else None
    hs = sim.half_spreads(P) if os.environ.get("H10_USE_PRINTS") == "1" else {}
    days = gates.ERA_DAYS[gates.ERA_DAYS < gates.HOLD0]
    rows, t0 = [], time.time()
    for k, ex, q, H, c in grid(spec):
        E = sim.load_events("dev", q, k, H)
        T = sim.run(E, q, 30000.0, 0.5, ex, c, P)
        out = {}
        for mult in (2.0, 1.0):
            r, T2, inf = sim.daily_returns(T, q, 30000.0, ex, mult, days, hs)
            gates.assert_dev_only(r)
            out[f"s30_{int(mult)}x"] = r
            if mult == 2.0:
                info2, T2x = inf, T2
        v = vname(k, ex, q, H, c)
        D = pd.DataFrame(out)
        D.index.name = "day"
        D.to_parquet(os.path.join(OUT, f"{v}.parquet"))
        tdir = os.environ.get("H10_TRADES_DIR", OUT)          # per-trade files are large: kept out of git
        os.makedirs(tdir, exist_ok=True)
        T2x.to_parquet(os.path.join(tdir, f"trades_{v}.parquet"), index=False)
        src = T.src.value_counts().to_dict() if len(T) else {}
        rows.append(dict(variant=v, k=k, exit=ex, qset=q, H=H, cascade=c, trades=len(T2x),
                         fill_musd=float(T2x.fill.sum() / 1e6) if len(T2x) else 0.0,
                         src_print=int(src.get("print", 0)), src_candle=int(src.get("candle", 0)),
                         print_reject=int(src.get("print_reject", 0)), small=int(sum(v_ for s, v_ in src.items()
                                                                                       if s.endswith("_small"))),
                         trade_usd_2x=info2["trade_usd"], inv_usd_2x=info2["inv_usd"]))
        print(rows[-1], f"{time.time() - t0:.0f}s", flush=True)
    pd.DataFrame(rows).to_csv(os.path.join(OUT, f"summary_{tag}.csv"), index=False)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
