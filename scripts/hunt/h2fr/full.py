#!/usr/bin/env python3
"""H2 (FR): the frozen variant (reports/hunt/h2fr/frozen.json) over all scored days, run once after the freeze commit.

Writes reports/hunt/h2fr/: gates.json, daily.parquet (s30_2x, s50_2x, s30_1x, s50_1x; theta 0.5), checks.json,
full/trades_*.parquet (standalone trades), full/portfolio_30k.parquet, full/perp_trades.parquet (input of prints.py).

usage: python scripts/hunt/h2fr/full.py            # the HOLD read (all scored days)
       python scripts/hunt/h2fr/full.py --dev-dry  # plumbing test on DEV days only (no gates, no HOLD data loaded)
"""
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "scripts", "hunt"))
import common  # noqa: E402
import dev  # noqa: E402
import fr  # noqa: E402
import gates  # noqa: E402

OUT = os.path.join(ROOT, "reports", "hunt", "h2fr")


def rnd(x, n=4):
    if isinstance(x, dict):
        return {str(k): rnd(v, n) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [rnd(v, n) for v in x]
    if isinstance(x, (float, np.floating)):
        return None if not np.isfinite(x) else round(float(x), n)
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (np.bool_,)):
        return bool(x)
    return x


def main():
    dry = "--dev-dry" in sys.argv
    F = json.load(open(os.path.join(OUT, "frozen.json")))
    cfg = F["variant"]
    end = fr.DEV_END if dry else fr.FULL_END
    days = gates.ERA_DAYS[gates.ERA_DAYS < gates.HOLD0] if dry else gates.ERA_DAYS
    outdir = os.path.join(OUT, "full_dry" if dry else "full")
    dev.build([dev.base_cfg(cfg)], end=end, outdir=outdir)
    T = dev.load_trades(cfg, outdir=outdir)
    S, Ps = {}, {}
    for C in (30000.0, 50000.0, 100000.0):
        for th in (0.5, 0.25):
            for col in ("pnl_2x", "pnl_1x", "pnl_2x_fee0.12", "pnl_2x_fee0.30", "pnl_1x_fee0.12", "pnl_1x_fee0.30"):
                s, P, n = dev.series(T, C, th, days, col)
                S[(int(C), th, col)] = s
                Ps[(int(C), th)] = P
    D = pd.DataFrame({"s30_2x": S[(30000, 0.5, "pnl_2x")], "s50_2x": S[(50000, 0.5, "pnl_2x")],
                      "s30_1x": S[(30000, 0.5, "pnl_1x")], "s50_1x": S[(50000, 0.5, "pnl_1x")]})
    D.index.name = "day"
    if dry:
        gates.assert_dev_only(D.s30_2x)
    out = dict(variant=cfg, dry=dry)
    if not dry:
        g = gates.path_b({30000: D.s30_2x, 50000: D.s50_2x}, days=days)
        out["gates_2x"] = g
        out["info_1x"] = gates.path_b({30000: D.s30_1x, 50000: D.s50_1x}, days=days)
        out["info_theta025_2x"] = gates.path_b({30000: S[(30000, 0.25, "pnl_2x")], 50000: S[(50000, 0.25, "pnl_2x")]},
                                               days=days)
        for fee in ("0.12", "0.30"):
            out[f"info_fee{fee}_2x"] = gates.path_b({30000: S[(30000, 0.5, f"pnl_2x_fee{fee}")],
                                                     50000: S[(50000, 0.5, f"pnl_2x_fee{fee}")]}, days=days)
        s100 = S[(100000, 0.5, "pnl_2x")]
        inc = gates.incumbent(100e3, days=days)
        out["path_a_applies"] = bool(gates.sharpe(s100) > gates.sharpe(inc))
        if out["path_a_applies"]:
            out["path_a"] = gates.path_a(s100, days=days)
    pc = dev.parse(cfg)
    out["checks"] = checks(T, Ps, S, days, outdir, pc["W"], pc["k"])
    tag = "_dry" if dry else ""
    with open(os.path.join(OUT, f"gates{tag}.json"), "w") as f:
        json.dump(rnd(out), f, indent=1, default=str)
    if not dry:
        D.to_parquet(os.path.join(OUT, "daily.parquet"))
    print(json.dumps(rnd({k: v for k, v in out.items() if k in ("gates_2x", "info_1x", "path_a_applies")}), indent=1,
                     default=str)[:6000])


