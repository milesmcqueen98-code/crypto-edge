"""Sizing lab, post-hoc diagnostics after the one holdout read: explanation only, no rule is changed. Writes
reports/sizing_lab/posthoc.txt."""
import os, sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd, lab
pd.set_option("display.width", 250)
out = []
for era in lab.ERAS:
    tag = lab.ERAS[era][0]
    sig, rowg = lab.features(tag)
    for book in ("main",):
        d, Q, _, _ = lab.run(book, 250e3, era, key="flat")
        r = lab.signal_returns(Q, 250e3)
        b = sig.bq3.reindex(r.index)
        g = pd.DataFrame({"r": r * 1e4, "b": b})
        s = g.groupby("b").r.agg(["count", "mean", "std"])
        s["mu_over_var_x1e4"] = s["mean"] / s["std"] ** 2 * 1e4
        out.append(f"{era} B2 terciles (flat main $250K, per-dollar bp):\n{s.round(2).to_string()}\n  unranked {int(b.isna().sum())}")
        # C1: guarded vs unguarded deeper rows, P&L per filled dollar
        q = Q[(Q.k > 4.0) & (Q.fill > 0)].copy()
        mi = pd.MultiIndex.from_arrays([q.ts, q.coin, q.k])
        q["c1"] = rowg.reindex(mi).fillna(0).to_numpy() > 0
        c = q.groupby("c1").apply(lambda x: pd.Series(dict(rows=len(x), fill_musd=x.fill.sum() / 1e6,
                                                            pnl_per_dollar_bp=1e4 * x.pnl.sum() / x.fill.sum())))
        out.append(f"{era} C1 deeper rows (flat main $250K):\n{c.round(2).to_string()}")
        top = (d * 250e3).sort_values(ascending=False).head(3)
        out.append(f"{era} flat main $250K best days: " + ", ".join(f"{i.date()} ${v:,.0f}" for i, v in top.items()))
txt = "\n\n".join(out) + "\n"
open(os.path.join(lab.OUT, "posthoc.txt"), "w").write(txt)
print(txt)
