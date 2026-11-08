#!/usr/bin/env python3
"""Red team 2 (ladder v5): an independent re-test of C3 (passive time exit), with the model's and the prints' costs.

Rule (reports/ladder_v5/specs/exits.md; written from the spec, the builder's cand_exits.py was not read): at the
60-minute mark a rung's unsold remainder rests as a post-only sell at the previous minute's close + 1 tick, re-pegged
each minute, for N minutes (candles fill+61 .. fill+60+N); in minute j it fills up to theta x the USD volume traded
above the peg on a one-tick trade-through (x today's volume factor in S*), at the maker fee, no half-spread or impact;
the leftover is sold at market at the close of candle fill+60+N with the taker fee, half-spread and impact on the
leftover. C3 does not change who gets cash (hsim is frozen), so the incumbent's per-tranche results (qdump.py) are all
it needs: each tranche's pnl_rem is replaced, P&L booked on each sale's day, the two latency bounds blended as hsim.

Options (each a separate scoring, all against the frozen cache's incumbent unless the exit cost is replaced, in which
case the incumbent is re-scored with the same cost so both sides pay the same market-exit cost model):
  paths    "frozen": reports/ladder_v5/exit_paths_<tag>.pkl by the frozen dataset's index (the spec's instruction)
           "live":   my own paths from the candles at the tranche's live fill time (hsim can fill a deeper rung later
                     than the research data; the frozen paths are computed at the research fill time)
  tick     "model": wick_sim.spot_tick (what exit_paths used: the coarser of spot and perp tick); "real": the spot tick
  share    False: every tranche gets theta x the minute's volume on its own; True: tranches of one coin resting in the
           same minute share it
  cap      "candle": the frozen model's capacity; "print": theta x USD printed at or above peg + tick (prints_exit.py)
  cost     "model": half-spread 2 bp x cost_mult + 0.7 x cost_mult x daily vol x sqrt(size / ADV);
           "print": the print-measured half-spread + first-X slippage at that minute (x `pmult`), with the depth
           scaled by today's volume factor in S* (size / factor)
"""
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import gates  # noqa: E402
import fsim  # noqa: E402

RT = os.path.join(fsim.OUT, "redteam2")
QD = os.path.join(RT, "q")
NMAX = 15
_CANDLES, _SCALE, _P = {}, {}, {}


def ticks():
    sys.path.insert(0, os.path.join(fsim.ROOT, "scripts"))
    import wick_sim as ws
    t = pd.read_csv(os.path.join(fsim.ROOT, "reports", "wick1m", "spot_ticks_wide.csv"))
    real = {r.coin: float(r.tick) for r in t.itertuples() if np.isfinite(r.tick)}
    real["PEPE"] = 1e-8
    model = {}
    for c in real:
        try:
            model[c] = float(ws.spot_tick(c))
        except KeyError:
            model[c] = np.nan
    return model, real


TICK_MODEL, TICK_REAL = ticks()


def candles(tag, coin):
    if (tag, coin) not in _CANDLES:
        src = "minute" if tag == "main" else "minute_early"
        m = pd.read_parquet(os.path.join(fsim.ROOT, "data", src, f"{coin}.parquet")).drop_duplicates("ts")
        m = m.set_index("ts").sort_index()
        m = m[m.volume > 0]
        full = pd.date_range(m.index.min(), m.index.max(), freq="min")
        _CANDLES[(tag, coin)] = (full[0], m.close.reindex(full).ffill().to_numpy(np.float32),
                                 m.high.reindex(full).to_numpy(np.float32), m.low.reindex(full).to_numpy(np.float32),
                                 m.volume.reindex(full).fillna(0.0).to_numpy(np.float32))
    return _CANDLES[(tag, coin)]


def data(tag):
    if tag not in _P:
        _P[tag] = fsim.load(tag)
    return _P[tag]


def today_scale(era):
    if era not in _SCALE:
        tag, (lo, hi) = fsim.ERAS[era]
        _SCALE[era] = fsim.today_scale(data(tag), lo, hi)
    return _SCALE[era]


