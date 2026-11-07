#!/usr/bin/env python3
"""H3 (LM): log the DEV trials (local only; the shared ledger is file-locked), print the mechanism test and the
selection. Reads reports/hunt/h3lm/dev/ (DEV days only; produced by `lm.py dev` on Actions).

  python scripts/hunt/h3lm/dev_log.py show          print the DEV table (no logging)
  python scripts/hunt/h3lm/dev_log.py log           log all 16 trials (8 density + 8 control) once; writes dev_trials.csv
"""
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
HUNT = os.path.dirname(HERE)
ROOT = os.path.dirname(os.path.dirname(HUNT))
sys.path.insert(0, HUNT)
import gates  # noqa: E402

IDEA = "h3lm"
DEV = os.path.join(ROOT, "reports", "hunt", IDEA, "dev")


def load():
    M = json.load(open(os.path.join(DEV, "dev_mech.json")))
    d = pd.read_parquet(os.path.join(DEV, "dev_daily.parquet"))
    T = pd.read_parquet(os.path.join(DEV, "dev_trades.parquet"))
    assert d.index.max() < gates.HOLD0 and (T.fill_ts < gates.HOLD0).all()
    return M, d, T


def table(M, d, T):
    rows = []
    for name in M["configs"]:
        for arm in ("dens", "ctrl"):
            v = f"{arm}_{name}"
            s30 = d[f"{v}|30000|0.5|2x"]
            gates.assert_dev_only(s30)
            scr = gates.dev_screen(s30)
            bk = gates.dev_book(s30)
            tr = T[T.variant == v]
            rows.append(dict(variant=v, arm=arm, cfg=name, trades=len(tr), sleeve_sharpe_2x=scr["sleeve_sharpe"],
                             t_alpha=scr["t_alpha"], corr=scr["corr"], active_days=scr["active_days"],
                             book_sharpe=gates.sharpe(bk), ret_yr_2x=float(s30.sum() / (len(s30) / 365.25)),
                             ret_yr_1x=float(d[f"{v}|30000|0.5|1x"].sum() / (len(s30) / 365.25)),
                             ret_yr_th025=float(d[f"{v}|30000|0.25|2x"].sum() / (len(s30) / 365.25)),
                             mech_t=M["mech"][name]["t_naive"], mech_t_day=M["mech"][name]["t_day_cluster"],
                             mech_pass=M["mech"][name]["pass"]))
    return pd.DataFrame(rows)


def main():
    M, d, T = load()
    tab = table(M, d, T)
    pd.set_option("display.width", 220)
    print(tab.round(3).to_string(index=False))
    print("pooled (descriptive):", M["pooled"])
    if len(sys.argv) > 1 and sys.argv[1] == "log":
        flag = os.path.join(DEV, "logged.json")
        if os.path.exists(flag):
            raise SystemExit("already logged: " + open(flag).read())
        out = []
        for r in tab.itertuples():
            s30 = d[f"{r.variant}|30000|0.5|2x"]
            bk = gates.dev_book(s30)
            mech = M["mech"][r.cfg]
            note = (f"{'density' if r.arm == 'dens' else 'depth-matched random control'} bid, {r.cfg}; "
                    f"mechanism paired t {mech['t_naive']:.2f} / day-clustered {mech['t_day_cluster']:.2f}")
            row = gates.log_trial(IDEA, r.variant, bk, note=note, trades=int(r.trades),
                                  sleeve_sharpe_2x=round(float(r.sleeve_sharpe_2x), 4), t_alpha=round(float(r.t_alpha), 4),
                                  mech_pass=bool(r.mech_pass))
            out.append(row)
        pd.DataFrame(out).to_csv(os.path.join(DEV, "dev_trials.csv"), index=False)
        json.dump(dict(n=len(out), ledger=gates.LEDGER), open(flag, "w"))
        print(f"logged {len(out)} trials to {gates.LEDGER}")
    tab.to_csv(os.path.join(DEV, "dev_table.csv"), index=False)


if __name__ == "__main__":
    main()
