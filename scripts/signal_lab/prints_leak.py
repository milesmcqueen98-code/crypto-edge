#!/usr/bin/env python3
"""Signal lab 2: per-candidate leak flags under the rule of deviations 2 and 3 of reports/signal_lab/prospective_prereg.md
(branch signal-lab, commit 8a0990f). Prints and candles only; no outcome, label or prediction is read.

For each candidate (coin, q):
  leak_0: trades stamped before q sit in the candle of q or later; any of
    (i)   a move in the leak direction (A: prints stamped in [q-d, q) sit in candle q) with d > 0 reconciles the pair
          (q-1, q) by prints_boundary.py's single-move test (one-sided where minute q was never fetched: candle q-1 =
          its prints less a suffix of them, candle q holding at least that volume);
    (ii)  no measured move explains the pair (q-1, q) (single-move kind "none" or "edge") and both signs fit a move
          into q: the prints of q-1 exceed its candle and the candle of q exceeds its prints;
    (iii) the candle row of q-1 is missing (or has zero volume) while prints exist in minute q-1.
  leak_5:  the same with d > 5 s in (i); (ii) and (iii) unchanged.
  leak_60: the candle rows of q-1 and q-2 are both missing while prints exist in minute q-2. A clock lag above 60 s
           cannot be measured by this diagnostic.
"Exceeds" means by more than 1e-5 relative (the tolerance of the boundary test; candle volume is float32).
Undecidable cases, counted apart and in the upper bounds:
  ii_unknown:   minute q's prints were never fetched (the last candidate of each merged window), the prints of q-1
                exceed its candle, (i) does not hold and candle q has volume: whether candle q exceeds its prints is
                unknown;
  ii_neighbour: the pair is explained by reconciled moves at the neighbouring boundaries (kind "neighbour") and both
                signs fit (a stricter reading of (ii) would count it).
The flags are for choosing one margin for every row; they must never be used to mask or drop rows.
Writes <out_dir>/leak_flags.parquet and qa_leak.json.
usage: python scripts/signal_lab/prints_leak.py <art_dir> [<out_dir>]      (selftest: python ... selftest)
"""
import glob
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
PR = os.path.join(ROOT, "reports", "signal_lab", "prints")
sys.path.insert(0, HERE)

NS_MIN = 60 * 10 ** 9
TOL = 1e-5
READ_ERAS = (("selection", "2025-01-01", "2026-04-01"), ("check", "2026-04-01", "2026-11-06"),
             ("early_holdout", "2022-01-01", "2024-01-01"), ("2021", "2021-01-01", "2022-01-01"),
             ("2024", "2024-01-01", "2025-01-01"))


def exceeds(a, b):
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    with np.errstate(invalid="ignore"):
        return (a - b) > TOL * np.maximum(a, b)


def flags(D):
    """D: two_sided, kind, d_s (single-move test at q), P2, P1, P0 (print base volume of q-2, q-1, q; P0 NaN when q
    was not fetched), C2, C1, C0 (candle volume, 0 without a row), row2, row1 (candle row exists, volume > 0)."""
    two = D.two_sided.to_numpy(bool)
    kind = D.kind.astype(str).to_numpy()
    d = D.d_s.to_numpy(float)
    c_i = (kind == "A") & (np.nan_to_num(d, nan=0.0) > 0)
    signs = exceeds(D.P1, D.C1) & exceeds(D.C0, D.P0)            # False where P0 is NaN
    c_ii = two & np.isin(kind, ["none", "edge"]) & signs
    c_iii = ~D.row1.to_numpy(bool) & (D.P1.to_numpy(float) > 0)
    leak_0 = c_i | c_ii | c_iii
    leak_5 = (c_i & (np.nan_to_num(d, nan=0.0) > 5.0)) | c_ii | c_iii
    leak_60 = ~D.row1.to_numpy(bool) & ~D.row2.to_numpy(bool) & (D.P2.to_numpy(float) > 0)
    ii_unknown = ~two & ~c_i & exceeds(D.P1, D.C1) & (D.C0.to_numpy(float) > 0)
    ii_neighbour = two & (kind == "neighbour") & signs
    merged = exceeds(D.C0, D.P0)
    iii_case = np.where(~c_iii, "", np.where(~two, "unknown", np.where(merged, "merged_into_q", "not_merged")))
    comp = np.array(["+".join(n for n, f in (("i", a), ("ii", b), ("iii", c)) if f)
                     for a, b, c in zip(c_i, c_ii, c_iii)], dtype=object)
    return pd.DataFrame(dict(leak_0=leak_0, leak_5=leak_5, leak_60=leak_60, component=comp,
                             d_s=np.where(c_i, d, np.nan), c_i=c_i, c_ii=c_ii, c_iii=c_iii, iii_case=iii_case,
                             ii_unknown=ii_unknown, ii_neighbour=ii_neighbour))


