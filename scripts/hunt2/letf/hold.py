#!/usr/bin/env python3
"""Edge hunt 2, LETF: the single HOLD read of the frozen variant (AFTER the freeze commit only).

Runs reports/hunt2/letf/frozen.json's variant on every era (sel, chk, early): the sleeve on $25K/$50K/$75K/$125K at 2x
and 1x costs (theta from frozen.json; theta 0.25 too, for information, when the leg rests orders). Scored days: each
era's gated days (letf.scored_days). An era with < 60 scored days or < 10 trades ($50K, 2x) is reported, not gated
(prereg "Windows"): its days are left out of daily.parquet and of the gate days. Gates: h2gates.path_b at 2x; the same
call at 1x is information. The early era is also run with the gate off, as the SPEC's descriptive placebo.
usage: python scripts/hunt2/letf/hold.py
Writes reports/hunt2/letf/daily.parquet (s25_2x .. s125_2x, s25_1x .. s125_1x on the gated scored days), gates.json,
hold_trades.csv (every trade of the frozen variant, $50K, 2x and 1x P&L) and hold_info.json (per era, per year, capacity,
placebo).
"""
import json
import os
import subprocess
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import letf as L  # noqa: E402

G = L.G
WT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
OUT = os.path.join(WT, "reports", "hunt2", "letf")


def committed(path):
    """frozen.json must be committed and unchanged (the freeze)."""
    rel = os.path.relpath(path, WT)
    st = subprocess.run(["git", "-C", WT, "status", "--porcelain", rel], capture_output=True, text=True).stdout.strip()
    log = subprocess.run(["git", "-C", WT, "log", "--format=%H", "-1", "--", rel], capture_output=True, text=True).stdout
    return st == "" and log.strip() != ""


def tstats(T):
    f = T[T.status == "filled"] if len(T) else T
    if len(f) == 0:
        return dict(trades=0)
    return dict(trades=int(len(f)), mean_gross_bp=float((1e4 * f.gross / f.notional).mean()),
                mean_net_bp=float((1e4 * f.pnl / f.notional).mean()), hit=float((f.pnl > 0).mean()),
                pnl=float(f.pnl.sum()), mean_notional=float(f.notional.mean()),
                fill_share=float(f.contracts.sum() / max(1, f.target.sum())),
                by_asset={a: int(n) for a, n in f.asset.value_counts().items()},
                stale_exits=int(f.stale.sum()) if "stale" in f else 0)


