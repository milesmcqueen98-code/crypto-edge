#!/usr/bin/env python3
"""H7 (UL): short the perp ahead of large scheduled unlocks (reports/hunt/h7ul/SPEC.md).

Modes
  dev    DEV trial grid (SPEC: 16 core trials + 1 category split), each logged with gates.log_trial. Price tables are
         built only from bars that start before 2026-06-01 00:00 UTC, so no HOLD price is ever read in this mode.
  hold   after the freeze commit: the frozen variant over all scored days at 2x and 1x on $30K and $50K, gates.path_b,
         reports/hunt/h7ul/{daily.parquet, gates.json, trades.csv}.

Trade (SPEC, fixed): short at 16:00 UTC on U - d1 (taker), cover at 16:00 UTC on U + d2 (taker). U = the first day
DefiLlama's schedule shows the unlock (rule.py). Equal notional per event = 50% of sleeve capital in whole contracts.
At each entry: gross notional <= 2x capital AND the sum of CFM overnight initial margin (Nov 6 2026 rates,
reports/cfm_products.json; R3) <= capital; older positions keep priority, so an entry that would breach either cap is
skipped. Hedge variant: long BTC perp x trailing 30-day beta (daily closes before the entry day, clipped to [0, 3];
1.0 with < 20 returns). $150 minimum contract value at entry.
Prices: the coin's perp (data/cfm) when the perp was live on the entry day; otherwise Coinbase spot (1-minute, else
hourly) with the perp cost model plus a 10%/yr carry charge = HYPOTHETICAL SHORTABILITY. The BTC hedge leg uses the
BTC perp from its launch, spot before (a long; no carry charge).
Costs (common.py): $0.20/contract/side + 1.5x measured median half-spread for taker orders; funding 1 bp/8 h either
side, pro rata by the hour; every term (and the carry) doubled at 2x. Daily P&L is marked to market at 00:00 UTC
(the SPEC hint: positions last days), on sleeve capital, calendar days, 0 when idle.
"""
import argparse
import json
import os
import pickle
import subprocess
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, os.path.join(ROOT, "scripts", "hunt"))
sys.path.insert(0, HERE)
import common  # noqa: E402
import gates  # noqa: E402
import prices  # noqa: E402

OUT = os.path.join(ROOT, "reports", "hunt", "h7ul")
CACHE = os.environ.get("H7UL_CACHE", os.path.join(os.path.expanduser("~"), ".cache", "h7ul"))   # outside the repo
IDEA = "h7ul"
START = pd.Timestamp("2021-09-01")
DEV_END = gates.HOLD0                         # exclusive: first instant of HOLD
FULL_END = gates.END + pd.Timedelta(days=1)   # 2026-11-06 00:00: marks for 2026-11-05 need its 00:00 price
SIZE, GROSS_CAP, CARRY = 0.5, 2.0, 0.10
BETA_LO, BETA_HI, BETA_N, BETA_MIN = 0.0, 3.0, 30, 20


# ------------------------------------------------------------------ inputs
def margin_rates():
    P = json.load(open(os.path.join(ROOT, "reports", "cfm_products.json")))
    by_pid = {p["product_id"]: p for p in P}
    out = {}
    for c, (pid, _, _) in common.PERP.items():
        p = by_pid.get(pid)
        if p is None:
            continue
        om = p["future_product_details"]["overnight_margin_rate"]
        out[c] = (float(om["short_margin_rate"]), float(om["long_margin_rate"]))
    return out


def load_events(X, cat, end):
    e = pd.read_csv(os.path.join(OUT, "events.csv"), parse_dates=["U"])
    e = e[(np.isclose(e.X, X)) & (e.cat == cat)]
    # universe (common.py): a Coinbase US perp with 1-minute perp data in data/cfm (BNB, DOT, SHIB have none)
    have = {c for c in common.PERP if os.path.exists(os.path.join(common.DATA, "cfm", f"{c}.parquet"))}
    e = e[e.coin.isin(have) & (e.U >= START) & (e.U < end)]
    return e.sort_values(["U", "coin"]).reset_index(drop=True)


def price_tables(end, coins):
    os.makedirs(CACHE, exist_ok=True)
    f = os.path.join(CACHE, f"prices_{end.date()}.pkl")
    P = pickle.load(open(f, "rb")) if os.path.exists(f) else {}
    need = [c for c in coins if c not in P]
    if need:
        P.update(prices.build(need, START, end))
        pickle.dump(P, open(f, "wb"))
    for c in coins:                            # guard: nothing at or after `end`
        for k in ("spot", "perp"):
            t = P[c][k]
            if t is not None:
                assert t.index.max() <= end and (t.loc[t.index >= end, ["p16"]].isna().all().all())
    return P


