#!/usr/bin/env python3
"""Apply the pre-registered adoption bars (reports/wick_v2_prereg.md) to the shortlist.
Needs: shortlist.json, holdout_report.csv + overfit_stats.json (analyze.py --holdout), futures_check.csv.
Among shortlisted variants that pass every bar, the one with the best VALIDATION score is adopted (the
holdout is a pass/fail check, not a ranking). Writes reports/lab/v2_decision.json."""
import json
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import core  # noqa: E402

OUT = os.path.join(core.ROOT, "reports", "lab")
BASE = "V000 base (v1)"


def main():
    sl = json.load(open(os.path.join(OUT, "shortlist.json")))
    H = pd.read_csv(os.path.join(OUT, "holdout_report.csv")).set_index("variant")
    ov = json.load(open(os.path.join(OUT, "overfit_stats.json")))
    F = pd.read_csv(os.path.join(OUT, "futures_check.csv"))
    perp = F[F.venue == "perp"].set_index("variant")
    b = H.loc[BASE]
    rows = []
    for name in sl["variants"]:
        h = H.loc[name]
        bars = {
            "1 validation >= base + 0.25": bool(h.val_real >= b.val_real + 0.25),
            "2 holdout >= base holdout + 0.25": bool(h.hold_real >= b.hold_real + 0.25),
            "3 perp check (spot-confirmed) >= base": bool(perp.loc[name, "all_real_sharpe"] >= perp.loc[BASE, "all_real_sharpe"]),
            "4 deflated Sharpe >= 0.95 (N = v2 trials + 2,000)": bool(h.dsr_with_2000 >= 0.95),
            "5 PBO <= 0.3": bool(ov["pbo"] <= 0.3),
        }
        rows.append(dict(variant=name, val_real=h.val_real, hold_real=h.hold_real,
                         perp_real=perp.loc[name, "all_real_sharpe"], dsr_v2=h.dsr_v2, dsr_with_2000=h.dsr_with_2000,
                         passes=all(bars.values()), **bars))
    R = pd.DataFrame(rows)
    ok = R[R.passes].sort_values("val_real", ascending=False)
    near = R[R[[c for c in R.columns if c[:2] in ("1 ", "2 ", "3 ", "5 ")]].all(axis=1)].sort_values("dsr_with_2000",
                                                                                                   ascending=False)
    dec = dict(adopted=ok.variant.iloc[0] if len(ok) else None,
               candidate=None if len(ok) else (near.variant.iloc[0] if len(near) else None),
               base=dict(val_real=b.val_real, hold_real=b.hold_real, perp_real=perp.loc[BASE, "all_real_sharpe"]),
               pbo=ov["pbo"], walk_forward=dict(sharpe=ov["wf_sharpe"], base=ov["wf_base_sharpe"],
                                                hold=ov.get("wf_hold_sharpe"), hold_base=ov.get("wf_hold_base_sharpe")),
               shortlist=R.to_dict(orient="records"))
    json.dump(dec, open(os.path.join(OUT, "v2_decision.json"), "w"), indent=1, default=float)
    pd.set_option("display.width", 250)
    print(R.round(3).to_string(index=False))
    print("\nADOPTED:", dec["adopted"] or f"none - v1 stays; closest to clearing every bar: {dec['candidate']}")


if __name__ == "__main__":
    main()
