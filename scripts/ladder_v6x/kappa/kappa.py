#!/usr/bin/env python3
"""Ladder v6 exits: kappa(m), the cost of a market sell at minute m after a fill relative to minute 60
(reports/ladder_v6x_prereg.md, "Exit costs at any minute"), from reports/ladder_v6x/kappa/prints_kappa.csv.

cost(m) of an event = its own half-spread at minute m (hs_bp, only when hs_n >= 5) + the slippage at its size X
(sample.csv: fill / fsc) from its own first-X grid at minute m (a grid size only when n >= 3), computed as
scripts/ladder_v6x/frozen/c3.py PrintCost.cost does: cumulative max over sizes, linear below the smallest size,
interpolation inside, linear extrapolation beyond the largest size with data. No coin-era pooled fallback and no model
fallback (fb_bp = 0): an event-minute without its own valid data is missing.
Valid pair at m: cost(m) and cost(60) both finite and cost(60) > 0. kappa(m) = median over valid pairs of
cost(m) / cost(60); with fewer than 100 valid pairs at a minute, kappa(m) = 2 (pre-registered).
Writes reports/ladder_v6x/kappa/kappa.csv (by m: n_valid, kappa, and for information the median costs, the mean
ratio, the dollar-weighted ratio sum(X cost(m)) / sum(X cost(60)), kappa by rung k, and a cross-check that prices X
from the slippage measured at exactly X), kappa_events.csv (per event and m) and kappa_clip.csv (sensitivity, never
used as kappa: m = 2 and 5 with prints before fill_t + 1 min dropped, against the same cost(60)).
usage: python scripts/ladder_v6x/kappa/kappa.py
"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
KD = os.path.join(ROOT, "reports", "ladder_v6x", "kappa")
XS = np.array((250, 500, 1000, 2000, 5000, 10000, 20000, 50000, 100000, 200000), float)
MS = (2, 5, 10, 20, 30, 45, 60)
MIN_N, MIN_HS = 3, 5                  # PrintCost: own slippage at a size when n >= 3; own half-spread when hs_n >= 5
MIN_PAIRS, KAPPA_FEW = 100, 2.0       # pre-registered: fewer than 100 valid pairs at a minute -> kappa = 2
RUNGS = (4, 6, 8)


def own_table(D):
    """PrintCost.__init__'s per-event table with the coin-era pools switched off."""
    tab = {}
    for r in D.itertuples():
        sl = np.array([getattr(r, f"slip_{int(x)}") for x in XS], float)
        nn = np.array([getattr(r, f"n_{int(x)}") for x in XS], float)
        s = np.where(nn >= MIN_N, sl, np.nan)
        hs = r.hs_bp if np.isfinite(r.hs_bp) and r.hs_n >= MIN_HS else np.nan
        tab[(r.event_id, r.m)] = (hs, s)
    return tab


def cost_bp(v, x):
    """PrintCost.cost of x USD with fb_bp = 0 (no model floor beyond the data), in bp instead of a fraction."""
    if v is None or not np.isfinite(v[0]):
        return np.nan
    hs, s = v
    ok = np.isfinite(s)
    if not ok.any():
        return np.nan
    xs, ss = XS[ok], np.maximum.accumulate(np.maximum(s[ok], 0.0))
    if x <= xs[0]:
        sl = ss[0] * x / xs[0]
    elif x <= xs[-1]:
        sl = np.interp(x, xs, ss)
    else:
        sl = max(ss[-1] * x / xs[-1], 0.0)
    return hs + sl


def frozen_check(tab, K):
    """The same costs from the frozen PrintCost.cost itself (its table replaced by the pool-free one)."""
    try:
        sys.path.insert(0, os.path.join(ROOT, "scripts", "ladder_v5"))
        import gates  # noqa: F401  (first, as lsim.py does)
        sys.path.insert(0, os.path.join(ROOT, "scripts", "ladder_v6x", "frozen"))
        import c3
    except Exception as err:                              # noqa: BLE001
        return f"skipped ({err!r})"
    pc = object.__new__(c3.PrintCost)
    pc.xs = XS.copy()
    pc.tab = {(eid, pd.Timestamp(ft), m): tab[(eid, m)] for (eid, m), ft in
              zip(zip(K.event_id, K.m), K.fill_t) if (eid, m) in tab}
    fz = np.array([1e4 * c3.PrintCost.cost(pc, r.event_id, r.fill_t, r.m, r.X, fb_bp=0.0)
                   for r in K.itertuples()])
    same_nan = bool((np.isnan(fz) == np.isnan(K.cost_bp.to_numpy())).all())
    both = np.isfinite(fz) & np.isfinite(K.cost_bp.to_numpy())
    dmax = float(np.max(np.abs(fz[both] - K.cost_bp.to_numpy()[both]))) if both.any() else np.nan
    return f"{both.sum()} event-minutes, max |difference| {dmax:.2e} bp, missing pattern identical: {same_nan}"