# ------------------------------------------------------------------ one leg
def side_cost(coin, price, mult, fee_usd):
    """One taker side in bp of notional: per-contract fee at fee_usd + 1.5x half-spread (common.py), x mult."""
    size = common.PERP[coin][1]
    spread = common.perp_cost_bp(coin, price, taker=True, mult=mult) - common.perp_cost_bp(coin, price, mult=mult)
    return mult * fee_usd / (price * size) * 1e4 + spread


def leg_path(T, q, E, X, end, cost_coin, mult, fee_usd, carry):
    """Daily P&L ($) of q coin units (signed) bought/sold at 16:00 on E and closed at 16:00 on the first day >= X
    with a print (<= X + 3). T: daily table (m00 = price at 00:00, p16 = first trade at/after 16:00)."""
    m = T["m00"].ffill()
    p_in = T["p16"].get(E, np.nan)
    if not np.isfinite(p_in):
        return None
    last = end - pd.Timedelta(days=1)
    Xp = None
    for k in range(4):
        d = X + pd.Timedelta(days=k)
        if d > last:
            break
        if np.isfinite(T["p16"].get(d, np.nan)):
            Xp = d
            break
    if Xp is None:
        raise RuntimeError(f"no exit print for a leg exiting {X.date()} before {end.date()}")
    days = pd.date_range(E, Xp, freq="D")
    pnl = pd.Series(0.0, index=days)
    fund = pd.Series(0.0, index=days)
    p_out = float(T["p16"][Xp])
    a = abs(q)
    for d in days:
        start_px = p_in if d == E else float(m[d])
        end_px = p_out if d == Xp else float(m[d + pd.Timedelta(days=1)])
        pnl[d] += q * (end_px - start_px)
        hours = 24.0 - (16.0 if d == E else 0.0) - (8.0 if d == Xp else 0.0)
        fund[d] = a * start_px * (common.perp_funding_bp(hours, mult) / 1e4 + (carry * mult * hours / (24 * 365)))
    c_in = a * p_in * side_cost(cost_coin, p_in, mult, fee_usd) / 1e4
    c_out = a * p_out * side_cost(cost_coin, p_out, mult, fee_usd) / 1e4
    cost = fund.copy()
    cost[E] += c_in
    cost[Xp] += c_out
    if not np.isfinite(pnl).all():
        raise RuntimeError("non-finite mark")
    return dict(pnl=pnl - cost, gross=pnl, cost=cost, p_in=p_in, p_out=p_out, exit=Xp, fees=c_in + c_out,
                funding=float(fund.sum()))


def beta(close, coin_close, E):
    """Trailing 30-day beta of the coin on BTC from daily closes known before 16:00 on E (closes up to E 00:00)."""
    if close is None or coin_close is None:
        return 1.0
    a = np.log(coin_close[coin_close.index <= E]).diff().iloc[-BETA_N:]
    b = np.log(close[close.index <= E]).diff().iloc[-BETA_N:]
    x = pd.concat([a, b], axis=1, join="inner").dropna()
    if len(x) < BETA_MIN or x.iloc[:, 1].var() <= 0:
        return 1.0
    bt = np.cov(x.iloc[:, 0], x.iloc[:, 1])[0, 1] / x.iloc[:, 1].var()
    return float(np.clip(bt, BETA_LO, BETA_HI))