def main():
    fzp = os.path.join(OUT, "frozen.json")
    assert committed(fzp), "frozen.json is not committed: no HOLD read before the freeze"
    fz = json.load(open(fzp))
    p = fz["params"]
    leg, k, uni, theta = p["leg"], p["k"], L.UNIVERSE[p["universe"]], p["theta"]
    series = {f"s{c // 1000}_{m}x": [] for c in L.CAPS for m in (2, 1)}
    th25 = []
    info, trades, era_days = {}, [], {}
    for era in ("sel", "chk", "early"):
        D = L.signals(era, allow_hold=True)
        days = L.scored_days(uni, era, allow_hold=True)
        era_days[era] = days
        for cap in L.CAPS:
            for m in (2, 1):
                r, T = L.sleeve(D, leg, k, uni, cap, mult=float(m), theta=theta, days=days)
                series[f"s{cap // 1000}_{m}x"].append(r)
                if cap == 50000:
                    T = T.assign(era=era, mult=m)
                    trades.append(T)
                    info.setdefault(era, {})[f"{m}x"] = tstats(T)
        if leg == "mkr":
            r25, T25 = L.sleeve(D, leg, k, uni, 50000, mult=2.0, theta=0.25, days=days)
            th25.append(r25)
            info[era]["theta025_2x"] = tstats(T25)
        info[era]["scored_days"] = int(len(days))
        info[era]["trading_days"] = int(D.day.nunique())
        info[era]["gate_open_share"] = {a: float(g.gate.mean()) for a, g in D[D.asset.isin(uni)].groupby("asset")}
        info[era]["signals"] = int((D[D.asset.isin(uni)].gate & D[D.asset.isin(uni)].cok &
                                    (D[D.asset.isin(uni)].z.abs() >= k)).sum())
        if era == "early":                                     # the SPEC's placebo: the same rule with the gate off
            Dp = D.copy()
            Dp["gate"] = True
            lo, hi = L.era_window("early")
            pdays = pd.date_range(lo, hi, freq="D")
            rp, Tp = L.sleeve(Dp, leg, k, uni, 50000, mult=2.0, theta=theta, days=pdays)
            rp1, Tp1 = L.sleeve(Dp, leg, k, uni, 50000, mult=1.0, theta=theta, days=pdays)
            info["early_placebo_gate_off"] = dict(stats_2x=tstats(Tp), stats_1x=tstats(Tp1),
                                                  sleeve_sharpe_2x=G.sharpe(rp), sleeve_sharpe_1x=G.sharpe(rp1),
                                                  days=len(pdays), note="descriptive only, never gated")
    S = {k_: pd.concat(v).sort_index() for k_, v in series.items()}
    S = pd.DataFrame(S)
    S = S[~S.index.duplicated()]
    # eras gated: >= 60 scored days and >= 10 trades (2x, $50K); sel is DEV and always kept for the a choice
    gated = ["sel"]
    for era in ("chk", "early"):
        n_d, n_t = info[era]["scored_days"], info[era]["2x"].get("trades", 0)
        info[era]["gated"] = bool(n_d >= 60 and n_t >= 10)
        if info[era]["gated"]:
            gated.append(era)
    gdays = pd.DatetimeIndex(sorted(set().union(*[set(era_days[e]) for e in gated])))
    daily = S.reindex(gdays).fillna(0.0)
    daily.to_parquet(os.path.join(OUT, "daily.parquet"))
    caps = {25000: "s25", 50000: "s50", 75000: "s75", 125000: "s125"}
    g = G.path_b({c: daily[f"{n}_2x"] for c, n in caps.items()}, gdays)
    g1 = G.path_b({c: daily[f"{n}_1x"] for c, n in caps.items()}, gdays)
    g["at_1x"] = {kk: g1[kk] for kk in g1 if kk.startswith(("hold_", "chk_", "early_", "full_", "dev_")) or
                  kk in ("a", "years", "B1", "B2", "B3", "B4", "pass")}
    g["gated_eras"] = gated
    g["scored_days"] = int(len(gdays))
    g["variant"], g["idea"] = fz["variant"], "letf"
    # descriptive: an ungated HOLD era with scored days, through the same test (never a gate)
    for era in ("chk", "early"):
        if era not in gated and len(era_days[era]):
            alld = pd.DatetimeIndex(sorted(set(gdays) | set(era_days[era])))
            gd = G.path_b({c: S[f"{n}_2x"].reindex(alld).fillna(0.0) for c, n in caps.items()}, alld)
            g[f"descriptive_{era}"] = {kk: gd[kk] for kk in gd if kk.startswith(era)}
    json.dump(g, open(os.path.join(OUT, "gates.json"), "w"), indent=1, default=str)
    T = pd.concat(trades, ignore_index=True)
    T.to_csv(os.path.join(OUT, "hold_trades.csv"), index=False)
    # years and per-era sleeve stats on the gated days ($50K, 2x / 1x)
    s50 = daily["s50_2x"]
    info["sleeve_years_2x_50k"] = {int(y): float(v) for y, v in s50.groupby(s50.index.year).sum().items()}
    info["sleeve_years_1x_50k"] = {int(y): float(v) for y, v in daily["s50_1x"].groupby(daily.index.year).sum().items()}
    for era in gated:
        m = G.era_of(daily.index) == era
        info[era]["sleeve_sharpe_2x_50k"] = G.sharpe(daily["s50_2x"][m])
        info[era]["sleeve_sharpe_1x_50k"] = G.sharpe(daily["s50_1x"][m])
    if th25:
        info["theta025_s50_2x_sharpe_by_era"] = {e: G.sharpe(r) for e, r in zip(("sel", "chk", "early"), th25)}
    json.dump(info, open(os.path.join(OUT, "hold_info.json"), "w"), indent=1, default=str)
    keys = ("a", "hold_gain", "hold_t_alpha", "chk_gain", "early_gain", "full_gain", "dsr", "years", "B1", "B2", "B3",
            "B4", "pass")
    print(json.dumps({kk: g.get(kk) for kk in keys}, indent=1, default=str))
    print(json.dumps({e: info[e] for e in ("sel", "chk", "early")}, indent=1, default=str))


if __name__ == "__main__":
    main()
