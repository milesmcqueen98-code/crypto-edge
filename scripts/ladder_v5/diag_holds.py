#!/usr/bin/env python3
"""Ladder v5, step 1c: the live cash rule's cost (research book vs hold-aware book, engine policy only).

Writes reports/ladder_v5/diag_holds.csv: per era and capital, return / Sharpe of the research book (fsim) and of the
hold-aware book (hsim, the bot's allocation), the share of research parents and deeper fills the bot funds, and the
paired t of the difference. No candidate policy is run here.
"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fsim  # noqa: E402
import hsim  # noqa: E402


def main():
    rows = []
    for tag in ("main", "early"):
        P = fsim.load(tag)
        coins = sorted(P.coin.unique())
        idx, M, thr = hsim.panel(tag, coins)
        pan = (idx, M, thr, coins)
        for era, (tg, (lo, hi)) in fsim.ERAS.items():
            if tg != tag:
                continue
            adv = hsim.adv_table(tag, coins, lo, hi)
            for C in (250e3, 1e6):
                r0, _ = fsim.book(P, era, C=C)
                r1, out = hsim.book(P, era, C=C, adv=adv, pan=pan)
                st = out["instant"][3]
                s0, s1 = fsim.stats(r0, C, era), fsim.stats(r1, C, era)
                Qi = out["instant"][0]
                rows.append(dict(era=era, C=C, research_ret=s0["ret_yr"], research_sharpe=s0["sharpe"],
                                 live_ret=s1["ret_yr"], live_sharpe=s1["sharpe"], paired_t=fsim.nw_t(r1 - r0),
                                 parents=st["parents"], parents_unfunded=st["parent_unfunded"],
                                 parents_partial=st["parent_partial"], deeper_research=int(((Qi.k > 4)).sum()),
                                 deeper_never=st["deep_never"], deeper_late=st["deep_late"],
                                 cash_short_minutes=st["cash_short_minutes"]))
                print(rows[-1], flush=True)
    R = pd.DataFrame(rows)
    R.to_csv(os.path.join(fsim.OUT, "diag_holds.csv"), index=False)
    pd.set_option("display.width", 250)
    print(R.round(3).to_string(index=False))


if __name__ == "__main__":
    main()
