#!/usr/bin/env python3
"""Phase 1 grid (reports/wick1m_prereg.md): 4 size caps x 2 ladders x 3 exits x 2 trade lists, selection period,
$1M, theta 0.5 (and 0.25 shown). With WICK1M_CHECK=1 also the check period. Writes reports/wick1m/grid_<tag>.csv."""
import itertools
import os
import sys

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import sim  # noqa: E402

KAPPAS = [None, 0.0010, 0.0005, 0.00025] + ([0.0020, 0.0040] if os.environ.get("KAPPA_EXT") == "1" else [])
LADDERS = [False, True]
EXITS = ["E0", "E1", "E2"]
LISTS = ["bot", "all"]


def run_period(P, cfg, lo, hi, theta, C, gross=1.0):
    W = P[(P.ts >= lo) & (P.ts < pd.Timestamp(hi) + pd.Timedelta(days=1))]
    days = (pd.Timestamp(hi) - pd.Timestamp(lo)).days + 1
    Q, daily, info = sim.evaluate(W, theta=theta, C=C, days=days, gross_cap=gross, **cfg)
    st = sim.period_stats(daily, C, lo, hi)
    st.update(trades=int((Q.fill > 0).sum()), avg_fill=float(Q.fill[Q.fill > 0].mean()) if (Q.fill > 0).any() else 0.0,
              maker_bp=info["maker_bp"], taker_bp=info["taker_bp"])
    return st


def main():
    tag = sys.argv[1] if len(sys.argv) > 1 else "main"
    C = float(sys.argv[2]) if len(sys.argv) > 2 else 1e6
    gross = float(sys.argv[3]) if len(sys.argv) > 3 else 1.0
    P = pd.read_pickle(os.path.join(sim.OUT, f"pre_{tag}.pkl"))
    rows = []
    for kappa, ladder, ex, lst in itertools.product(KAPPAS, LADDERS, EXITS, LISTS):
        cfg = dict(kappa=kappa, ladder=ladder, exit_rule=ex, trade_list=lst)
        row = dict(kappa=kappa if kappa else 0.0, ladder=ladder, exit=ex, list=lst)
        periods = {"sel": sim.SEL} if tag != "early" else {"early": sim.EARLY}
        if sim.CHECK_OPEN and tag != "early":
            periods["chk"] = sim.CHK
        for pname, (lo, hi) in periods.items():
            for th in (0.5, 0.25):
                st = run_period(P, cfg, lo, hi, th, C, gross)
                for k_, v_ in st.items():
                    row[f"{pname}_{th}_{k_}"] = v_
        rows.append(row)
        print({k: (round(v, 3) if isinstance(v, float) else v) for k, v in row.items() if "0.5_" in k or k in ("kappa", "ladder", "exit", "list")}, flush=True)
    G = pd.DataFrame(rows)
    G.to_csv(os.path.join(sim.OUT, f"grid_{tag}{'_chk' if sim.CHECK_OPEN else ''}_{int(C/1e3)}k_g{gross:g}.csv"), index=False)
    key = "sel_0.5_sharpe" if tag != "early" else "early_0.5_sharpe"
    best = G.sort_values([key, key.replace("sharpe", "dollars_yr")], ascending=False).head(10)
    pd.set_option("display.width", 250)
    cols = [c for c in G.columns if c in ("kappa", "ladder", "exit", "list") or "_0.5_" in c or c.endswith("0.25_sharpe") or c.endswith("0.25_ret_yr")]
    print(best[cols].round(3).to_string(index=False))


if __name__ == "__main__":
    main()
