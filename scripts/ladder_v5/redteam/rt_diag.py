#!/usr/bin/env python3
"""Red team: the claim's diagnostic table (reports/ladder_v5/diag_holds.csv) from my replay, plus the paired t of the
live book against the research book, per era and capital (base: research volumes, 1x costs, theta 0.5).
usage: python scripts/ladder_v5/redteam/rt_diag.py [era ...]"""
import os
import sys
import time

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import rt_live as RL  # noqa: E402
import fsim  # noqa: E402


def counts(A, R, bound):
    """Parents unfunded / partial; research deeper fills (minute bound: first trade-through after minute 0) never
    filled live, filled late (a later trade-through)."""
    a4, wf = R["a4"], A["p_want"]
    par_unf = int((a4 <= 0).sum())
    par_part = int(((a4 > 0) & (a4 < wf * (1 - 1e-6))).sum())
    dres = never = late = 0
    st, ln, off = A["dp_start"], A["dp_len"], A["dp"]["off"]
    for q in range(A["NP"]):
        for k in range(2):
            if ln[q, k] == 0:
                continue
            first = off[st[q, k]]
            if bound == "minute" and first == 0:
                continue                       # the research's minute bound drops it
            dres += 1
            j = R["r_fidx"][q, k]
            if R["r_state"][q, k] != 2:
                never += 1
            elif j != st[q, k]:
                late += 1
    return dict(parents=A["NP"], parents_unfunded=par_unf, parents_partial=par_part, deeper_research=dres,
                deeper_never=never, deeper_late=late, cash_short=int(R["cash_short"]),
                why=pd.Series(R["why4"]).value_counts().to_dict())


def main(eras, caps=(250e3, 1e6)):
    rows = []
    t0 = time.time()
    for era in eras:
        tag = fsim.ERAS[era][0]
        P = RL.inputs(tag)["P"]
        for C in caps:
            A = RL.era_arrays(tag, era, 0.5, C, False)
            dres, _ = fsim.book(P, era, theta=0.5, C=C)
            dl, out, _ = RL.book(tag, era, theta=0.5, C=C, policy="engine", A=A, detail=True)
            dn, outn, _ = RL.book(tag, era, theta=0.5, C=C, policy="nocash", A=A, detail=True)
            sr, sl, sn = fsim.stats(dres, C, era), fsim.stats(dl, C, era), fsim.stats(dn, C, era)
            row = dict(era=era, C=C, research_ret=sr["ret_yr"], research_sharpe=sr["sharpe"], live_ret=sl["ret_yr"],
                       live_sharpe=sl["sharpe"], paired_t=fsim.nw_t(dl - dres), nocash_ret=sn["ret_yr"],
                       nocash_sharpe=sn["sharpe"], t_live_vs_nocash=fsim.nw_t(dl - dn))
            for b in ("minute", "instant"):
                cts = counts(A, out[b][1], b)
                for k, v in cts.items():
                    row[f"{b}_{k}"] = v
                row[f"{b}_ret"] = fsim.stats(out[b][0], C, era)["ret_yr"]
            rows.append(row)
            print({k: (round(v, 4) if isinstance(v, float) else v) for k, v in row.items()}, f"({time.time() - t0:.0f}s)",
                  flush=True)
    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(RL.OUT, "rt_diag_base.csv"), index=False)
    return df


if __name__ == "__main__":
    main(sys.argv[1:] or list(fsim.ERAS))