def selftest():
    rows = [  # two_sided, kind, d_s, P2, P1, P0, C2, C1, C0, row2, row1 -> expected leak_0, leak_5, leak_60, comp
        (True, "equal", np.nan, 5, 5, 5, 5, 5, 5, True, True, (False, False, False, "")),
        (True, "A", 3.0, 5, 5, 5, 5, 4, 6, True, True, (True, False, False, "i")),
        (True, "A", 9.0, 5, 5, 5, 5, 4, 6, True, True, (True, True, False, "i")),
        (True, "B", 2.0, 5, 5, 5, 5, 6, 4, True, True, (False, False, False, "")),
        (True, "none", np.nan, 5, 5, 5, 5, 4, 7, True, True, (True, True, False, "ii")),
        (True, "none", np.nan, 5, 5, 5, 5, 6, 7, True, True, (False, False, False, "")),
        (True, "neighbour", np.nan, 5, 5, 5, 5, 4, 7, True, True, (False, False, False, "")),
        (True, "A", 59.0, 5, 5, 5, 5, 0, 10, True, False, (True, True, False, "i+iii")),
        (True, "none", np.nan, 5, 5, 5, 5, 0, 5, True, False, (True, True, False, "iii")),
        (True, "none", np.nan, 5, 5, 5, 0, 0, 15, False, False, (True, True, True, "ii+iii")),
        (False, "deficit_unexplained", np.nan, 5, 5, np.nan, 5, 4, 7, True, True, (False, False, False, "")),
        (False, "equal", np.nan, 0, 5, np.nan, 0, 5, 7, False, True, (False, False, False, "")),
        (True, "none", np.nan, 0, 0, 5, 0, 0, 5, False, False, (False, False, False, "")),
    ]
    cols = ["two_sided", "kind", "d_s", "P2", "P1", "P0", "C2", "C1", "C0", "row2", "row1"]
    D = pd.DataFrame([r[:-1] for r in rows], columns=cols)
    F = flags(D)
    for k, r in enumerate(rows):
        want = r[-1]
        got = (bool(F.leak_0[k]), bool(F.leak_5[k]), bool(F.leak_60[k]), F.component[k])
        assert got == want, (k, got, want)
    assert F.ii_unknown.tolist() == [False] * 10 + [True, False, False]
    assert F.ii_neighbour.tolist() == [False] * 6 + [True] + [False] * 6
    assert F.iii_case.tolist() == [""] * 7 + ["merged_into_q", "not_merged", "merged_into_q", "", "", ""]
    msg = f"prints_leak self-test passed ({len(rows)} cases)"
    print(msg, flush=True)
    return msg


def era_of(ts):
    lab = np.full(len(ts), "", dtype=object)
    for name, a, b in READ_ERAS:
        lab[(ts >= pd.Timestamp(a)) & (ts < pd.Timestamp(b))] = name
    return lab


def summary(F):
    n = len(F)
    out = dict(n=int(n))
    for k in ("leak_0", "leak_5", "leak_60"):
        out[k] = int(F[k].sum())
        out[k + "_share"] = float(F[k].mean()) if n else None
    for k in ("c_i", "c_ii", "c_iii"):
        out[k] = int(F[k].sum())
    out["leak_0_components"] = {k: int(v) for k, v in F.component[F.leak_0].value_counts().items()}
    out["c_i_with_d_gt_5"] = int((F.c_i & (F.d_s > 5)).sum())
    out["iii_cases"] = {k: int(v) for k, v in F.iii_case[F.c_iii].value_counts().items()}
    out["ii_unknown_not_flagged"] = int((F.ii_unknown & ~F.leak_0).sum())
    out["ii_neighbour_not_flagged"] = int((F.ii_neighbour & ~F.leak_0).sum())
    up = F.ii_unknown | F.ii_neighbour
    out["leak_0_upper"] = int((F.leak_0 | up).sum())
    out["leak_5_upper"] = int((F.leak_5 | up).sum())
    out["leak_0_upper_share"] = float((F.leak_0 | up).mean()) if n else None
    out["leak_5_upper_share"] = float((F.leak_5 | up).mean()) if n else None
    return out


