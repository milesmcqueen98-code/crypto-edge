#!/usr/bin/env python3
"""Live order timing study, part 2: symmetric valuation (reports/owner/timing_prereg.md, "Deviation 2" and
"Deviation 3"). Planned after the first reading was seen.

  moves   per era and policy against P0: the share of P0's parents that the policy fills in the same coin within one
          and two minutes; how many of the parents only in the policy and only in P0 pair up as such moves (one to
          one, nearest first); the entry difference of the paired moves; the ten largest ladders removed from P1.
  S1      every parent of every policy (P0 included) on its 4-sigma rung alone: the lab's exit rule on candles
          (take-profit at 0.6 x 4 sigma, else the close of minute q + 60), maker 6 bp in and on the take-profit, else
          taker + 2 x 2 bp half-spread + 2 x square-root impact on today's ADV; the size of evaluate.py (the
          research's 4-sigma fill, else the coin and quarter mean). This is evaluate.py's "rung alone", now for all.
  S2      the whole ladder for every parent of every policy (s2 subcommand; needs the deep prints, deviation 3).
Inputs: the parents of evaluate.py (reports/owner/timing/parents.csv.gz) and its scratch (studied minutes).
usage: python scripts/owner/timing/part2.py s1 <scratch_dir>
       python scripts/owner/timing/part2.py s2 <scratch_dir> <deep_all.parquet>
"""
import os
import sys
import time

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
OUT = os.path.join(ROOT, "reports", "owner", "timing")
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "scripts", "ladder_v6x"))
import evaluate as EV  # noqa: E402
import lsim  # noqa: E402
import fsim  # noqa: E402

POLS = ["P0", "P1", "P1a", "P1b", "P2", "P3"]
PAIRS = [(p, "P0") for p in POLS[1:]] + [("P2", "P1"), ("P3", "P1")]
H = 60


def research_rows(era):
    """Per research parent (ts, coin), poll1s blend at S*: whole ladder P&L, 4-sigma rung P&L, dollars bought
    (evaluate.research_book with the 4-sigma rung kept apart)."""
    cfg = "S_0.5"
    kw = lsim.CONFIGS[cfg]
    books = lsim.load_books(cfg, era)
    out = {}
    for b, (Q, info) in books.items():
        Q = Q.assign(rowpnl=row_pnl(Q, info, era, kw))
        g = Q.groupby(["ts", "coin"])
        out[b] = pd.DataFrame(dict(ladder=g.rowpnl.sum(), bought=g.fill.sum(),
                                   r4=Q[Q.k == 4.0].groupby(["ts", "coin"]).rowpnl.sum(),
                                   n_rungs=g.size()))
    s = fsim.lat_share(era, kw["theta"])
    m, x = out["minute"], out["instant"]
    R = m.copy()
    for col in ("ladder", "bought", "r4"):
        R[col] = m[col] + s * (x[col].reindex(m.index).fillna(0.0) - m[col])
    R["r4"] = R.r4.fillna(0.0)
    return R


def row_pnl(Q, info, era, kw):
    """lsim.rem_daily's per-row P&L: take-profit leg - entry cost + remainder at minute 60 priced from prints."""
    tk_fee = info["taker_bp"] / 1e4
    hs = fsim.HS_BP * kw["cost_mult"] / 1e4
    y = fsim.IMPACT_Y * kw["cost_mult"]
    tag, (lo, hi) = fsim.ERAS[era]
    sc = fsim.today_scale(lsim.RL.inputs(tag)["P"], lo, hi)
    rem = np.maximum((Q.fill - Q.tp_fill).to_numpy(), 0.0)
    adv = Q.adv.fillna(Q.adv.median()).to_numpy()
    vol_d = Q.vol_d.fillna(Q.vol_d.median()).to_numpy()
    fsc = Q.coin.map(sc).fillna(1.0).to_numpy()
    g60 = Q.g60.to_numpy() / 1e4
    pc = lsim.pcost()
    pnl = (Q.pnl_tp - Q.entry_cost).to_numpy().copy()
    for i in np.nonzero(rem > 0)[0]:
        R_ = rem[i]
        model = hs + y * vol_d[i] * np.sqrt(R_ / adv[i])
        fb = 1e4 * fsim.IMPACT_Y * vol_d[i] * np.sqrt(R_ / adv[i])
        ci = pc.cost(Q.coin.iat[i], pd.Timestamp(Q.fill_t.iat[i]), 0, R_ / fsc[i], fb_bp=fb)
        if not np.isfinite(ci):
            ci = model
        pnl[i] += R_ * (g60[i] - tk_fee - ci)
    return pnl