def costs(D, S, ms):
    tab = own_table(D)
    rows = []
    for e in S.itertuples():
        for m in ms:
            v = tab.get((e.event_id, m))
            r = D[(D.event_id == e.event_id) & (D.m == m)]
            r = r.iloc[0] if len(r) else None
            ax = np.nan
            if v is not None and np.isfinite(v[0]) and r is not None and r.n_at_X >= MIN_N:
                ax = v[0] + max(r.slip_at_X, 0.0)
            rows.append(dict(event_id=e.event_id, coin=e.coin, fill_t=e.fill_t, k=int(e.k), X=e.X, m=m,
                             hs_own_bp=v[0] if v is not None else np.nan,
                             n_sizes_own=int(np.isfinite(v[1]).sum()) if v is not None else 0,
                             cost_bp=cost_bp(v, e.X), cost_atX_bp=ax))
    return pd.DataFrame(rows), tab


def pair(K, ref):
    """Attach cost(60) (from `ref`, the unclipped minute-60 costs) and the valid-pair ratio."""
    c60 = ref.set_index("event_id").cost_bp
    a60 = ref.set_index("event_id").cost_atX_bp
    K = K.copy()
    K["cost60_bp"] = K.event_id.map(c60)
    K["valid"] = np.isfinite(K.cost_bp) & np.isfinite(K.cost60_bp) & (K.cost60_bp > 0)
    K["ratio"] = np.where(K.valid, K.cost_bp / K.cost60_bp, np.nan)
    K["cost60_atX_bp"] = K.event_id.map(a60)
    v = np.isfinite(K.cost_atX_bp) & np.isfinite(K.cost60_atX_bp) & (K.cost60_atX_bp > 0)
    K["ratio_atX"] = np.where(v, K.cost_atX_bp / K.cost60_atX_bp, np.nan)
    return K


def table(K, rule=True):
    """By m: valid pairs, kappa (with the pre-registered rule when `rule`), and the information columns."""
    med = lambda s: float(np.median(s)) if len(s) else np.nan  # noqa: E731
    out = []
    for m, g in K.groupby("m"):
        v = g[g.valid]
        n = len(v)
        kr = med(v.ratio)
        row = dict(m=m, n_valid=n)
        if rule:
            row["kappa"] = kr if n >= MIN_PAIRS else KAPPA_FEW
        row.update(kappa_median=kr, med_cost_m_bp=med(v.cost_bp), med_cost_60_bp=med(v.cost60_bp),
                   mean_ratio=float(v.ratio.mean()) if n else np.nan,
                   dw_ratio=float((v.X * v.cost_bp).sum() / (v.X * v.cost60_bp).sum()) if n else np.nan,
                   n_cost_m=int(np.isfinite(g.cost_bp).sum()))
        for k in RUNGS:
            vk = v[v.k == k]
            row[f"n_k{k}"], row[f"kappa_k{k}"] = len(vk), med(vk.ratio)
        va = g[np.isfinite(g.ratio_atX)]
        row["n_valid_atX"], row["kappa_atX"] = len(va), med(va.ratio_atX)
        out.append(row)
    return pd.DataFrame(out)


def main():
    S = pd.read_csv(os.path.join(KD, "sample.csv"), parse_dates=["fill_t"])
    D = pd.read_csv(os.path.join(KD, "prints_kappa.csv"), parse_dates=["fill_t"])
    Dc = pd.read_csv(os.path.join(KD, "prints_kappa_clip.csv"), parse_dates=["fill_t"])
    assert len(S) == 300 and S.event_id.is_unique
    K, tab = costs(D, S, MS)
    print("frozen PrintCost.cost cross-check:", frozen_check(tab, K))
    K = pair(K, K[K.m == 60])
    T = table(K)
    Kc, _ = costs(Dc, S, (2, 5))
    Kc = pair(Kc, K[K.m == 60])
    Tc = table(Kc, rule=False)
    K.to_csv(os.path.join(KD, "kappa_events.csv"), index=False)
    T.to_csv(os.path.join(KD, "kappa.csv"), index=False)
    Tc.to_csv(os.path.join(KD, "kappa_clip.csv"), index=False)
    pd.set_option("display.width", 250)
    print("kappa(m):")
    print(T.round(4).to_string(index=False))
    print("sensitivity (prints from fill_t + 1 min on; not kappa):")
    print(Tc.round(4).to_string(index=False))
    have = K.groupby("event_id").cost_bp.apply(lambda s: np.isfinite(s).any())
    print(f"events with a finite cost at some minute: {int(have.sum())} of {len(S)}; "
          f"with a finite cost(60): {int(np.isfinite(K[K.m == 60].cost_bp).sum())}; "
          f"cost(60) > 0: {int((K[K.m == 60].cost_bp > 0).sum())}")


if __name__ == "__main__":
    main()
