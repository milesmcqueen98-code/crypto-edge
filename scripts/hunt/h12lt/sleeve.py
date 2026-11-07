#!/usr/bin/env python3
"""H12 (LT) sleeve (reports/hunt/h12lt/SPEC.md): scripts/wick1m/sim.py `evaluate` on the precomputed tranches of the
sleeve's trade list (universe coins only), with the incumbent's rules exactly as scripts/hunt/incumbent.py applies
them (ladder 4/6/8 sigma in thirds, kappa = 0.2% of the trailing 30-day median daily USD volume, every AI signal,
cash <= 100% of capital, Coinbase spot only, the 'instant' bound) and the hunt cost model instead of sim.py's own
tiers: 6 bp maker, 12.5 bp taker, 2 bp half-spread on market exits, x2 for every gate (the account's VIP1 tier).
sim.py's square-root impact on market exits is kept unchanged (1x).

  dev     the SPEC's trial grid on DEV days only (2025-01-01 .. 2026-05-31; END fixed, HOLD never read); logs every
          trial (gates.log_trial, gates.dev_book), writes reports/hunt/h12lt/trials_dev.csv and frozen.json.
  sample  a fixed-seed random sample of the frozen variant's DEV fills for the print check (data/hunt/h12lt).
  hold    after the freeze commit: the frozen variant over every scored day; gates.path_b; gates.json, daily.parquet,
          diagnostics.json.
usage: python scripts/hunt/h12lt/sleeve.py dev|sample|hold
"""
import json
import os
import subprocess
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, os.path.join(ROOT, "scripts", "hunt"))
sys.path.insert(0, os.path.join(ROOT, "scripts", "wick1m"))
import gates  # noqa: E402
import sim  # noqa: E402

OUT = os.path.join(ROOT, "reports", "hunt", "h12lt")
IDEA = "h12lt"
DEV0, DEV1 = pd.Timestamp("2025-01-01"), pd.Timestamp("2026-05-31")       # DEV end fixed (HOLD starts 2026-06-01)
ALL1 = gates.END
W0 = {4.0: 1, 6.0: 1, 8.0: 1}
MAKER, TAKER, HS_BP = 6e-4, 12.5e-4, 2.0
SCORED = gates.ERA_DAYS[gates.ERA_DAYS >= DEV0]
# sim.evaluate reads the perp venue's fee table; the spot sleeve has no perp capacity (in_perp = 0), so no perp
# fill is ever priced. Return empty maps instead of reading reports/lab/cost_table.csv (absent in sparse checkouts).
sim.perp_cost = lambda: ({}, {})

# The SPEC's trial grid (<= 6). Every variant uses the incumbent's rules except the one change it names.
GRID = {
    "T1_base": dict(pre="base", note="universe as defined, incumbent rules"),
    "T2_vol1m": dict(pre="base", min_vol=1e6, note="base trade list, coins with 2024 median volume >= $1M"),
    "T3_ai70": dict(pre="ai70", note="signals with prediction >= the quarter's 70th pct of training predictions"),
    "T4_noladder": dict(pre="base", weights={4.0: 1}, note="base, 4-sigma parent only (whole signal at 4 sigma)"),
    "T5_kappa01": dict(pre="base", kappa=0.001, note="base, kappa = 0.1% of trailing ADV"),
}
SIMPLICITY = ["T1_base", "T4_noladder", "T5_kappa01", "T2_vol1m", "T3_ai70"]     # tie-break order (simpler first)


def universe():
    return pd.read_csv(os.path.join(OUT, "universe.csv"))


def load_pre(name, min_vol=None):
    P = pd.read_pickle(os.path.join(OUT, f"pre_{name}.pkl"))
    for col in ("in_perp", "tp_perp"):                   # the spot sleeve cannot fill on the perp venue
        if col in P:
            P[col] = 0.0
    if min_vol is not None:
        U = universe()
        P = P[P.coin.isin(set(U.coin[U.vol2024 >= min_vol]))]
    return P


