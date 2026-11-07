#!/usr/bin/env python3
"""H10 (XQ): log DEV trials into the shared ledger (gates.log_trial, file-locked; run locally) from the daily series
written by trials.py, and keep reports/hunt/h10xq/trials_h10xq.csv (variant, DEV sleeve Sharpe, DEV alpha t on the
incumbent at $70K (the selection metric), dev_screen at $100K, trades). A variant already in the ledger is not
logged twice. usage: python scripts/hunt/h10xq/log_trials.py <summary tag> [note]"""
import json
import os
import sys

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, os.path.dirname(HERE))
import gates  # noqa: E402

IDEA = "h10xq"
DEV = os.path.join(ROOT, "reports", "hunt", "h10xq", "dev")
TAB = os.path.join(ROOT, "reports", "hunt", "h10xq", "trials_h10xq.csv")


def main(tag, note=""):
    S = pd.read_csv(os.path.join(DEV, f"summary_{tag}.csv"))
    L = pd.read_csv(gates.LEDGER) if os.path.exists(gates.LEDGER) else pd.DataFrame(columns=["idea", "variant"])
    done = set(L[L.idea == IDEA].variant)
    old = pd.read_csv(TAB) if os.path.exists(TAB) else pd.DataFrame()
    rows = []
    for s in S.itertuples():
        D = pd.read_parquet(os.path.join(DEV, f"{s.variant}.parquet"))
        r2 = D.s30_2x
        gates.assert_dev_only(r2)
        bk = gates.dev_book(r2)
        ri70 = gates.incumbent(70e3, days=r2.index)
        at = gates.alpha_test(r2, ri70)
        scr = gates.dev_screen(r2)
        row = dict(variant=s.variant, trades=int(s.trades), dev_sleeve_sharpe_2x=gates.sharpe(r2),
                   dev_sleeve_sharpe_1x=gates.sharpe(D.s30_1x), dev_alpha_t_70k=at["t_alpha"],
                   dev_alpha_yr_70k=at["alpha_yr"], dev_book_sharpe=gates.sharpe(bk),
                   dev_inc_sharpe_70k=gates.sharpe(ri70), screen=json.dumps({k: round(v, 4) if isinstance(v, float)
                                                                             else v for k, v in scr.items()}),
                   sum_ret_2x=float(r2.sum()), sum_ret_1x=float(D.s30_1x.sum()))
        if s.variant not in done:
            gates.log_trial(IDEA, s.variant, bk, note=note or f"H10 XQ DEV trial ({tag})", trades=int(s.trades),
                            dev_alpha_t_70k=round(at["t_alpha"], 3), sleeve_sharpe_2x=round(row["dev_sleeve_sharpe_2x"], 3))
            row["logged"] = "now"
        else:
            row["logged"] = "before"
        rows.append(row)
        print({k: (round(v, 3) if isinstance(v, float) else v) for k, v in row.items() if k != "screen"}, flush=True)
    T = pd.concat([old, pd.DataFrame(rows)], ignore_index=True).drop_duplicates("variant", keep="last")
    T.to_csv(TAB, index=False)
    L = pd.read_csv(gates.LEDGER)
    print("ledger rows for", IDEA, int((L.idea == IDEA).sum()))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "")
