#!/usr/bin/env python3
"""H1 DEV trials (SPEC "Trial grid"): 18 core variants (side x k x latency mode, H = 60, theta = 0.5), then H = 15 for
the best of the 18, then the maintenance-hour split (no orders 4:55-6:05 pm ET / orders only then) for the best so far.
Every variant is logged with gates.log_trial(gates.dev_book(sleeve $30K at 2x costs)). Selection: the highest DEV
alpha t (sleeve at 2x costs on the incumbent at $70K) among variants with >= 40 trades; ties to the simpler variant.
DEV only: the daily series end 2026-05-31 and are checked with gates.assert_dev_only.

  python scripts/hunt/h1pb/dev_trials.py [--dry]      (--dry: compute and print, do not log trials)
"""
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
import book as B  # noqa: E402
import gates  # noqa: E402

DRY = "--dry" in sys.argv
START = pd.Timestamp(os.environ.get("H1_START", "2025-07-19"))
DEV_DAYS = gates.ERA_DAYS[(gates.ERA_DAYS >= START) & (gates.ERA_DAYS < gates.HOLD0)]
OUT = os.path.join(B.REP, "dev_trials.csv")
SIMPLE = {"minute": 0, "sync": 1, "long": 0, "short": 0, "both": 1}


def score(name, E, mode, k, side, tod=None, H=60):
    r, T = B.sleeve(E, mode, k, side, DEV_DAYS, 30_000.0, 2.0, tod)
    gates.assert_dev_only(r)
    ri70 = gates.incumbent(70e3, 0.5, "instant", DEV_DAYS)
    at = gates.alpha_test(r, ri70)
    scr = gates.dev_screen(r)
    db = gates.dev_book(r)
    row = dict(variant=name, mode=mode, k=k, side=side, H=H, tod=tod or "all", trades=len(T),
               sleeve_sharpe=gates.sharpe(r), t_alpha70=at["t_alpha"], alpha_yr70=at["alpha_yr"],
               t_alpha100=scr["t_alpha"], corr=scr["corr"], dev_book_sharpe=gates.sharpe(db),
               dev_inc70_sharpe=gates.sharpe(gates.incumbent(70e3, 0.5, "instant", DEV_DAYS)),
               pnl_usd=float(T.net.sum()) if len(T) else 0.0, gross_usd=float(T.gross.sum()) if len(T) else 0.0,
               net_bp=float((T.net / T.notional).mean() * 1e4) if len(T) else np.nan,
               active_days=int((r != 0).sum()), simplicity=SIMPLE[mode] + SIMPLE[side] + (tod is not None) + (H != 60))
    if not DRY:
        gates.log_trial("h1pb", name, db, note=f"H1 perp wicks/rips on prints; {mode} k={k} {side} H={H} tod={tod or 'all'}"
                        f"; sleeve $30K 2x; trades={len(T)}", trades=len(T), t_alpha70=at["t_alpha"],
                        sleeve_sharpe=row["sleeve_sharpe"])
    print({k_: (round(v, 3) if isinstance(v, float) else v) for k_, v in row.items()}, flush=True)
    return row


def best(rows):
    ok = [r for r in rows if r["trades"] >= 40 and np.isfinite(r["t_alpha70"])]
    if not ok:
        return None
    return sorted(ok, key=lambda r: (-round(r["t_alpha70"], 6), r["simplicity"]))[0]


def main():
    rows = []
    E = B.load_devc(60, 0.5)
    print(f"DEV entries (H 60, theta 0.5, n >= 1): {len(E)}; days {DEV_DAYS[0].date()}..{DEV_DAYS[-1].date()} "
          f"({len(DEV_DAYS)})", flush=True)
    for mode in ("minute", "sync"):
        for k in (3.0, 4.0, 6.0):
            for side in ("long", "short", "both"):
                rows.append(score(f"{mode}_k{int(k)}_{side}_H60", E, mode, k, side))
    b18 = best(rows)
    if b18 is not None:
        E15 = B.load_devc(15, 0.5)
        rows.append(score(f"{b18['mode']}_k{int(b18['k'])}_{b18['side']}_H15", E15, b18["mode"], b18["k"], b18["side"], H=15))
        del E15
    b19 = best(rows)
    if b19 is not None:
        Eb = E if b19["H"] == 60 else B.load_devc(15, 0.5)
        base = f"{b19['mode']}_k{int(b19['k'])}_{b19['side']}_H{b19['H']}"
        rows.append(score(base + "_nomaint", Eb, b19["mode"], b19["k"], b19["side"], tod="no_maint", H=b19["H"]))
        rows.append(score(base + "_onlymaint", Eb, b19["mode"], b19["k"], b19["side"], tod="only_maint", H=b19["H"]))
    R = pd.DataFrame(rows)
    R.to_csv(OUT, index=False)
    sel = best(rows)
    print("\nselected:", json.dumps(sel, default=str))
    pd.set_option("display.width", 250)
    print(R[["variant", "trades", "sleeve_sharpe", "t_alpha70", "t_alpha100", "dev_book_sharpe", "pnl_usd",
             "net_bp", "corr"]].round(3).to_string(index=False))


if __name__ == "__main__":
    main()
