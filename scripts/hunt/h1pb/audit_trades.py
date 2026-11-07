#!/usr/bin/env python3
"""Independent re-computation (plain Python, no numba kernel) of individual H1 entries from a raw print tape.

  python scripts/hunt/h1pb/audit_trades.py <tape.parquet> <entries.parquet> <coin> [n]

For up to n entries (minute mode, H = 60, theta = 0.5) whose fill lies in the tape, re-derive: the trigger (print
strictly through L with the previous print at or inside L), the through-volume run, the size, the take-profit fills
(placed 1 s after the fill; runs strictly beyond TP that start from a print at or inside TP) and the time exit (first
print >= 2 s after fill + 60 min), and compare with the kernel's numbers."""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import common  # noqa: E402

NS = 10**9


def recompute(tp_df, e, cs, tick):
    t, p, q, syn, seg = (tp_df[c].to_numpy() for c in ("t", "p", "q", "syn", "seg"))
    i = int(np.nonzero(t == e.t_fill)[0][0])
    assert i >= 1, "no print before the trigger in the window"
    long_ = e.side > 0
    L, TP = round(float(e.L) / tick) * tick, round(float(e.TP) / tick) * tick     # stored as float32: snap to the grid
    beyond_L = (lambda x: x <= L - tick * 0.999) if long_ else (lambda x: x >= L + tick * 0.999)
    inside_L = (lambda x: x >= L - tick * 0.001) if long_ else (lambda x: x <= L + tick * 0.001)
    assert beyond_L(p[i]) and inside_L(p[i - 1]) and seg[i - 1] == seg[i], "trigger condition"
    run, j = 0.0, i
    while j < len(t) and seg[j] == seg[i] and not syn[j] and beyond_L(p[j]):
        run += q[j]
        j += 1
    ntg = int(10_000 // (L * cs))
    n = min(ntg, int(0.5 * run))
    beyond_T = (lambda x: x >= TP + tick * 0.999) if long_ else (lambda x: x <= TP - tick * 0.999)
    D = e.t_fill + 3600 * NS
    left, tpn, gross, cum, live_run = n, 0, 0.0, 0.0, False
    tclose = None
    j = i + 1
    while j < len(t) and seg[j] == seg[i] and not syn[j] and t[j] < D and left > 0:
        if beyond_T(p[j]) and t[j] >= e.t_fill + NS:
            if not live_run and not beyond_T(p[j - 1]):
                live_run, cum = True, 0.0
            if live_run:
                f = min(left, int(0.5 * (cum + q[j])) - int(0.5 * cum))
                cum += q[j]
                if f > 0:
                    left -= f
                    tpn += f
                    gross += f * cs * ((TP - L) if long_ else (L - TP))
                    tclose = t[j]
        else:
            live_run = False
        j += 1
    if left > 0:
        k = j
        while k < len(t) and seg[k] == seg[i] and not syn[k] and t[k] < D + 2 * NS:
            k += 1
        x = p[k]
        gross += left * cs * ((x - L) if long_ else (L - x))
        tclose = t[k]
    return dict(run=run, n=n, tpn=tpn, gross=gross, tclose=tclose)


def main(tape_f, ent_f, coin, nmax=20):
    T = pd.read_parquet(tape_f)
    _, cs, tick = common.PERP[coin]
    E = pd.read_parquet(ent_f)
    E = E[(E.coin == coin) & E.valid60 & E.t_fill.isin(T.t.to_numpy())]
    E = E.sample(min(nmax, len(E)), random_state=1) if len(E) else E
    bad = 0
    for e in E.itertuples():
        r = recompute(T, e, cs, tick)
        same = (abs(r["run"] - e.run) < 1e-6 and r["n"] == e.n50 and r["tpn"] == e.tpn60_50
                and abs(r["gross"] - e.gross60_50) < 1e-6 * max(1, abs(r["gross"])) and r["tclose"] == e.tclose60_50)
        bad += not same
        print(("OK  " if same else "DIFF"), coin, pd.Timestamp(e.t_fill), "side", e.side, "k", e.k, "L", e.L,
              "kernel", (e.run, e.n50, e.tpn60_50, round(e.gross60_50, 4)), "audit",
              (r["run"], r["n"], r["tpn"], round(r["gross"], 4)))
    print(f"{len(E)} entries audited, {bad} differences")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4]) if len(sys.argv) > 4 else 20)