# ------------------------------------------------------------------ the book
def simulate(P, ev, d1, d2, hedge, capital, mult, end, fee_usd=common.PERP_FEE_USD, MR=None):
    MR = MR or margin_rates()
    legs, trades = [], []
    for r in ev.itertuples():
        U = pd.Timestamp(r.U)
        E, X = U - pd.Timedelta(days=d1), U + pd.Timedelta(days=d2)
        if E < START or X >= end:
            continue
        info = P[r.coin]
        hyp = not (info["live"] is not None and E >= info["live"])
        T = info["spot"] if hyp else info["perp"]
        p_in = T["p16"].get(E, np.nan) if T is not None else np.nan
        rec = dict(coin=r.coin, U=U.date(), entry=E.date(), size_supply=r.size, hyp=hyp, taken=False, why="")
        if not np.isfinite(p_in):
            rec["why"] = "no price"
            trades.append(rec)
            continue
        csz = common.PERP[r.coin][1]
        if p_in * csz < common.MIN_CONTRACT_USD:
            rec["why"] = f"contract ${p_in * csz:.0f} < $150"
            trades.append(rec)
            continue
        n = int(SIZE * capital // (p_in * csz))
        if n < 1:
            rec["why"] = "size < 1 contract"
            trades.append(rec)
            continue
        new = [dict(coin=r.coin, cost_coin=r.coin, q=-n * csz, T=T, hyp=hyp, rate=MR[r.coin][0], carry=CARRY if hyp else 0)]
        if hedge:
            b = beta(P["BTC"]["close"], info["close"], E)
            bt_live = P["BTC"]["live"] is not None and E >= P["BTC"]["live"]
            TB = P["BTC"]["perp"] if bt_live else P["BTC"]["spot"]
            pb = TB["p16"].get(E, np.nan)
            nb = int(round(b * n * csz * p_in / (pb * common.PERP["BTC"][1]))) if np.isfinite(pb) else 0
            rec["beta"] = round(b, 3)
            if nb > 0:
                new.append(dict(coin="BTC", cost_coin="BTC", q=nb * common.PERP["BTC"][1], T=TB, hyp=hyp,
                                rate=MR["BTC"][1], carry=0.0))   # hyp: the split follows the event; no carry on a long
        # caps at 16:00 on E: positions exiting at 16:00 on E are closed first
        open_ = [g for g in legs if g["E"] <= E < g["exit"]]

        def px(g):
            v = g["T"]["p16"].get(E, np.nan)
            return v if np.isfinite(v) else float(g["T"]["m00"].ffill().get(E, np.nan))
        gross = sum(abs(g["q"]) * px(g) for g in open_)
        marg = sum(abs(g["q"]) * px(g) * g["rate"] for g in open_)
        add_g = sum(abs(g["q"]) * g["T"]["p16"][E] for g in new)
        add_m = sum(abs(g["q"]) * g["T"]["p16"][E] * g["rate"] for g in new)
        if gross + add_g > GROSS_CAP * capital + 1e-6:
            rec["why"] = f"gross cap ({(gross + add_g) / capital:.2f}x)"
            trades.append(rec)
            continue
        if marg + add_m > capital + 1e-6:
            rec["why"] = f"margin cap ({(marg + add_m) / capital:.2f})"
            trades.append(rec)
            continue
        paths = []
        for g in new:
            pth = leg_path(g["T"], g["q"], E, X, end, g["cost_coin"], mult, fee_usd, g["carry"])
            if pth is None:
                raise RuntimeError("leg without entry price")
            paths.append(pth)
        for g, pth in zip(new, paths):
            g.update(E=E, exit=pth["exit"], path=pth)
            legs.append(g)
        main = paths[0]
        v_in = T["v16"].get(E, np.nan)
        v_out = T["v16"].get(main["exit"], np.nan)
        rec.update(part_in=n * csz / v_in if v_in > 0 else np.nan, part_out=n * csz / v_out if v_out > 0 else np.nan)
        rec.update(taken=True, exit=main["exit"].date(), contracts=n, notional=n * csz * p_in, p_in=main["p_in"],
                   p_out=main["p_out"], ret_coin=main["p_out"] / main["p_in"] - 1,
                   pnl=float(sum(p["pnl"].sum() for p in paths)), pnl_short=float(main["pnl"].sum()),
                   pnl_hedge=float(sum(p["pnl"].sum() for p in paths[1:])),
                   fees=float(sum(p["fees"] for p in paths)), funding=float(sum(p["funding"] for p in paths)),
                   hedge_notional=float(sum(abs(g["q"]) * g["path"]["p_in"] for g in new[1:])),
                   min_mark=float(min(main["gross"].cumsum().min(), 0.0)))
        trades.append(rec)
    days = pd.date_range(START, end - pd.Timedelta(days=1), freq="D")
    pnl = pd.Series(0.0, index=days)
    hyp_pnl = pd.Series(0.0, index=days)
    for g in legs:
        s = g["path"]["pnl"].reindex(days).fillna(0.0)
        pnl += s
        if g["hyp"]:
            hyp_pnl += s
    return pnl / capital, pd.DataFrame(trades), hyp_pnl / capital


def scored(r, end):
    days = gates.ERA_DAYS[gates.ERA_DAYS < end]
    return r.reindex(days).fillna(0.0)


def n_scored_events(tr, end):
    if tr.empty or "exit" not in tr:
        return 0
    days = set(gates.ERA_DAYS[gates.ERA_DAYS < end])
    k = 0
    for t in tr[tr.taken].itertuples():
        span = pd.date_range(pd.Timestamp(t.entry), pd.Timestamp(t.exit), freq="D")
        k += any(d in days for d in span)
    return k


def vname(d1, d2, X, hedge, cat):
    return f"d1={d1},d2={d2},X={X * 100:g}%,hedge={'beta' if hedge else 'none'},cat={cat}"


# ------------------------------------------------------------------ DEV grid
def run_dev(log=True):
    end = DEV_END
    ev_all = {(X, c): load_events(X, c, end) for X in (0.01, 0.025) for c in ("all", "ti")}
    coins = sorted(set().union(*[set(e.coin) for e in ev_all.values()]) | {"BTC"})
    P = price_tables(end, coins)
    MR = margin_rates()
    inc70 = gates.incumbent(70e3, days=gates.ERA_DAYS[gates.ERA_DAYS < end])
    rows = []

    def trial(d1, d2, X, hedge, cat):
        r30, tr, hyp = simulate(P, ev_all[(X, cat)], d1, d2, hedge, 30e3, 2.0, end, MR=MR)
        s = scored(r30, end)
        gates.assert_dev_only(s)
        at = gates.alpha_test(s, inc70.reindex(s.index))
        scr = gates.dev_screen(s)
        nev = n_scored_events(tr, end)
        v = vname(d1, d2, X, hedge, cat)
        if log:
            gates.log_trial(IDEA, v, gates.dev_book(s), note=f"DEV sleeve $30K 2x; events={nev}; t70={at['t_alpha']:.3f}",
                            n_events=nev, t_alpha_70k=at["t_alpha"], sleeve_sharpe=scr["sleeve_sharpe"])
        row = dict(variant=v, d1=d1, d2=d2, X=X, hedge=hedge, cat=cat, events=nev,
                   skipped=int((~tr.taken).sum()) if len(tr) else 0, sleeve_sharpe=scr["sleeve_sharpe"],
                   t_alpha_70k=at["t_alpha"], t_alpha_100k=scr["t_alpha"], corr=scr["corr"],
                   active_days=scr["active_days"], hyp_share_days=float((hyp.reindex(s.index).fillna(0) != 0).sum() /
                                                                      max(1, (s != 0).sum())))
        rows.append(row)
        print(json.dumps(row), flush=True)
        return row

    for d1 in (7, 14):
        for d2 in (0, 3):
            for X in (0.01, 0.025):
                for hedge in (False, True):
                    trial(d1, d2, X, hedge, "all")
    core = pd.DataFrame(rows)
    elig = core[core.events >= 20]
    best = elig.sort_values("t_alpha_70k", ascending=False).iloc[0] if len(elig) else core.iloc[0]
    trial(int(best.d1), int(best.d2), float(best.X), bool(best.hedge), "ti")
    T = pd.DataFrame(rows)
    T.to_csv(os.path.join(OUT, "trials_dev.csv"), index=False)
    return T


def select(T):
    """Pre-registered: highest DEV alpha t (sleeve 2x on the incumbent at $70K) among variants with >= 20 events;
    ties go to the simpler variant (no hedge, d2 = 0, smaller d1, cat = all)."""
    e = T[T.events >= 20].copy()
    e["simple"] = e.hedge.astype(int) * 4 + (e.d2 > 0) * 2 + (e.d1 > 7) * 1 + (e["cat"] != "all") * 8
    e = e.sort_values(["t_alpha_70k", "simple"], ascending=[False, True])
    return e.iloc[0]


# ------------------------------------------------------------------ HOLD (after the freeze)
def run_hold():
    fz = json.load(open(os.path.join(OUT, "frozen.json")))
    p = fz["params"]
    end = FULL_END
    ev = load_events(p["X"], p["cat"], end)
    coins = sorted(set(ev.coin) | {"BTC"})
    P = price_tables(end, coins)
    MR = margin_rates()
    S, TR = {}, {}
    for cap in (30000, 50000):
        for mult in (2.0, 1.0):
            r, tr, hyp = simulate(P, ev, p["d1"], p["d2"], p["hedge"], cap, mult, end, MR=MR)
            S[f"s{cap // 1000}_{int(mult)}x"] = scored(r, end)
            TR[(cap, mult)] = (tr, scored(hyp, end))
    D = pd.DataFrame(S)
    D.index.name = "day"
    D.to_parquet(os.path.join(OUT, "daily.parquet"))
    g2 = gates.path_b({30000: D.s30_2x, 50000: D.s50_2x}, days=D.index)
    g1 = gates.path_b({30000: D.s30_1x, 50000: D.s50_1x}, days=D.index)
    tr30 = TR[(30000, 2.0)][0]
    tr30.to_csv(os.path.join(OUT, "trades.csv"), index=False)
    TR[(30000, 2.0)][1].rename("hyp_s30_2x").to_frame().to_parquet(os.path.join(OUT, "daily_hyp.parquet"))
    out = dict(frozen=fz["variant"], gates_2x=g2, info_1x={k: g1[k] for k in g1 if k not in ("a_grid",)})
    json.dump(out, open(os.path.join(OUT, "gates.json"), "w"), indent=1, default=float)
    print(json.dumps({k: g2[k] for k in g2 if k != "a_grid"}, default=float, indent=1))
    return D, g2, g1, tr30


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["dev", "hold"])
    ap.add_argument("--no-log", action="store_true")
    a = ap.parse_args()
    if a.mode == "dev":
        T = run_dev(log=not a.no_log)
        b = select(T)
        print("SELECTED", b.variant, f"t70={b.t_alpha_70k:.3f}", f"events={b.events}")
    else:
        run_hold()


if __name__ == "__main__":
    main()
