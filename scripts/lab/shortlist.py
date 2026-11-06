#!/usr/bin/env python3
"""Fix the shortlist from validation results only (reports/wick_v2_prereg.md): the top 5 eligible variants
(>= 150 validation trades, diagnostics excluded) by validation realistic Sharpe over rounds 1, 1b and 2,
ENS10 = the top 10, plus the base. Writes reports/lab/shortlist.json."""
import json
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import core  # noqa: E402

OUT = os.path.join(core.ROOT, "reports", "lab")
DIAGNOSTIC = ("D12", "F06", "F07")


def main():
    tags = [t for t in ("round1", "round1b", "round2") if os.path.exists(os.path.join(OUT, f"results_val_{t}.csv"))]
    V = pd.concat([pd.read_csv(os.path.join(OUT, f"results_val_{t}.csv")) for t in tags], ignore_index=True)
    V = V.drop_duplicates("variant", keep="last")
    E = V[(V.val_trades >= 150) & (V.family != "base") & ~V.variant.str[:3].isin(DIAGNOSTIC)]
    E = E.sort_values("val_real_sharpe", ascending=False)
    sl = {"variants": E.variant.head(5).tolist(), "ens10": E.variant.head(10).tolist(), "rounds": tags,
          "n_variants": int(len(V)), "fixed_from": "validation 2025-01-01..2026-03-31 only"}
    json.dump(sl, open(os.path.join(OUT, "shortlist.json"), "w"), indent=1)
    print(json.dumps(sl, indent=1))
    print(E[["variant", "val_real_sharpe", "val_base_sharpe", "val_trades", "val_net_real_bp"]].head(10).round(2).to_string(index=False))


if __name__ == "__main__":
    main()