def run(P, C, lo, hi, theta=0.5, mult=2.0, hs=HS_BP, kappa=0.002, weights=None, drop=False, mtm=False):
    """Daily return on capital C over calendar days lo..hi (P&L booked on the exit day; P&L booked after hi dropped)."""
    W = P[(P.ts >= lo) & (P.ts < pd.Timestamp(hi) + pd.Timedelta(days=1))]
    sim.SPOT_HS_BP = hs * mult
    tiers = [(0, MAKER * mult, TAKER * mult)]
    days = (pd.Timestamp(hi) - pd.Timestamp(lo)).days + 1
    Q, daily, info = sim.evaluate(W, kappa=kappa, trade_list="all", theta=theta, C=C, days=days, gross_cap=1.0,
                                  drop_same_minute=drop, weights=weights or W0, use_bitstamp=False, tiers=tiers,
                                  mtm=mtm)
    idx = pd.date_range(lo, hi, freq="D")
    return daily.reindex(idx, fill_value=0.0) / C, Q, info


def n_trades(Q):
    return int((Q.groupby(["ts", "coin"]).fill.sum() > 0).sum())


def variant_kw(v):
    g = GRID[v]
    return dict(kappa=g.get("kappa", 0.002), weights=g.get("weights"))


# ------------------------------------------------------------------ DEV: trial grid, selection, freeze
def dev():
    rows = []
    for v, g in GRID.items():
        P = load_pre(g["pre"], g.get("min_vol"))
        P = P[P.ts < gates.HOLD0]
        r, Q, info = run(P, 30e3, DEV0, DEV1, mult=2.0, **variant_kw(v))
        gates.assert_dev_only(r)
        ri70 = gates.incumbent(70e3, 0.5, "instant", r.index)
        at = gates.alpha_test(r, ri70)
        scr = gates.dev_screen(r)
        bk = gates.dev_book(r)
        nt = n_trades(Q)
        gates.log_trial(IDEA, v, bk, note=g["note"], sleeve_sharpe=scr["sleeve_sharpe"], t_alpha_70k=at["t_alpha"],
                        trades=nt, capital=30e3, costs="2x")
        r1, _, _ = run(P, 30e3, DEV0, DEV1, mult=1.0, **variant_kw(v))
        rows.append(dict(variant=v, note=g["note"], trades=nt, coins=int(Q[Q.fill > 0].coin.nunique()),
                         filled_usd=float(Q.fill.sum()), pnl_usd=float(Q.pnl.sum()),
                         net_bp=float(Q.pnl.sum() / Q.fill.sum() * 1e4) if Q.fill.sum() > 0 else np.nan,
                         sleeve_sharpe=scr["sleeve_sharpe"], t_alpha_70k=at["t_alpha"], t_alpha_100k=scr["t_alpha"],
                         beta=at["beta"], corr=scr["corr"], dev_book_sharpe=gates.sharpe(bk),
                         dev_inc_sharpe=gates.sharpe(gates.incumbent(100e3, 0.5, "instant", r.index)),
                         active_days=scr["active_days"], ret_yr=float(r.sum() / len(r) * 365),
                         sleeve_sharpe_1x=gates.sharpe(r1), maker_bp=info["maker_bp"], taker_bp=info["taker_bp"]))
        print(json.dumps(rows[-1], default=float), flush=True)
    T = pd.DataFrame(rows)
    T.to_csv(os.path.join(OUT, "trials_dev.csv"), index=False)
    ok = T[T.trades >= 100].copy()
    ok["simple"] = ok.variant.map({v: i for i, v in enumerate(SIMPLICITY)})
    best = ok.sort_values(["t_alpha_70k", "simple"], ascending=[False, True]).iloc[0] if len(ok) else None
    pd.set_option("display.width", 250)
    print(T.drop(columns=["note"]).round(3).to_string(index=False))
    if best is None:
        print("no variant has >= 100 DEV trades")
        return
    code = subprocess.run(["git", "-C", ROOT, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    F = dict(idea=IDEA, variant=best.variant, params=dict(GRID[best.variant], **variant_kw(best.variant)),
             rules=dict(theta=0.5, ladder="4/6/8 sigma thirds" if not GRID[best.variant].get("weights") else "4 sigma only",
                        gross_cap=1.0, bound="instant", venue="Coinbase spot only", costs="maker 6 / taker 12.5 / "
                        "half-spread 2 bp, x2 for gates", capital=[30000, 50000]),
             selection="highest DEV alpha t (sleeve $30K at 2x on the incumbent at $70K) among variants with >= 100 "
                       "DEV trades; ties to the simpler variant",
             code_commit=code, dev=best.drop(labels=["simple"]).to_dict(), trials_logged=len(T),
             frozen_utc=pd.Timestamp.now(tz="UTC").strftime("%Y-%m-%dT%H:%MZ"))
    json.dump(F, open(os.path.join(OUT, "frozen.json"), "w"), indent=1, default=float)
    print("FROZEN:", best.variant)


# ------------------------------------------------------------------ print sample (DEV fills of the frozen variant)
def sample(n=300, seed=12):
    F = json.load(open(os.path.join(OUT, "frozen.json")))
    v = F["variant"]
    g = GRID[v]
    P = load_pre(g["pre"], g.get("min_vol"))
    P = P[P.ts < gates.HOLD0]
    _, Q, _ = run(P, 30e3, DEV0, DEV1, mult=2.0, **variant_kw(v))
    q = Q[Q.fill > 0].copy()
    q = q.sample(n=min(n, len(q)), random_state=seed)
    U = universe().set_index("coin")
    q["pid"] = q.coin.map(U.pid)
    q["tick"] = q.coin.map(U.tick)
    q["fill_t"] = q.ts + pd.to_timedelta(q.f_off, unit="m")
    cols = ["pid", "coin", "ts", "fill_t", "k", "lvl", "tick", "in_spot", "fill", "tp_fill", "pnl"]
    d = os.path.join(ROOT, "data", "hunt", "h12lt")
    os.makedirs(d, exist_ok=True)
    q[cols].sort_values(["pid", "fill_t"]).to_csv(os.path.join(d, "print_sample.csv"), index=False)
    print(f"{len(q)} DEV fills sampled of {int((Q.fill > 0).sum())}")


# ------------------------------------------------------------------ HOLD (after the freeze commit)
def hold():
    F = json.load(open(os.path.join(OUT, "frozen.json")))
    v = F["variant"]
    g = GRID[v]
    P = load_pre(g["pre"], g.get("min_vol"))
    kw = variant_kw(v)
    S, Qs = {}, {}
    for C in (30e3, 50e3, 100e3):
        for mult in (2.0, 1.0):
            r, Q, info = run(P, C, DEV0, ALL1, mult=mult, **kw)
            S[f"s{int(C / 1e3)}_{int(mult)}x"] = r.reindex(SCORED).fillna(0.0)
            Qs[(C, mult)] = Q
        for name, extra in (("hs5", dict(hs=5.0)), ("th025", dict(theta=0.25)), ("minute", dict(drop=True))):
            r, Q, _ = run(P, C, DEV0, ALL1, mult=2.0, **kw, **extra)
            S[f"s{int(C / 1e3)}_2x_{name}"] = r.reindex(SCORED).fillna(0.0)
    daily = pd.DataFrame({k: S[k] for k in ("s30_2x", "s50_2x", "s30_1x", "s50_1x")})
    daily.index.name = "day"
    daily.to_parquet(os.path.join(OUT, "daily.parquet"))
    pd.DataFrame(S).to_parquet(os.path.join(OUT, "daily_all.parquet"))
    G = gates.path_b({30000: S["s30_2x"], 50000: S["s50_2x"]}, days=SCORED)
    info = {
        "1x": gates.path_b({30000: S["s30_1x"], 50000: S["s50_1x"]}, days=SCORED),
        "2x_hs5": gates.path_b({30000: S["s30_2x_hs5"], 50000: S["s50_2x_hs5"]}, days=SCORED),
        "2x_theta025": gates.path_b({30000: S["s30_2x_th025"], 50000: S["s50_2x_th025"]}, theta=0.25, days=SCORED),
        "2x_minute_bound": gates.path_b({30000: S["s30_2x_minute"], 50000: S["s50_2x_minute"]}, days=SCORED),
    }
    for vz_mode in ("pooled", "plain"):
        N, V = gates.n_trials(vz_mode)
        bk = (G["a"] * gates.incumbent(G["a"] * 100e3, 0.5, "instant", SCORED)
              + (1 - G["a"]) * S["s30_2x" if G["a"] == 0.7 else "s50_2x"])
        info[f"dsr_{vz_mode}"] = dict(zip(("dsr", "sr0_ann"), gates.deflated_sharpe(bk, N, V)), N=N, vz=V)
    inc100 = gates.incumbent(100e3, 0.5, "instant", SCORED)
    if gates.sharpe(S["s100_2x"]) > gates.sharpe(inc100):
        info["path_a"] = gates.path_a(S["s100_2x"], days=SCORED)
    out = dict(idea=IDEA, variant=v, gates_2x=G, info=info,
               sleeve_sharpe_100k_2x=gates.sharpe(S["s100_2x"]), inc_sharpe_100k=gates.sharpe(inc100))
    json.dump(out, open(os.path.join(OUT, "gates.json"), "w"), indent=1, default=float)
    diagnostics(P, kw, S, Qs, G)
    print(json.dumps({k: G[k] for k in ("a", "full_t_alpha", "hold_t_alpha", "dev_t_alpha", "full_gain", "hold_gain",
                                         "dev_gain", "dsr", "G1", "G2", "G3", "G4", "G5", "years")}, default=float))


def diagnostics(P, kw, S, Qs, G):
    U = universe().set_index("coin")
    Q = Qs[(30e3, 2.0)].copy()
    Q["year"] = Q.ts.dt.year
    Q["era"] = np.where(Q.ts >= gates.HOLD0, "hold", "dev")
    Q["tier"] = pd.cut(Q.coin.map(U.vol2024), [0.5e6, 1e6, 2e6, 3e6], right=False, labels=["0.5-1M", "1-2M", "2-3M"])
    Q["delisted"] = Q.coin.map(U.status) == "delisted"
    f = Q[Q.fill > 0]

    def agg(by):
        a = f.groupby(by, observed=True).agg(fills=("fill", "size"), filled_usd=("fill", "sum"), pnl_usd=("pnl", "sum"))
        a["net_bp"] = a.pnl_usd / a.filled_usd * 1e4
        return a.round(2)

    D = {}
    D["by_year"] = agg("year").to_dict("index")
    D["by_era"] = agg("era").to_dict("index")
    D["by_tier"] = agg("tier").to_dict("index")
    D["by_rung"] = agg("k").to_dict("index")
    D["by_coin"] = agg("coin").sort_values("pnl_usd").to_dict("index")
    D["delisted"] = dict(in_universe=int((U.status == "delisted").sum()), traded=int(f[f.delisted].coin.nunique()),
                         coins=sorted(f[f.delisted].coin.unique()), **agg("delisted").to_dict("index").get(True, {}))
    D["coins_traded"] = dict(all=int(f.coin.nunique()), dev=int(f[f.era == "dev"].coin.nunique()),
                             hold=int(f[f.era == "hold"].coin.nunique()), universe=len(U))
    D["trades"] = dict(all=n_trades(Q), dev=n_trades(Q[Q.era == "dev"]), hold=n_trades(Q[Q.era == "hold"]))
    want = np.minimum(0.25 * 30e3, kw["kappa"] * Q.adv.fillna(0.0).to_numpy()) / (3.0 if not kw["weights"] else 1.0)
    D["capacity_30k"] = dict(filled_usd=float(Q.fill.sum()), wanted_usd_filled_rungs=float(want.sum()),
                             fill_ratio=float(Q.fill.sum() / want.sum()) if want.sum() > 0 else np.nan,
                             tp_share=float(Q.tp_fill.sum() / Q.fill.sum()) if Q.fill.sum() > 0 else np.nan,
                             mean_fill_usd=float(f.fill.mean()))
    for cap in (30e3, 50e3):                               # peak cash in open positions (fills until their exits)
        q = Qs[(cap, 2.0)]
        q = q[q.fill > 0]
        t_tp = q.fill_t + pd.to_timedelta(np.where(q.tp_off >= 0, q.tp_off, 60), unit="m")
        ev = pd.concat([pd.Series(q.fill.to_numpy(), index=q.fill_t.to_numpy()),
                        pd.Series(-q.tp_fill.to_numpy(), index=t_tp.to_numpy()),
                        pd.Series(-(q.fill - q.tp_fill).to_numpy(), index=(q.fill_t + pd.Timedelta(minutes=60)).to_numpy())])
        ev = ev.groupby(level=0).sum().sort_index().cumsum()
        D[f"peak_open_usd_{int(cap / 1e3)}k"] = float(ev.max()) if len(ev) else 0.0
    s = S["s30_2x"]
    inc = gates.incumbent(100e3, 0.5, "instant", SCORED)
    for name, m in (("all", np.ones(len(s), bool)), ("dev", s.index < gates.HOLD0), ("hold", s.index >= gates.HOLD0)):
        D[f"corr_{name}"] = float(np.corrcoef(s[m], inc[m])[0, 1])
    act = s != 0
    D["same_day"] = dict(sleeve_active_days=int(act.sum()), both_active=int((act & (inc != 0)).sum()),
                         share_sleeve_pnl_on_inc_active_days=float(s[act & (inc != 0)].sum() / s.sum()) if s.sum() else np.nan)
    worst = inc.nsmallest(10).index
    D["inc_worst10"] = dict(days=[str(d.date()) for d in worst], inc_sum=float(inc[worst].sum()),
                            sleeve_sum=float(s[worst].sum()), sleeve_pos_days=int((s[worst] > 0).sum()))
    pnl = s * 30e3
    top = pnl.sort_values(ascending=False)
    D["top3_share"] = float(top.head(3).sum() / pnl.sum()) if pnl.sum() else np.nan
    D["top3_days"] = [str(d.date()) for d in top.head(3).index]
    for k_, r in S.items():
        D.setdefault("sleeve_stats", {})[k_] = dict(
            sharpe_all=gates.sharpe(r), sharpe_dev=gates.sharpe(r[r.index < gates.HOLD0]),
            sharpe_hold=gates.sharpe(r[r.index >= gates.HOLD0]), ret_yr=float(r.sum() / len(r) * 365),
            years={int(y): float(v) for y, v in r.groupby(r.index.year).sum().items()})
    _, _, inf = run(P, 30e3, DEV0, ALL1, mult=2.0, mtm=True, **kw)
    st = sim.period_stats(s * 30e3, 30e3, DEV0, ALL1, equity=inf.get("equity"))
    D["period_stats_30k_2x"] = {k: st.get(k) for k in ("ret_yr", "sharpe", "maxdd", "maxdd_mtm", "top3_share",
                                                        "sharpe_p05", "sharpe_p95")}
    json.dump(D, open(os.path.join(OUT, "diagnostics.json"), "w"), indent=1, default=float)


# ------------------------------------------------------------------ print check summary (DEV sample)
def prints(ddir=None):
    """Candle-vs-print confirmation of sampled DEV fills (fetch.py trades): confirm = a print at or below the level
    minus one tick in the fill minute; print through-volume vs the candle estimate; realised half-spread."""
    import glob
    ddir = ddir or os.path.join(ROOT, "data", "hunt", "h12lt")
    R = pd.concat([pd.read_csv(f) for f in sorted(glob.glob(os.path.join(ddir, "print_check_*.csv")))],
                  ignore_index=True)
    ok = R[R.n_trades > 0].copy()
    ok["ratio"] = ok.print_through_usd / ok.cand_through_usd.replace(0, np.nan)
    ok["fill_le_half_print"] = ok.fill_usd <= 0.5 * ok.print_through_usd + 1e-9
    out = dict(sampled=len(R), with_prints=len(ok), fetch_failed=int((R.n_trades < 0).sum()),
               no_prints=int((R.n_trades == 0).sum()),
               confirm_rate=float(ok.confirm.mean()), touch_rate=float(ok.touch.mean()),
               confirm_rate_parent=float(ok[ok.k == 4.0].confirm.mean()) if (ok.k == 4.0).any() else np.nan,
               confirm_rate_deeper=float(ok[ok.k > 4.0].confirm.mean()) if (ok.k > 4.0).any() else np.nan,
               print_vs_candle_through_median=float(ok.ratio.median()),
               print_vs_candle_through_sum=float(ok.print_through_usd.sum() / ok.cand_through_usd.sum()),
               fill_within_half_print_through=float(ok.fill_le_half_print.mean()),
               fill_usd_confirmed_share=float(ok.fill_usd[ok.confirm].sum() / ok.fill_usd.sum()),
               half_spread_bp_median=float(ok.half_spread_bp_med.median()),
               half_spread_bp_mean_of_medians=float(ok.half_spread_bp_med.mean()),
               half_spread_bp_p75=float(ok.half_spread_bp_med.quantile(0.75)),
               tick_bp_median=float(ok.tick_bp.median()), coins=int(ok.coin.nunique()))
    json.dump(out, open(os.path.join(OUT, "print_check.json"), "w"), indent=1, default=float)
    print(json.dumps(out, indent=1, default=float))


if __name__ == "__main__":
    fn = {"dev": dev, "sample": sample, "hold": hold, "prints": prints}[sys.argv[1]]
    fn(*sys.argv[2:])
