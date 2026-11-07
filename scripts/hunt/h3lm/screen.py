#!/usr/bin/env python3
"""H3 (LM): record the mechanism-screen outcome (DEV only). Writes reports/hunt/h3lm/frozen.json (no variant frozen
when the screen fails) and gates.json (gates not evaluated; DEV-only analogues for information). HOLD is never read.

  python scripts/hunt/h3lm/screen.py
"""
import json
import os
import subprocess
import sys
import time

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
HUNT = os.path.dirname(HERE)
ROOT = os.path.dirname(os.path.dirname(HUNT))
sys.path.insert(0, HUNT)
import gates  # noqa: E402

OUT = os.path.join(ROOT, "reports", "hunt", "h3lm")
DEV = os.path.join(OUT, "dev")


def main():
    M = json.load(open(os.path.join(DEV, "dev_mech.json")))
    tab = pd.read_csv(os.path.join(DEV, "dev_table.csv"))
    chk = json.load(open(os.path.join(DEV, "dev_checks.json")))
    oi = json.load(open(os.path.join(DEV, "oi_check.json")))
    d = pd.read_parquet(os.path.join(DEV, "dev_daily.parquet"))
    assert d.index.max() < gates.HOLD0
    # prereg selection statistic: alpha t of the sleeve (2x, $30K) on the incumbent at $70K, DEV days
    inc70 = gates.incumbent(70e3, days=d.index)
    tab["t_alpha_inc70"] = [gates.alpha_test(d[f"{v}|30000|0.5|2x"], inc70)["t_alpha"] for v in tab.variant]
    tab.to_csv(os.path.join(DEV, "dev_table.csv"), index=False)
    passed = [k for k, v in M["mech"].items() if v["pass"]]
    dens = tab[(tab.arm == "dens") & (tab.trades >= 40)].sort_values("t_alpha_inc70", ascending=False)
    would = dens.iloc[0]
    commit = subprocess.run(["git", "-C", ROOT, "log", "--format=%H", "-1", "--", "scripts/hunt/h3lm/lm.py"],
                            capture_output=True, text=True).stdout.strip()
    # DEV-only analogues of the gates for the would-be selection (information only; not a gate result)
    v = would.variant
    s30, s50 = d[f"{v}|30000|0.5|2x"], d[f"{v}|50000|0.5|2x"]
    inc100 = gates.incumbent(100e3, days=d.index)
    bk7 = 0.7 * gates.incumbent(70e3, days=d.index) + 0.3 * s30
    bk5 = 0.5 * gates.incumbent(50e3, days=d.index) + 0.5 * s50
    a = 0.7 if gates.sharpe(bk7) >= gates.sharpe(bk5) else 0.5
    bk = bk7 if a == 0.7 else bk5
    ri = gates.incumbent(a * 100e3, days=d.index)
    at = gates.alpha_test(s30 if a == 0.7 else s50, ri)
    N, V = gates.n_trials()
    dsr, sr0 = gates.deflated_sharpe(bk, N, V)
    yrs = bk.groupby(bk.index.year).sum()
    dev_analogue = dict(variant=v, a=a, dev_t_alpha=at["t_alpha"], dev_book_sharpe=gates.sharpe(bk),
                        dev_inc_sharpe=gates.sharpe(inc100), dev_gain=gates.sharpe(bk) - gates.sharpe(inc100),
                        dev_sleeve_sharpe_2x=gates.sharpe(s30), dev_dsr=dsr, n_trials=N, vz=V,
                        dev_book_years={int(k): round(float(x), 4) for k, x in yrs.items()},
                        G1_like_t_ge_3=bool(at["t_alpha"] >= 3), G3_like_gain_ge_05=bool(gates.sharpe(bk) - gates.sharpe(inc100) >= 0.5),
                        G4_like_dsr_ge_095=bool(dsr >= 0.95), G5_like_no_losing_year=bool((yrs > 0).all()))
    frozen = dict(idea="h3lm", variant=None, params=None,
                  status="NO FREEZE: the mechanism test failed on DEV for all 8 density configs (SPEC: stop; HOLD not read)",
                  mechanism_rule="paired t of per-event net bp (density - depth-matched control, 2x costs) >= 2, "
                                 "event-level and day-clustered (Newey-West 5 lags)",
                  configs_passing=passed, code_commit=commit,
                  would_be_selection_if_screen_had_passed=dict(variant=v, dev_t_alpha_inc70=float(would.t_alpha_inc70),
                                                               dev_t_alpha_inc100=float(would.t_alpha),
                                                               trades=int(would.trades),
                                                               dev_sleeve_sharpe_2x=float(would.sleeve_sharpe_2x),
                                                               dev_book_sharpe_a07=float(would.book_sharpe)),
                  mech={k: {kk: M["mech"][k][kk] for kk in ("n_events", "dens_fills", "ctrl_fills", "diff_mean_bp",
                                                             "t_naive", "t_day_cluster", "pass")} for k in M["configs"]},
                  written=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    json.dump(frozen, open(os.path.join(OUT, "frozen.json"), "w"), indent=1, default=str)
    G = dict(idea="h3lm", path="B", result="FAIL at the mechanism screen (DEV); HOLD not read; G1-G5 not evaluated",
             G1=None, G2=None, G3=None, G4=None, G5=None, pass_G1_G5=False,
             gates_note="Each gate is recorded as not evaluated. The SPEC stops the idea before HOLD, so no full-window "
                        "or HOLD statistic exists. The DEV-only analogues below are information only.",
             mechanism=M["mech"], mechanism_pooled_descriptive=M["pooled"],
             dev_trials=json.loads(tab.to_json(orient="records")),
             dev_only_analogue_of_would_be_selection=dev_analogue, dev_checks=chk, binance_oi_check=oi,
             mechanism_extras=json.load(open(os.path.join(DEV, "mech_extra.json"))),
             per_fill_welch=json.load(open(os.path.join(DEV, "per_fill_welch.json"))),
             daily_parquet="reports/hunt/h3lm/daily.parquet holds DEV days only (the would-be selection); "
                           "HOLD days were never computed",
             deviations=["R3 venue facts (coordinator, before any result): bid within 5% of spot (both eras); "
                         "2-minute halt after a +-10% move from the hour's first open; no bids/fills/exits Friday "
                         "5-6 PM ET (all eras); fee sensitivity at $0.12/$0.30 (descriptive)",
                         "Mechanism pass rule requires both the SPEC's event-level paired t and a day-clustered t to "
                         "be >= 2 (fixed in the code before the DEV run); no config reached 2 on either",
                         "Control depth: the density bids' sigma-depths permuted within blocks of 25 events of "
                         "adjacent sigma rank (same coin, era, config), fixed seed 20261107; clip to R <= 1%"])
    json.dump(G, open(os.path.join(OUT, "gates.json"), "w"), indent=1, default=str)
    print(json.dumps(dict(passed=passed, would=frozen["would_be_selection_if_screen_had_passed"],
                          dev_analogue=dev_analogue), indent=1, default=str))
    print(tab[["variant", "trades", "sleeve_sharpe_2x", "t_alpha", "t_alpha_inc70", "book_sharpe"]].round(3)
          .to_string(index=False))


if __name__ == "__main__":
    main()