def main(art_dir, out_dir=PR):
    import prints_diag as PD
    import prints_features as PFE
    test_msg = selftest()
    files = sorted(glob.glob(os.path.join(art_dir, "**", "prints_*.parquet"), recursive=True))
    W = pd.read_csv(os.path.join(PR, "windows.csv"), parse_dates=["start", "end"])
    C = PFE.candidates()
    B = pd.read_parquet(os.path.join(PR, "qa_boundary_cand.parquet"))
    assert len(B) == len(C) and (B.coin.astype(str).to_numpy() == C.coin.to_numpy()).all()
    assert (B.ts.to_numpy() == C.ts.to_numpy()).all()
    cols = {k: np.full(len(C), np.nan) for k in ("P2", "P1", "P0", "C2", "C1", "C0")}
    rows = {k: np.zeros(len(C), dtype=bool) for k in ("row2", "row1", "row0", "q_fetched")}
    for product, g in W.groupby("product"):
        coin = product[:-4]
        idx = np.flatnonzero((C.coin == coin).to_numpy())
        qm = C.ts.to_numpy()[idx].astype("datetime64[ns]").view(np.int64) // NS_MIN
        raw, _ = PFE.load_coin(files, product)
        if raw is None:
            pm, pv = np.zeros(1, np.int64) - 1, np.zeros(1)
        else:
            d, _ = PFE.prep(raw["trade_id"], raw["t"], raw["price"], raw["size"], raw["sell"])
            del raw
            pm, pf = np.unique(d["t"] // NS_MIN, return_index=True)
            pv = np.add.reduceat(d["size"], pf)
            del d

        def pvol(mm):
            j = np.searchsorted(pm, mm)
            jc = np.clip(j, 0, len(pm) - 1)
            return np.where((j < len(pm)) & (pm[jc] == mm), pv[jc], 0.0)
        cm, cv = PD.candles(coin)

        def cvol(mm):
            j = np.searchsorted(cm, mm)
            jc = np.clip(j, 0, len(cm) - 1)
            hit = (j < len(cm)) & (cm[jc] == mm)
            return np.where(hit, cv[jc], 0.0), hit
        g = g.sort_values("start")
        st = g.start.to_numpy().astype("datetime64[ns]").view(np.int64) // NS_MIN
        en = g.end.to_numpy().astype("datetime64[ns]").view(np.int64) // NS_MIN
        k = np.searchsorted(st, qm, "right") - 1
        inside = (k >= 0) & (en[np.clip(k, 0, None)] > qm)          # minute q lies in a merged window: fetched
        for lag, pk, ck, rk in ((2, "P2", "C2", "row2"), (1, "P1", "C1", "row1"), (0, "P0", "C0", "row0")):
            cols[pk][idx] = pvol(qm - lag)
            cols[ck][idx], rows[rk][idx] = cvol(qm - lag)
        cols["P0"][idx[~inside]] = np.nan
        rows["q_fetched"][idx] = inside
        print(f"{coin}: {len(idx)} candidates, minute q fetched for {int(inside.sum())}", flush=True)
    D = pd.DataFrame(dict(two_sided=B.two_sided.to_numpy(bool), kind=B.kind.astype(str).to_numpy(),
                          d_s=B.d_s.to_numpy(float), **cols, row2=rows["row2"], row1=rows["row1"]))
    assert (D.two_sided.to_numpy() == rows["q_fetched"]).all(), "two-sidedness disagrees with the windows"
    F = flags(D)
    F.insert(0, "ts", C.ts.to_numpy())
    F.insert(0, "coin", C.coin.astype(str).to_numpy())
    F["read_era"] = era_of(pd.DatetimeIndex(C.ts))
    assert (F.read_era != "").all(), "a candidate outside every read era"
    F["two_sided"] = D.two_sided.to_numpy()
    F["candle_q_minus_prints_q"] = (D.C0 - D.P0).to_numpy()
    out = dict(self_test=test_msg, rule="prospective_prereg.md deviations 2 and 3 (signal-lab 8a0990f)",
               eras={name: summary(F[F.read_era == name]) for name, _, _ in READ_ERAS})
    out["all"] = summary(F)
    os.makedirs(out_dir, exist_ok=True)
    F.to_parquet(os.path.join(out_dir, "leak_flags.parquet"), index=False)
    with open(os.path.join(out_dir, "qa_leak.json"), "w") as fh:
        json.dump(out, fh, indent=1)
    print(json.dumps(out, indent=1), flush=True)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "selftest":
        selftest()
    else:
        main(*sys.argv[1:3])