def load(scr):
    Pp = pd.read_csv(os.path.join(OUT, "parents.csv.gz"), parse_dates=["q"])
    S = pd.concat([pd.read_parquet(os.path.join(scr, f"studied_{t}.parquet")) for t in ("main", "early")],
                  ignore_index=True)
    J = Pp.merge(S, on=["coin", "q"], how="left", validate="m:1")
    assert J.L.notna().all()
    return J


def alone(J, era):
    """S1: the 4-sigma rung alone of each parent (evaluate.py's formula), and its exit day."""
    tag = EV.ERAS[era][0]
    cfg = "S_0.5"
    kw = lsim.CONFIGS[cfg]
    info = lsim.load_books(cfg, era)["minute"][1]
    maker, taker = info["maker_bp"] / 1e4, info["taker_bp"] / 1e4
    hs, imp_y = fsim.HS_BP * 2.0 / 1e4, fsim.IMPACT_Y * 2.0
    _, (lo, hi) = fsim.ERAS[era]
    sc = fsim.today_scale(lsim.RL.inputs(tag)["P"], lo, hi)
    st = J.src.eq("stale").to_numpy()
    lev = np.where(st, J.L_prev, J.L)
    tp_off = np.where(st, J.tp_off_prev, J.tp_off_cur)
    gtp = np.where(st, J.gtp_prev, J.gtp_cur)
    g60 = np.where(st, J.g60_prev, J.g60_cur) + 1e4 * np.log(lev / J.px.to_numpy())
    S_ = J["size"].to_numpy()
    advs = J.adv.to_numpy() * J.coin.map(sc).fillna(1.0).to_numpy()
    vd = np.where(np.isfinite(J.vol_d), J.vol_d, 0.05)
    with np.errstate(invalid="ignore", divide="ignore"):
        imp = np.where(advs > 0, imp_y * vd * np.sqrt(S_ / advs), 0.0)
    a = np.where(tp_off >= 0, S_ * (gtp / 1e4 - maker) - S_ * maker,
                 S_ * (g60 / 1e4 - taker - hs - imp) - S_ * maker)
    day = (J.q + pd.to_timedelta(np.where(tp_off >= 0, tp_off + 1, H), unit="m")).dt.floor("D")
    return a, day.to_numpy()


# ------------------------------------------------------------------------------------------------ moves
def match(a, b, w):
    """One-to-one pairs of minute indices a (only policy) and b (only P0) of one coin with |a - b| <= w, nearest
    first. Returns [(ia, ib)]."""
    cand = sorted((abs(x - y), i, j) for i, x in enumerate(a) for j, y in enumerate(b) if abs(x - y) <= w)
    ua, ub, out = set(), set(), []
    for _, i, j in cand:
        if i in ua or j in ub:
            continue
        ua.add(i)
        ub.add(j)
        out.append((i, j))
    return out


