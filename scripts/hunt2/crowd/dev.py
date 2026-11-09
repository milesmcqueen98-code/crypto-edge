#!/usr/bin/env python3
"""Edge hunt 2, CROWD: the 8 DEV trials of the SPEC's frozen grid, each run once on the frozen simulator (sel, X2,
$250K) through pathA.dev_trial, which logs it in the shared ledger. DEV only (era fixed to sel). Resumable: variants
already in reports/hunt2/crowd/dev_trials.csv are not re-run (no trial is logged twice).

usage: python scripts/hunt2/crowd/dev.py sel
Writes reports/hunt2/crowd/dev_trials.csv and dev_daily.parquet (each variant's DEV series at X2), DEV-only.
"""
import json
import os
import sys
import time

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import crowd as CW  # noqa: E402

F, pathA = CW.F, CW.pathA
WT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
OUT = os.path.join(WT, "reports", "hunt2", "crowd")


def main(era):
    assert era == "sel", "DEV trials run on sel only"
    os.makedirs(OUT, exist_ok=True)
    csv, pq = os.path.join(OUT, "dev_trials.csv"), os.path.join(OUT, "dev_daily.parquet")
    done = pd.read_csv(csv) if os.path.exists(csv) else pd.DataFrame()
    daily = pd.read_parquet(pq) if os.path.exists(pq) else pd.DataFrame()
    par = pathA.parents("sel")
    with pathA.cpu_slot():
        F.arrays("sel")
    rows = done.to_dict("records")
    for v in CW.VARIANTS:
        name = CW.vname(v)
        if len(done) and name in set(done.variant):
            continue
        t0 = time.time()
        thr = CW.threshold(v, par)
        sk = CW.skip_frame("sel", v, thr)
        ns, npar = CW.n_skipped("sel", sk)
        m = CW.mult("sel", sk)
        scr, d = pathA.dev_trial("crowd", name, m=m, n_skip=ns, note="DEV trial, X2, $250K", thr=thr,
                                 skip_share=ns / npar, coin_days_skipped=int(sk.to_numpy().sum()))
        row = dict(variant=name, src=v["src"], stat=v["stat"], thr_kind=v["thr"], thr=thr, n_skipped=ns,
                   n_parents=npar, skip_share=ns / npar, coin_days_skipped=int(sk.to_numpy().sum()),
                   eligible=bool(0.10 <= ns / npar <= 0.50), sec=round(time.time() - t0))
        row.update({k: scr[k] for k in ("t_diff", "mean_diff_bp", "d_sharpe", "cand_sharpe", "inc_sharpe", "top5_share",
                                         "n_days")})
        rows.append(row)
        daily[name] = d
        pd.DataFrame(rows).to_csv(csv, index=False)
        daily.to_parquet(pq)
        print(json.dumps({k: (round(x, 4) if isinstance(x, float) else x) for k, x in row.items()}), flush=True)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "sel")