def checks(T, Ps, S, days, outdir, W, k):
    """The SPEC's checks (descriptive), on the 30K / theta 0.5 portfolio, exits on scored days."""
    tag = "30k_0.5"
    P = Ps[(30000, 0.5)]
    P = P[P[f"exit_day@{tag}"].isin(days)].copy()
    P.to_parquet(os.path.join(outdir, "portfolio_30k.parquet"))
    hold0 = gates.HOLD0
    P["era"] = np.where(P[f"exit_day@{tag}"] >= hold0, "hold", "dev")
    P["year"] = pd.DatetimeIndex(P[f"exit_day@{tag}"]).year
    c = {}
    E = pd.read_parquet(os.path.join(outdir, "events.parquet"))
    E = E[(E.W == W) & (E.k == k)].copy()
    E["day"] = pd.DatetimeIndex(E.t0_ts).normalize()
    E = E[E.day.isin(days)]
    c["events_by_year_coin"] = E.groupby([pd.DatetimeIndex(E.day).year, "coin"]).size().unstack(fill_value=0).to_dict()
    c["events_total_scored"] = int(len(E))
    c["trades_by_year_coin"] = P.groupby(["year", "coin"]).size().unstack(fill_value=0).to_dict()
    c["trades_total"] = int(len(P))
    agg = lambda X: dict(n=int(len(X)), gross_bp=X[f"gross_bp@{tag}"].mean(), net1x_bp=X[f"bp_1x@{tag}"].mean(),  # noqa
                         net2x_bp=X[f"bp_2x@{tag}"].mean(), pnl2x_usd=X[f"pnl_2x@{tag}"].sum(),
                         hit2x=(X[f"pnl_2x@{tag}"] > 0).mean(), tp_frac=X[f"tp_frac@{tag}"].mean())
    c["by_year"] = {int(y): agg(X) for y, X in P.groupby("year")}
    c["by_era"] = {e: agg(X) for e, X in P.groupby("era")}
    c["by_coin"] = {k: agg(X) for k, X in P.groupby("coin")}
    c["by_mode_spot_vs_perp_priced"] = {k: agg(X) for k, X in P.groupby("mode")}
    c["by_mode_era"] = {f"{m}|{e}": agg(X) for (m, e), X in P.groupby(["mode", "era"])}
    et = pd.DatetimeIndex(P.dec_ts).tz_localize("UTC").tz_convert("America/New_York")
    P["et_hour"] = et.hour
    c["by_et_hour"] = {int(h): agg(X) for h, X in P.groupby("et_hour")}
    ets = pd.DatetimeIndex(E.t0_ts).tz_localize("UTC").tz_convert("America/New_York")
    c["events_by_et_hour"] = E.groupby(ets.hour).size().to_dict()
    # incumbent overlap
    inc = gates.incumbent(100e3, days=days)
    eday = pd.DatetimeIndex(P.entry_ts).normalize()
    big = inc.abs() >= inc[inc != 0].abs().quantile(0.9)
    top = inc >= inc[inc > 0].quantile(0.9)
    c["r208_overlap"] = dict(share_trade_days_inc_active=float(inc.reindex(eday).ne(0).mean()),
                             share_trade_days_inc_top10pct_abs=float(big.reindex(eday).fillna(False).mean()),
                             share_trade_days_inc_top10pct_gain=float(top.reindex(eday).fillna(False).mean()),
                             base_rate_inc_active=float((inc != 0).mean()), base_rate_top10pct_abs=float(big.mean()))
    s = S[(30000, 0.5, "pnl_2x")]
    tot = float(s.sum())
    c["top3_days_share_2x"] = float(s.nlargest(3).sum() / tot) if tot > 0 else None
    c["top3_days_2x"] = {str(k.date()): float(v) for k, v in s.nlargest(3).items()}
    c["sleeve_total_return_2x"] = tot
    c["corr_inc_all"] = float(np.corrcoef(s, inc)[0, 1]) if s.std() > 0 else None
    worst = inc.nsmallest(int(round(0.05 * len(inc))))
    c["sleeve_on_inc_worst5pct_days_2x"] = float(s.reindex(worst.index).sum())
    eq = (1 + s).cumprod()
    c["maxdd_daily_2x"] = float((eq / eq.cummax() - 1).min())
    c["mae_bp_quantiles"] = P.mae_bp.quantile([0.5, 0.9, 0.99]).to_dict()
    c["mae_worst_bp"] = float(P.mae_bp.min())
    # capacity
    c["capacity"] = dict(tp_frac_theta05=float(P[f"tp_frac@{tag}"].mean()),
                         tp_frac_theta025=float(Ps[(30000, 0.25)].loc[lambda X: X["exit_day@30k_0.25"].isin(days),
                                                                      "tp_frac@30k_0.25"].mean()),
                         notional_over_capital=float((P[f"notional@{tag}"] / 30000).mean()),
                         entry_minute_volume_over_size_median=float(
                             (P.vol_e / (P[f"notional@{tag}"] / P.px_e)).median()),
                         entry_minute_volume_over_size_p10=float(
                             (P.vol_e / (P[f"notional@{tag}"] / P.px_e)).quantile(0.1)))
    for C in (30000, 50000, 100000):
        for th in (0.5, 0.25):
            for col in ("pnl_2x", "pnl_1x"):
                x = S[(C, th, col)]
                c.setdefault("sleeve_sharpe", {})[f"{C}|{th}|{col}"] = dict(
                    all=gates.sharpe(x), dev=gates.sharpe(x[x.index < hold0]),
                    hold=gates.sharpe(x[x.index >= hold0]) if (x.index >= hold0).any() else None,
                    ret_yr=float(x.mean() * 365))
    for fee in ("0.12", "0.30"):
        for col in (f"pnl_2x_fee{fee}", f"pnl_1x_fee{fee}"):
            x = S[(30000, 0.5, col)]
            c.setdefault("fee_sensitivity", {})[col] = dict(sharpe_all=gates.sharpe(x), ret_yr=float(x.mean() * 365))
    perp = T[T["mode"] == "perp"].copy()
    keep = set(zip(P.coin, P.entry_ts))
    perp["in_portfolio_30k"] = [(a, b) in keep for a, b in zip(perp.coin, perp.entry_ts)]
    cols = ["coin", "mode", "dec_ts", "entry_ts", "px_e", "tp", "px_x", "e", "x", "in_portfolio_30k",
            "n@30k_0.5", "n_tp@30k_0.5", "exit_ts@30k_0.5", "gross_bp@30k_0.5", "bp_2x@30k_0.5", "bp_1x@30k_0.5"]
    perp[cols].to_parquet(os.path.join(outdir, "perp_trades.parquet"))
    return c


if __name__ == "__main__":
    main()