def moves(J):
    J = J.assign(mi=((J.q - pd.Timestamp("2020-01-01")) // pd.Timedelta(minutes=1)).astype(np.int64))
    rows, top = [], []
    for e in EV.ERAS:
        E = J[J.era == e]
        b0 = E[E.policy == "P0"]
        for p in POLS[1:]:
            X = E[E.policy == p]
            r = dict(era=e, policy=p, vs="P0", p0_parents=len(b0), parents=len(X))
            xs = {c: np.sort(g.mi.to_numpy()) for c, g in X.groupby("coin")}
            for w in (0, 1, 2):
                n = 0
                for c, g in b0.groupby("coin"):
                    a = xs.get(c, np.zeros(0, np.int64))
                    n += sum(bool(len(a)) and np.abs(a - m).min() <= w for m in g.mi)
                r[f"share_pm{w}"] = n / len(b0)
            kx = set(zip(X.coin, X.mi))
            k0 = set(zip(b0.coin, b0.mi))
            ox = X[[k not in k0 for k in zip(X.coin, X.mi)]]
            o0 = b0[[k not in kx for k in zip(b0.coin, b0.mi)]]
            r.update(only_policy=len(ox), only_p0=len(o0))
            for w in (1, 2):
                ent, wts, n = [], [], 0
                for c in set(ox.coin) | set(o0.coin):
                    ga, gb = ox[ox.coin == c], o0[o0.coin == c]
                    pr = match(ga.mi.tolist(), gb.mi.tolist(), w)
                    n += len(pr)
                    for i, j in pr:
                        ent.append(1e4 * (ga.px.iat[i] / gb.px.iat[j] - 1.0))
                        wts.append(max(gb["size"].iat[j], 1e-9))
                r[f"paired_pm{w}"] = n
                r[f"entry_bp_paired_pm{w}"] = float(np.average(ent, weights=wts)) if n else np.nan
                r[f"entry_bp_paired_pm{w}_median"] = float(np.median(ent)) if n else np.nan
            rows.append(r)
            if p == "P1":
                o0 = o0.assign(lad_=o0.ladder.to_numpy())
                for x in o0.reindex(o0.lad_.abs().sort_values(ascending=False).index).head(10).itertuples():
                    a = xs.get(x.coin, np.zeros(0, np.int64))
                    d = (a - x.mi)
                    near = d[np.abs(d) <= 2]
                    top.append(dict(era=e, coin=x.coin, q=x.q, ladder_usd=x.lad_, in_research=bool(x.in_res),
                                    p1_within_2min=bool(len(near)),
                                    p1_offset_min=int(near[np.argmin(np.abs(near))]) if len(near) else np.nan))
    return pd.DataFrame(rows), pd.DataFrame(top)


# ------------------------------------------------------------------------------------------------ tables
def table(V, col, d0s, Cs, label):
    """Per era and pooled: each policy's P&L under `col`, against P0 and P1, and the daily Sharpe change.
    V: {era: frame of parents with era, policy, coin, q, col, day}."""
    rows = []
    pooled = {}
    for e, E in V.items():
        d0, C = d0s[e], Cs[e]
        idx = d0.index
        tot = {p: float(E.loc[E.policy == p, col].sum()) for p in POLS}
        daily = {p: E[E.policy == p].groupby("day")[col].sum().reindex(idx, fill_value=0.0) for p in POLS}
        for p in POLS:
            pooled.setdefault(p, 0.0)
            pooled[p] += tot[p]
        for p, ref in PAIRS:
            dx = d0 + (daily[p] - daily["P0"]) / C
            dr = d0 + (daily[ref] - daily["P0"]) / C
            rows.append(dict(val=label, era=e, policy=p, vs=ref, pnl_policy=tot[p], pnl_ref=tot[ref],
                             dpnl_usd=tot[p] - tot[ref], dpnl_pct=100 * (tot[p] - tot[ref]) / tot[ref],
                             dsharpe=fsim.stats(dx, C, e)["sharpe"] - fsim.stats(dr, C, e)["sharpe"]))
    for p, ref in PAIRS:
        rows.append(dict(val=label, era="pooled", policy=p, vs=ref, pnl_policy=pooled[p], pnl_ref=pooled[ref],
                         dpnl_usd=pooled[p] - pooled[ref], dpnl_pct=100 * (pooled[p] - pooled[ref]) / pooled[ref],
                         dsharpe=np.nan))
    return pd.DataFrame(rows)


def rule(T):
    """The plan's reading: 5% of P&L or more, same sign, in at least two of the three eras."""
    out = []
    for (p, ref), g in T[T.era != "pooled"].groupby(["policy", "vs"], sort=False):
        if (p, ref) not in (("P1", "P0"), ("P2", "P1"), ("P3", "P1")):
            continue
        x = g.dpnl_pct.to_numpy()
        up, dn = int((x >= 5).sum()), int((x <= -5).sum())
        verdict = "better by 5%+ in two eras" if up >= 2 else ("worse by 5%+ in two eras" if dn >= 2 else
                                                                 "no material effect")
        out.append(dict(val=g.val.iat[0], policy=p, vs=ref, eras_up5=up, eras_down5=dn, reading=verdict))
    return pd.DataFrame(out)


def base(scr):
    lsim.ensure_frozen()
    J = load(scr)
    R, d0s, Cs = {}, {}, {}
    for e in EV.ERAS:
        R[e] = research_rows(e)
        d0s[e] = lsim.incumbent_daily("S_0.5", e)
        Cs[e] = lsim.CONFIGS["S_0.5"]["C"]
    return J, R, d0s, Cs


def run_s1(scr):
    t0 = time.time()
    J, R, d0s, Cs = base(scr)
    # removed-ladder value of each parent, as evaluate.py: research ladder, else the rung alone
    V, chk = {}, []
    for e in EV.ERAS:
        E = J[J.era == e].copy()
        E["s1"], E["day"] = alone(E, e)
        key = list(zip(E.q, E.coin))
        inr = np.array([k in R[e].index for k in key])
        E["ladder"] = np.where(inr, [R[e].ladder.get(k, np.nan) if i else np.nan for k, i in zip(key, inr)], E.s1)
        V[e] = E
        # check: P0's rung alone against the research's own 4-sigma result, shared parents
        b0 = E[(E.policy == "P0") & inr]
        rr = R[e].loc[list(zip(b0.q, b0.coin))]
        Rall = R[e][(R[e].index.get_level_values(0) >= EV.ERAS[e][1])
                    & (R[e].index.get_level_values(0) < pd.Timestamp(EV.ERAS[e][2]) + pd.Timedelta(days=1))]
        chk.append(dict(era=e, shared_with_research=len(b0), s1_p0_usd=float(b0.s1.sum()),
                        research_r4_usd=float(rr.r4.sum()), diff_usd=float(b0.s1.sum() - rr.r4.sum()),
                        diff_pct=100 * float(b0.s1.sum() / rr.r4.sum() - 1),
                        research_ladder_usd=float(rr.ladder.sum()),
                        r4_share_of_ladder_shared=float(rr.r4.sum() / rr.ladder.sum()),
                        r4_share_of_ladder_all=float(Rall.r4.sum() / Rall.ladder.sum()),
                        research_parents=len(Rall)))
        print(f"{e}: S1 ({time.time() - t0:.0f}s)", flush=True)
    M, top = moves(pd.concat(V.values(), ignore_index=True))
    T = table(V, "s1", d0s, Cs, "S1")
    M.to_csv(os.path.join(OUT, "moves.csv"), index=False, float_format="%.6g")
    top.to_csv(os.path.join(OUT, "removed_top_p1.csv"), index=False, float_format="%.6g")
    T.to_csv(os.path.join(OUT, "s1.csv"), index=False, float_format="%.6g")
    pd.DataFrame(chk).to_csv(os.path.join(OUT, "s1_check.csv"), index=False, float_format="%.6g")
    rule(T).to_csv(os.path.join(OUT, "s1_rule.csv"), index=False)
    pd.set_option("display.width", 250)
    print(M.round(3).to_string(index=False))
    print(top.to_string(index=False))
    print(T.round(3).to_string(index=False))
    print(pd.DataFrame(chk).round(3).to_string(index=False))
    print(rule(T).to_string(index=False))


if __name__ == "__main__":
    if sys.argv[1] == "s1":
        run_s1(sys.argv[2])
    elif sys.argv[1] == "s2":
        import part2_s2  # noqa: F401  (written once the deep prints exist)
        part2_s2.run(sys.argv[2], sys.argv[3])
