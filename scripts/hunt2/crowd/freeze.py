#!/usr/bin/env python3
"""Edge hunt 2, CROWD: apply the SPEC's fixed selection rule to the 8 DEV trials and write reports/hunt2/crowd/frozen.json.
Rule: the highest DEV paired HAC t at X2 among variants that skip between 10% and 50% of the DEV research parents;
ties -> previous-day, then threshold 0. The threshold is frozen as the DEV number (q25 is never recomputed on HOLD).
The commit that adds frozen.json is the freeze.
usage: python scripts/hunt2/crowd/freeze.py <code commit>
"""
import json
import os
import sys

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
WT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
OUT = os.path.join(WT, "reports", "hunt2", "crowd")


def main(code_commit):
    T = pd.read_csv(os.path.join(OUT, "dev_trials.csv"))
    assert len(T) == 8, len(T)
    E = T[(T.skip_share >= 0.10) & (T.skip_share <= 0.50)].copy()
    E["stat_rank"] = (E.stat != "prev").astype(int)
    E["thr_rank"] = (E.thr_kind != "0").astype(int)
    E = E.sort_values(["t_diff", "stat_rank", "thr_rank"], ascending=[False, True, True])
    w, ru = E.iloc[0], E.iloc[1]
    num = lambda x: x.item() if hasattr(x, "item") else x  # noqa: E731
    fz = dict(idea="crowd", path="A", variant=w.variant,
              params=dict(source=w.src, statistic=w.stat, threshold_kind=str(w.thr_kind), threshold=float(w.thr),
                          rule="skip every 4-sigma bid of a coin on UTC day d when the statistic for d (from d - 1) "
                               "< threshold"),
              code_commit=code_commit, model="scripts/hunt2/crowd/crowd.py (pre-trial definitions in its docstring)",
              selection="highest DEV paired HAC t at X2 among variants skipping 10%..50% of DEV parents; ties -> "
                        "previous-day, then threshold 0",
              dev={k: num(w[k]) for k in ("t_diff", "mean_diff_bp", "d_sharpe", "cand_sharpe", "inc_sharpe",
                                          "n_skipped", "n_parents", "skip_share", "coin_days_skipped", "n_days")},
              runner_up=dict(variant=ru.variant, t_diff=float(ru.t_diff), skip_share=float(ru.skip_share)),
              eligible=list(E.variant), ineligible=list(T[~T.variant.isin(E.variant)].variant),
              n_trials_logged=int(len(T)),
              scored_days="sel 2025-01-01..2026-03-31, chk 2026-04-01..2026-11-05, early 2023-05-13..2023-12-31")
    json.dump(fz, open(os.path.join(OUT, "frozen.json"), "w"), indent=1, default=num)
    print(json.dumps(fz, indent=1, default=num))


if __name__ == "__main__":
    main(sys.argv[1])