def live_paths(Q, tag, tick):
    """Per row of Q: close[a + 0..N], high/low/vol[a + 1..N] at a = fill_t + 60 (the live fill time)."""
    n = len(Q)
    cl = np.full((n, NMAX + 1), np.nan)
    hi = np.full((n, NMAX + 1), np.nan)
    lo = np.full((n, NMAX + 1), np.nan)
    vo = np.zeros((n, NMAX + 1))
    tk = np.zeros(n)
    for coin, ix in Q.groupby("coin").indices.items():
        t0, c_, h_, l_, v_ = candles(tag, coin)
        a = ((Q.fill_t.iloc[ix] - t0) // pd.Timedelta(minutes=1)).to_numpy() + 60
        ok = (a >= 0) & (a + NMAX < len(c_))
        rows, aa = ix[ok], a[ok]
        grid = aa[:, None] + np.arange(NMAX + 1)[None, :]
        cl[rows], hi[rows], lo[rows], vo[rows] = (c_[grid].astype(np.float64), h_[grid].astype(np.float64),
                                                  l_[grid].astype(np.float64), v_[grid].astype(np.float64))
        tk[ix] = (TICK_MODEL if tick == "model" else TICK_REAL).get(coin, np.nan)
    return cl, hi, lo, vo, tk


def candle_cap(cl, hi, lo, vo, tk, lvl):
    """The frozen model's passive quantities from candles: peg gain (log vs the entry level) and USD capacity."""
    peg = cl[:, :-1] + np.nan_to_num(tk)[:, None]                     # peg for minute j = close of j-1 + tick
    h, l_, v = hi[:, 1:], lo[:, 1:], vo[:, 1:]
    rng = h - l_
    frac = np.where(rng <= 0, 1.0, np.minimum(1.0, (h - peg) / np.where(rng <= 0, 1.0, rng)))
    hit = np.isfinite(h) & (h >= peg + np.nan_to_num(tk)[:, None] * (1 - 1e-9))
    cap = np.where(hit, v * frac * 0.5 * (peg + h), 0.0)
    g = np.log(peg / lvl[:, None])
    return g, cap


def frozen_paths(Q, tag):
    """exit_paths_<tag>.pkl rows by the frozen dataset's index ((ts, coin, k) -> index)."""
    P = data(tag)
    E = pd.read_pickle(os.path.join(fsim.OUT, f"exit_paths_{tag}.pkl"))
    key = pd.Series(P.index, index=pd.MultiIndex.from_frame(P[["ts", "coin", "k"]]))
    pix = key.reindex(pd.MultiIndex.from_frame(Q[["ts", "coin", "k"]])).to_numpy()
    n = len(Q)
    close_g = np.full((n, NMAX + 1), np.nan)
    pas_g = np.full((n, NMAX), np.nan)
    pas_cap = np.zeros((n, NMAX))
    for r, p in enumerate(pix):
        if p is None or (isinstance(p, float) and np.isnan(p)) or p not in E.index:
            continue
        e = E.loc[p]
        close_g[r] = e.close_g
        pas_g[r] = e.pas_g[1:]
        pas_cap[r] = e.pas_cap[1:]
    return close_g, pas_g, pas_cap


class PrintCost:
    """Market-sell cost (fraction) of X USD at minute m (0 / 5 / 15) of an event, from prints_rt2_exit.csv: the
    half-spread plus the first-X slippage (event median when >= 3 orders of at least X, else the coin-era pooled
    median, else linear extrapolation from the largest size with data)."""

    def __init__(self, min_n=3):
        X = pd.read_csv(os.path.join(fsim.OUT, "prints_rt2_exit.csv"), parse_dates=["fill_t"])
        C = pd.read_csv(os.path.join(fsim.OUT, "prints_rt2_coin.csv"))
        self.xs = np.array(sorted(int(c.split("_")[1]) for c in X.columns if c.startswith("slip_")), float)
        self.pool = {}
        for (coin, era), g in C.groupby(["coin", "era_tag"]):
            g = g.set_index("X").reindex(self.xs.astype(int))
            self.pool[(coin, era)] = np.where(g.n.to_numpy() >= 20, g.med.to_numpy(), np.nan)
        hs_pool = X.groupby(["coin", "era_tag"]).hs_bp.median().to_dict()
        self.tab = {}
        for r in X.itertuples():
            sl = np.array([getattr(r, f"slip_{int(x)}") for x in self.xs], float)
            nn = np.array([getattr(r, f"n_{int(x)}") for x in self.xs], float)
            pl = self.pool.get((r.coin, r.era_tag), np.full(len(self.xs), np.nan))
            s = np.where(nn >= min_n, sl, pl)
            hs = r.hs_bp if np.isfinite(r.hs_bp) and r.hs_n >= 5 else hs_pool.get((r.coin, r.era_tag), np.nan)
            self.tab[(r.coin, pd.Timestamp(r.fill_t), r.m)] = (hs, s)

    n_calls = 0
    n_extrap = 0
    usd_extrap = 0.0
    usd_calls = 0.0

    def cost(self, coin, fill_t, m, x, fb_bp=0.0):
        """Fraction of x lost vs the mid (half-spread + slippage); NaN when the event has no prints. Beyond the
        largest size with data: the larger of a linear extrapolation in size and fb_bp (the caller passes the
        frozen model's 1x impact), so unobserved sizes are never cheaper than the model says."""
        v = self.tab.get((coin, pd.Timestamp(fill_t), m))
        if v is None or not np.isfinite(v[0]):
            return np.nan
        hs, s = v
        ok = np.isfinite(s)
        if not ok.any():
            return np.nan
        xs, ss = self.xs[ok], np.maximum.accumulate(np.maximum(s[ok], 0.0))
        self.n_calls += 1
        self.usd_calls += x
        if x <= xs[0]:
            sl = ss[0] * x / xs[0]
        elif x <= xs[-1]:
            sl = np.interp(x, xs, ss)
        else:
            sl = max(ss[-1] * x / xs[-1], fb_bp)
            self.n_extrap += 1
            self.usd_extrap += x
        return (hs + sl) / 1e4


def load_q(cfg, era, bound):
    Q = pd.read_parquet(os.path.join(QD, f"inc_{cfg}_{era}_{bound}.parquet"))
    return Q.reset_index(drop=True)


def summary_row(cfg, era, bound):
    S = pd.read_csv(os.path.join(QD, "summary.csv"))
    return S[(S.cfg == cfg) & (S.era == era) & (S.bound == bound)].iloc[0]


def tranche_pnl(Q, cfg, era, bound, N, paths="live", tick="model", share=False, cap="candle", cost="model",
                pmult=1.0, pc=None, pcap=None, detail=None):
    """Per tranche: list of (day, pnl) of its remainder under C3 with N passive minutes (N = 0: the market exit at
    60 minutes), and the incumbent's market-exit P&L under the same cost model."""
    kw = gates.CONFIGS[cfg]
    tag = fsim.ERAS[era][0]
    sr = summary_row(cfg, era, bound)
    mk, tk_fee = sr.maker_bp / 1e4, sr.taker_bp / 1e4
    hs = fsim.HS_BP * kw["cost_mult"] / 1e4
    y = fsim.IMPACT_Y * kw["cost_mult"]
    theta = kw["theta"]
    sc = today_scale(era) if kw["today"] else {}
    rem = np.maximum((Q.fill - Q.tp_fill).to_numpy(), 0.0)
    lvl = Q.lvl.to_numpy()
    adv = Q.adv.fillna(Q.adv.median()).to_numpy()
    vol_d = Q.vol_d.fillna(Q.vol_d.median()).to_numpy()
    fsc = Q.coin.map(sc).fillna(1.0).to_numpy() if sc else np.ones(len(Q))
    if paths == "live":
        cl, hi, lo, vo, tkk = live_paths(Q, tag, tick)
        pg, pcp = candle_cap(cl, hi, lo, vo, tkk, lvl)
        close_g = np.log(cl / lvl[:, None])
    else:
        close_g, pg, pcp = frozen_paths(Q, tag)
    if cap == "print":
        pg, pcp = pcap(Q, era, tick)             # peg gains and USD at/above peg + tick from prints, (n, 15)
    g60 = Q.g60.to_numpy() / 1e4

    def exit_cost(i, x, m):
        if x <= 0:
            return 0.0
        if cost == "model":
            return hs + y * vol_d[i] * np.sqrt(x / adv[i])
        fb = 1e4 * fsim.IMPACT_Y * vol_d[i] * np.sqrt(x / adv[i])
        c = pc.cost(Q.coin.iat[i], Q.fill_t.iat[i], m, x / fsc[i], fb_bp=fb)
        return pmult * c

    used = {}
    order = np.argsort(Q.fill_t.to_numpy(), kind="stable")
    out_c, out_i = [], []
    ex_day = (Q.fill_t + pd.Timedelta(minutes=60)).dt.floor("D").to_numpy()
    for i in order:
        R = rem[i]
        if R <= 0:
            continue
        ci = exit_cost(i, R, 0)
        if not np.isfinite(ci):
            ci = hs + y * vol_d[i] * np.sqrt(R / adv[i])        # no prints: fall back to the model
        out_i.append((ex_day[i], R * (g60[i] - tk_fee - ci)))
        if N == 0:
            out_c.append((ex_day[i], R * (g60[i] - tk_fee - ci)))
            continue
        left, parts = R, []
        for j in range(1, N + 1):
            if left <= 0:
                break
            c_ = pcp[i, j - 1]
            if not np.isfinite(c_) or c_ <= 0 or not np.isfinite(pg[i, j - 1]):
                continue
            capj = theta * c_ * fsc[i]
            if share:
                k = (Q.coin.iat[i], Q.fill_t.iat[i] + pd.Timedelta(minutes=60 + j))
                capj = max(0.0, capj - used.get(k, 0.0))
            f = min(left, capj)
            if f <= 0:
                continue
            if share:
                used[k] = used.get(k, 0.0) + f
            day = (Q.fill_t.iat[i] + pd.Timedelta(minutes=60 + j)).floor("D")
            parts.append((day, f * (pg[i, j - 1] - mk)))
            left -= f
        if left > 0:
            gN = close_g[i, N]
            if not np.isfinite(gN):
                gN = g60[i]
            cN = exit_cost(i, left, N)
            if not np.isfinite(cN):
                cN = hs + y * vol_d[i] * np.sqrt(left / adv[i])
            day = (Q.fill_t.iat[i] + pd.Timedelta(minutes=60 + N)).floor("D")
            parts.append((day, left * (gN - tk_fee - cN)))
        out_c += parts
        if detail is not None:
            detail.append(dict(cfg=cfg, era=era, bound=bound, N=N, coin=Q.coin.iat[i], k=Q.k.iat[i],
                               fill_t=Q.fill_t.iat[i], rem=R, passive=R - left, left=left,
                               pnl_inc=R * (g60[i] - tk_fee - ci), pnl_c3=sum(p for _, p in parts),
                               cost_inc=ci, g60=g60[i], gN=close_g[i, N]))
    return out_c, out_i


def daily(Q, parts, era, C):
    lo, hi = fsim.ERAS[era][1]
    idx = pd.date_range(lo, hi, freq="D")
    tp_day = Q.tp_t.dt.floor("D").to_numpy()
    s = pd.Series((Q.pnl_tp - Q.entry_cost).to_numpy(), index=tp_day)
    r = pd.Series([p for _, p in parts], index=pd.DatetimeIndex([d for d, _ in parts])) if parts else \
        pd.Series(dtype=float)
    return pd.concat([s, r]).groupby(level=0).sum().reindex(idx, fill_value=0.0) / C


def book(cfg, era, N, **opt):
    """(candidate daily, incumbent daily under the same cost model), latency-blended as hsim.book."""
    kw = gates.CONFIGS[cfg]
    dc, di = {}, {}
    for bound in ("minute", "instant"):
        Q = load_q(cfg, era, bound)
        pc_, pi_ = tranche_pnl(Q, cfg, era, bound, N, **opt)
        dc[bound], di[bound] = daily(Q, pc_, era, kw["C"]), daily(Q, pi_, era, kw["C"])
    s = fsim.lat_share(era, kw["theta"])
    return (dc["minute"] + s * (dc["instant"] - dc["minute"]), di["minute"] + s * (di["instant"] - di["minute"]))


def score(name, N, configs=("S_0.5", "S_0.25", "base_0.5", "cap_1M"), inc_from="cache", inc_qd=None, **opt):
    """gates.run's statistics for C3 with N passive minutes; inc_from 'cache' (the frozen incumbent) or 'same'
    (the incumbent re-scored with the same exit cost model as the candidate, from the tables in inc_qd if given,
    else from the candidate's own tables)."""
    out = {"name": name, "path": "return", "configs": {}, "opt": {k: str(v) for k, v in opt.items()
                                                                  if k not in ("pc", "pcap", "detail")}}
    for cfg in configs:
        kw = gates.CONFIGS[cfg]
        per, diffs = {}, []
        for era in fsim.ERAS:
            cand, inc_same = book(cfg, era, N, **opt)
            if inc_from == "same" and inc_qd is not None:
                qd0 = globals()["QD"]
                globals()["QD"] = inc_qd
                inc_same, _ = book(cfg, era, 0, **opt)
                globals()["QD"] = qd0
            inc = gates.incumbent_cached(era, cfg) if inc_from == "cache" else inc_same
            cand = cand.reindex(inc.index, fill_value=0.0)
            d = cand - inc
            si, sc = fsim.stats(inc, kw["C"], era), fsim.stats(cand, kw["C"], era)
            per[era] = dict(inc_ret=si["ret_yr"], inc_sharpe=si["sharpe"], cand_ret=sc["ret_yr"],
                            cand_sharpe=sc["sharpe"], d_ret=sc["ret_yr"] - si["ret_yr"],
                            d_sharpe=sc["sharpe"] - si["sharpe"], mean_diff=float(d.mean()), t=float(fsim.nw_t(d)))
            diffs.append((era, inc, cand))
        ai = pd.concat([x[1] for x in diffs])
        ac = pd.concat([x[2] for x in diffs])
        d = ac - ai
        vm = ac * (ai.std() / ac.std()) - ai
        out["configs"][cfg] = dict(eras=per, pooled_t=float(fsim.nw_t(d)), pooled_mean=float(d.mean()),
                                   pooled_t_volmatched=float(fsim.nw_t(vm)), pooled_mean_volmatched=float(vm.mean()),
                                   era_means_volmatched={e: float((c * (ai.std() / ac.std()) - i).mean())
                                                         for e, i, c in diffs})
    out["gates"] = gates.gates(out, "return")
    return out


def offswitch():
    """N = 0 must reproduce the frozen incumbent exactly (model costs)."""
    worst = 0.0
    for cfg in gates.CONFIGS:
        for era in fsim.ERAS:
            cand, inc_same = book(cfg, era, 0, paths="live")
            inc = gates.incumbent_cached(era, cfg)
            worst = max(worst, float(np.abs(cand.reindex(inc.index, fill_value=0.0) - inc).max()),
                        float(np.abs(inc_same.reindex(inc.index, fill_value=0.0) - inc).max()))
    return worst


if __name__ == "__main__":
    print("off-switch (N = 0) max daily difference vs the frozen incumbent:", offswitch())
    res = {}
    for name, N in (("C3a_passive_5", 5), ("C3b_passive_15", 15)):
        for paths in ("frozen", "live"):
            r = score(f"{name}_{paths}", N, paths=paths)
            res[r["name"]] = r
            print(gates.summary(r))
    json.dump(res, open(os.path.join(RT, "c3_model.json"), "w"), indent=1, default=float)
