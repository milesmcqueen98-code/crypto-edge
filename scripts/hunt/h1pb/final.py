#!/usr/bin/env python3
"""H1 after the freeze: the frozen variant over all scored days (DEV entries before CUT from the dev stage, the rest
from the hold stage), at 2x (gates) and 1x (information) costs, on $30K and $50K; gates.path_b; diagnostics.
Refuses to run unless reports/hunt/h1pb/frozen.json is committed and pushed (the freeze commit).
Writes reports/hunt/h1pb/{gates.json, daily.parquet, final_tables.txt, trades_frozen.parquet}.
"""
import json
import os
import subprocess
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
import book as B  # noqa: E402
import diag  # noqa: E402
import gates  # noqa: E402

CUT = pd.Timestamp("2026-05-31 10:00")            # hold-stage entries start here (their exits may reach into June)


def frozen_ok():
    fz = os.path.join(B.REP, "frozen.json")
    if not os.path.exists(fz):
        sys.exit("no frozen.json")
    root = B.ROOT
    rel = os.path.relpath(fz, root)
    st = subprocess.run(["git", "-C", root, "status", "--porcelain", rel], capture_output=True, text=True).stdout
    if st.strip():
        sys.exit("frozen.json has uncommitted changes")
    subprocess.run(["git", "-C", root, "fetch", "-q", "origin"], check=False)
    br = subprocess.run(["git", "-C", root, "rev-parse", "--abbrev-ref", "HEAD"], capture_output=True, text=True).stdout.strip()
    c = subprocess.run(["git", "-C", root, "log", "-1", "--format=%H", f"origin/{br}", "--", rel], capture_output=True,
                       text=True).stdout.strip()
    if not c:
        sys.exit("frozen.json is not on the remote branch yet")
    return json.load(open(fz)), c


def entries(H, theta, mode):
    D = B.load_devc(H, theta, mode)
    Hh = B.load("hold", H, theta, mode)
    D = D[D.t_fill < CUT.value]
    Hh = Hh[Hh.t_fill >= CUT.value]
    return pd.concat([D, Hh], ignore_index=True)


def main():
    fz, fz_commit = frozen_ok()
    v = fz["variant"]
    mode, k, side, H, tod = v["mode"], float(v["k"]), v["side"], int(v["H"]), v.get("tod")
    tod = None if tod in (None, "all") else tod
    start = pd.Timestamp(fz.get("start", "2025-07-19"))
    days = gates.ERA_DAYS[gates.ERA_DAYS >= start]
    E = entries(H, 0.5, mode)
    ser, trades = {}, {}
    for cap in (30_000.0, 50_000.0):
        for mult in (2.0, 1.0):
            r, T = B.sleeve(E, mode, k, side, days, cap, mult, tod)
            ser[f"s{int(cap / 1000)}_{int(mult)}x"] = r
            trades[(cap, mult)] = T
    daily = pd.DataFrame(ser)
    daily.index.name = "day"
    daily.to_parquet(os.path.join(B.REP, "daily.parquet"))
    G = gates.path_b({30000: daily["s30_2x"], 50000: daily["s50_2x"]}, days=days)
    G1x = gates.path_b({30000: daily["s30_1x"], 50000: daily["s50_1x"]}, days=days)
    T = trades[(30_000.0, 2.0)]
    T = T.assign(spot_conf=diag.spot_confirm(T)) if len(T) else T
    T.to_parquet(os.path.join(B.REP, "trades_frozen.parquet"), index=False)
    inc = gates.incumbent(70e3, 0.5, "instant", days)
    info = dict(frozen=v, freeze_commit=fz_commit, days=[str(days[0].date()), str(days[-1].date()), len(days)],
                trades_total=int(len(T)), trades_dev=int((pd.to_datetime(T.t_close) < gates.HOLD0).sum()),
                trades_hold=int((pd.to_datetime(T.t_close) >= gates.HOLD0).sum()),
                sleeve_sharpe_2x={"dev": gates.sharpe(daily.s30_2x[days < gates.HOLD0]),
                                  "hold": gates.sharpe(daily.s30_2x[days >= gates.HOLD0]), "full": gates.sharpe(daily.s30_2x)},
                sleeve_years_2x_30k={int(y): float(x) for y, x in gates.years(daily.s30_2x).items()},
                pnl_usd_2x={"dev": float(T[pd.to_datetime(T.t_close) < gates.HOLD0].net.sum()),
                            "hold": float(T[pd.to_datetime(T.t_close) >= gates.HOLD0].net.sum())})
    # information: theta 0.25, fee sensitivity
    E25 = entries(H, 0.25, mode)
    r25, T25 = B.sleeve(E25, mode, k, side, days, 30_000.0, 2.0, tod)
    info["theta025_2x"] = dict(trades=int(len(T25)), sharpe_full=gates.sharpe(r25),
                               sharpe_dev=gates.sharpe(r25[days < gates.HOLD0]), sharpe_hold=gates.sharpe(r25[days >= gates.HOLD0]),
                               pnl_usd=float(T25.net.sum()) if len(T25) else 0.0)
    for fee in (0.12, 0.30):
        rf, Tf = B.sleeve(E, mode, k, side, days, 30_000.0, 2.0, tod, fee_usd=fee)
        info[f"fee_{fee:.2f}_2x"] = dict(sharpe_full=gates.sharpe(rf), sharpe_dev=gates.sharpe(rf[days < gates.HOLD0]),
                                         sharpe_hold=gates.sharpe(rf[days >= gates.HOLD0]), pnl_usd=float(Tf.net.sum()))
        rf1, Tf1 = B.sleeve(E, mode, k, side, days, 30_000.0, 1.0, tod, fee_usd=fee)
        info[f"fee_{fee:.2f}_1x"] = dict(sharpe_full=gates.sharpe(rf1), pnl_usd=float(Tf1.net.sum()))
    tabs = diag.tables(T, daily.s30_2x, 30_000.0, inc)
    out = dict(gates_2x=G, gates_1x_info=G1x, info=info,
               provisional_note="G4 here uses the worktree gates.py ledger dispersion; the coordinator recomputes G4 centrally.")
    with open(os.path.join(B.REP, "gates.json"), "w") as f:
        json.dump(out, f, indent=1, default=lambda x: float(x) if isinstance(x, (np.floating, np.integer)) else str(x))
    with open(os.path.join(B.REP, "final_tables.txt"), "w") as f:
        for name, t in tabs.items():
            f.write(f"== {name}\n{t if not isinstance(t, pd.DataFrame) else t.to_string()}\n\n")
    print(json.dumps({k_: G[k_] for k_ in ("a", "full_t_alpha", "hold_t_alpha", "full_gain", "hold_gain", "dev_gain", "dsr",
                                           "G1", "G2", "G3", "G4", "G5", "years", "full_sleeve_sharpe",
                                           "hold_sleeve_sharpe", "dev_sleeve_sharpe")}, indent=1, default=str))
    print(json.dumps(info, indent=1, default=str))
    for name, t in tabs.items():
        print(f"== {name}\n{t}\n")


if __name__ == "__main__":
    main()
