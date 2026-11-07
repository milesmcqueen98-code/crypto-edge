#!/usr/bin/env python3
"""Ladder v5, C4 and C5 (reports/ladder_v5/specs/cash_venue.md; rules in reports/ladder_v5_prereg.md).

C4_usdc (path "return"): the bot's cash is held as USDC on the -USDC products, which are aliases of the -USD books (one
order book), so fills and trading P&L are the live incumbent's. Daily return added to the incumbent's (scenario A):
    (r_usdc(t) + m(t)) x (1 - positions_t / C)
  r_usdc(t) = max(0, T-bill(t) - 0.5%) / 365 with edge.book.rf_daily's T-bill; halved when cost_mult == 2 (S*, cap),
              full in base; earned on all USDC, including USDC on hold for resting bids;
  m(t)      = Bitstamp usdcusd daily close(t) / close(t-1) - 1 (data/ladder_v5/usdc_usd_bitstamp.csv daily candles, then
              data/ladder_v5/usdc_usd_bitstamp_ext.csv fetched by fetch_usdc_ext.py; a day with no candle counts 1.0);
  positions_t = the day's time-average of the live book's open positions at cost (each fill from its fill minute to its
              take-profit, or to its 60-minute exit), from hsim.book's instant-bound Q.
C5_perp_venue (path "return"): the same bids also rest on the coin's Coinbase US perp.
  - in_perp, tp_perp = the raw perp capacity (fsim.load keeps in_perp_raw, tp_perp_raw); fsim.evaluate splits each
    order across spot and perp by capacity (the research simulator's rule);
  - perp fee and half-spread (sim.perp_cost) x2 when cost_mult == 2, patched in this process only;
  - live cash rule: the signal's holds are unchanged (the perp bids hold the signal's cash, no margin credit), and the
    open positions that hsim counts against equity include the perp fills. That is hsim.run with four lines changed,
    applied to its frozen source below (EDITS); a tranche with no perp capacity takes hsim.run's own lines.
The frozen dataset: fsim.load reads reports/wick1m/pre_hunt_<tag>.pkl (gitignored); it is copied from
reports/ladder_v5/frozen/ and sha256-checked before anything runs.
usage: python scripts/ladder_v5/cand_cashvenue.py                    the two trials, C4_usdc then C5_perp_venue
       python scripts/ladder_v5/cand_cashvenue.py check [era cfg]    off switches (rate 0 and no USDC mark; no perp)
"""
import hashlib
import inspect
import json
import os
import shutil
import sys
import time
import traceback

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)


def _frozen_dataset():
    sums = dict(reversed(line.split()) for line in open(os.path.join(ROOT, "reports", "ladder_v5", "frozen",
                                                                       "SHA256SUMS")) if line.strip())
    for tag in ("main", "early"):
        src = os.path.join(ROOT, "reports", "ladder_v5", "frozen", f"pre_hunt_{tag}.pkl")
        dst = os.path.join(ROOT, "reports", "wick1m", f"pre_hunt_{tag}.pkl")
        if not os.path.exists(dst):
            shutil.copyfile(src, dst)
        got = hashlib.sha256(open(dst, "rb").read()).hexdigest()
        if got != sums[f"frozen/pre_hunt_{tag}.pkl"]:
            raise SystemExit(f"{dst} is not the frozen dataset (sha256 {got})")


_frozen_dataset()
import gates  # noqa: E402  (first: fsim puts scripts/hunt, which has its own gates.py, ahead on sys.path)
import fsim  # noqa: E402
import hsim  # noqa: E402

assert os.path.dirname(os.path.abspath(gates.__file__)) == HERE, gates.__file__

sim = fsim.sim
OUTD = os.path.join(fsim.OUT, "cashvenue")
USDC_CSV = [os.path.join(ROOT, "data", "ladder_v5", "usdc_usd_bitstamp.csv"),
            os.path.join(ROOT, "data", "ladder_v5", "usdc_usd_bitstamp_ext.csv")]
SPREAD = 0.005              # USDC reward = T-bill - 0.5%
UNVERIFIED = 2.0            # cost_mult of the S* and cap configurations
_PERP_COST0 = sim.perp_cost
REC = {"c4": [], "c5": [], "rungs": [], "hsim": [], "slim": []}


# ---------------------------------------------------------------------------------------------------- C4: USDC cash
_U = {}


def usdc_close():
    """Bitstamp usdcusd daily close by UTC day: the frozen CSV's daily candles, then the fetched extension (the frozen
    file wins where both have a day; differences are recorded)."""
    if "s" not in _U:
        ser, info = [], {}
        for p in USDC_CSV:
            if not os.path.exists(p):
                info[os.path.basename(p)] = "missing"
                continue
            d = pd.read_csv(p)
            d = d[d.step == 86400]
            s = pd.Series(d.close.to_numpy(float), index=pd.DatetimeIndex(pd.to_datetime(d.ts.to_numpy(), unit="s")))
            s = s[~s.index.duplicated()].sort_index()
            info[os.path.basename(p)] = dict(days=len(s), first=str(s.index.min().date()), last=str(s.index.max().date()))
            ser.append(s)
        s = ser[0]
        for x in ser[1:]:
            both = s.index.intersection(x.index)
            info["overlap_days"] = len(both)
            info["overlap_max_abs_diff"] = float((s[both] - x[both]).abs().max()) if len(both) else None
            s = s.combine_first(x)
        _U["s"], _U["info"] = s, info
    return _U["s"]


def usdc_mtm(days):
    s = usdc_close()
    full = pd.date_range(days[0] - pd.Timedelta(days=1), days[-1], freq="D")
    u = s.reindex(full).fillna(1.0)
    return (u / u.shift(1) - 1.0).iloc[1:].reindex(days).to_numpy(float)


def usdc_reward(days):
    """max(0, T-bill - 0.5%) / 365 per day (scenario A's rate before the S* halving)."""
    return np.maximum(0.0, sim.book.rf_daily(days).to_numpy(float) - SPREAD / 365.0)


def _segments(Q):
    q = Q[Q.fill > 0]
    a = np.concatenate([q.tp_fill.to_numpy(float), (q.fill - q.tp_fill).to_numpy(float)])
    s = np.concatenate([q.fill_t.to_numpy("datetime64[ns]")] * 2)
    e = np.concatenate([q.tp_t.to_numpy("datetime64[ns]"), q.ex_t.to_numpy("datetime64[ns]")])
    k = a > 0
    return a[k], s[k], e[k]


def day_positions(Q, days):
    """The day's time-average of open positions at cost ($): each fill's take-profit part from fill to take-profit, the
    rest from fill to the 60-minute exit (fsim's release rule; segments are <= 60 minutes, so at most two days)."""
    a, s, e = _segments(Q)
    if not len(a):
        return pd.Series(0.0, index=days)
    d0 = s.astype("datetime64[D]").astype("datetime64[ns]")
    d1 = d0 + np.timedelta64(1, "D")
    m0 = (np.minimum(e, d1) - s) / np.timedelta64(1, "m")
    m1 = np.maximum((e - d1) / np.timedelta64(1, "m"), 0.0)
    v = pd.concat([pd.Series(a * m0, index=d0), pd.Series(a * m1, index=d1)]).groupby(level=0).sum() / 1440.0
    return v.reindex(days, fill_value=0.0)


def cfg_of(theta, C, today, cost_mult):
    for k, v in gates.CONFIGS.items():
        if v == dict(theta=theta, C=C, today=today, cost_mult=cost_mult):
            return k
    return f"theta{theta}_C{C:.0f}_today{today}_cost{cost_mult}"


def c4_book(P, era, pan=None, adv_=None, theta=0.5, C=250e3, today=False, cost_mult=1.0, rate=True, mark=True,
            record=True):
    d, out = hsim.book(P, era, theta=theta, C=C, today=today, cost_mult=cost_mult, pan=pan, adv=adv_)
    pos = day_positions(out["instant"][0], d.index).to_numpy(float)
    free = 1.0 - pos / C
    r = usdc_reward(d.index) * (0.5 if cost_mult == UNVERIFIED else 1.0) if rate else np.zeros(len(d))
    m = usdc_mtm(d.index) if mark else np.zeros(len(d))
    cand = d + (r * free + m * free)
    if record:
        try:
            cfg = cfg_of(theta, C, today, cost_mult)
            REC["c4"].append(pd.DataFrame(dict(cfg=cfg, era=era, date=d.index, c4_trading=d.to_numpy(),
                                               c4_reward=r * free, c4_mtm=m * free, c4_pos_avg=pos, c4=cand.to_numpy())))
            for b in ("minute", "instant"):
                Q, _, info, st = out[b]
                _record_rows("inc", cfg, era, b, Q, np.zeros(len(Q)), np.zeros(len(Q), bool), info, st)
        except Exception:
            traceback.print_exc()
    return cand


# ---------------------------------------------------------------------------------------------------- C5: perp venue
def _perp_cap(x):
    x = float(x)
    return x if np.isfinite(x) and x > 0 else 0.0


def _tp_split(f, theta, in_s, tp_s, in_p, tp_p):
    """Take-profit part of a fill split across spot and perp by entry capacity (fsim.evaluate's split), each venue's
    take-profit capped by its own capacity."""
    cs, cp = theta * float(in_s), theta * in_p
    tot = cs + cp
    if tot <= 0:
        return 0.0
    return min(f * cs / tot, theta * float(tp_s)) + min(f * cp / tot, theta * tp_p)


EDITS = [   # (frozen hsim.run line(s), C5 line(s)); each must occur exactly once
    ("def run(", "def run_perp("),
    ("    def add_position(i, f, r):\n",
     "    def add_position(i, f, r, ip=0.0, tpp=0.0):\n"),
    ("            tp = min(f, theta * r.tp_spot)\n",
     "            tp = min(f, theta * r.tp_spot) if ip <= 0 else _tp_split(f, theta, r.in_spot, r.tp_spot, ip, tpp)\n"),
    ("            f = min(o, theta * r.in_spot)\n"
     "            key = (r.ts, c)\n"
     "            add_position(i, f, r)\n",
     "            ip_, tpp_ = _perp_cap(r.in_perp), _perp_cap(r.tp_perp)\n"
     "            f = min(o, theta * r.in_spot) if ip_ <= 0 else min(o, theta * (r.in_spot + ip_))\n"
     "            key = (r.ts, c)\n"
     "            add_position(i, f, r, ip_, tpp_)\n"),
    ('                f = min(order[d["row"]], theta * rr.in_spot)\n'
     '                add_position(i, f, rr)\n',
     '                ip_, tpp_ = _perp_cap(W.at[d["row"], "in_perp"]), _perp_cap(W.at[d["row"], "tp_perp"])\n'
     '                f = (min(order[d["row"]], theta * rr.in_spot) if ip_ <= 0\n'
     '                     else min(order[d["row"]], theta * (rr.in_spot + ip_)))\n'
     '                add_position(i, f, rr, ip_, tpp_)\n'),
]


def _make_run_perp():
    src = inspect.getsource(hsim.run)
    for old, new in EDITS:
        if src.count(old) != 1:
            raise SystemExit(f"hsim.run edit does not apply exactly once: {old!r}")
        src = src.replace(old, new)
    ns = dict(vars(hsim))
    ns.update(_perp_cap=_perp_cap, _tp_split=_tp_split)
    exec(compile(src, "<hsim.run with C5 edits>", "exec"), ns)
    return ns["run_perp"]


run_perp = _make_run_perp()


class perp_cost_as:
    """Within the block, sim.perp_cost (which fsim.evaluate calls) is fn; restored afterwards."""

    def __init__(self, fn):
        self.fn = fn

    def __enter__(self):
        sim.perp_cost = self.fn

    def __exit__(self, *exc):
        sim.perp_cost = _PERP_COST0
        return False


def perp_cost_x(mult):
    def f():
        fee, hs = _PERP_COST0()
        return {c: v * mult for c, v in fee.items()}, {c: v * mult for c, v in hs.items()}
    return f


def _perp_cost_probe():
    """Diagnostics only: a 100% perp fee, so that entry_cost reveals each row's perp fill (fills do not depend on
    costs)."""
    fee, hs = _PERP_COST0()
    return {c: 1e4 for c in fee}, {c: 0.0 for c in hs}


def book_perp(P, era, theta=0.5, C=250e3, today=False, cost_mult=1.0, adv=None, pan=None, perp=True, split=False):
    """hsim.book with the perp venue restored (C5): same steps, run_perp in place of hsim.run, perp costs scaled."""
    if perp:
        P = P.copy()
        P["in_perp"], P["tp_perp"] = P["in_perp_raw"], P["tp_perp_raw"]
    tag, (lo, hi) = fsim.ERAS[era]
    W = fsim.window(P, lo, hi)
    if adv is None:
        adv = hsim.adv_table(tag, sorted(W.coin.unique()), lo, hi)
    sc = None
    if today:
        sc = fsim.today_scale(P, lo, hi)
        W = fsim.apply_scale(W, sc)
        adv = adv.copy()
        for c in adv.columns:
            adv[c] = adv[c] * sc.get(c, 1.0)
    days = (pd.Timestamp(hi) - pd.Timestamp(lo)).days + 1
    kw = dict(hs_bp=fsim.HS_BP * cost_mult, impact_y=fsim.IMPACT_Y * cost_mult)
    idx_d = pd.date_range(lo, hi, freq="D")
    out = {}
    for name, drop in (("minute", True), ("instant", False)):
        o, st, foff = run_perp(W, era, C=C, theta=theta, drop_same_minute=drop, adv=adv, pan=pan, scale=sc)
        Wm = hsim.with_live_fills(W, foff, tag, sc)
        want = np.minimum(0.25 * C, 0.002 * Wm.adv.fillna(0.0)) * Wm.k.map({4.0: 1 / 3, 6.0: 1 / 3, 8.0: 1 / 3})
        Wm["mult"] = np.where(want > 0, o.reindex(Wm.index).fillna(0.0) / want, 0.0)
        with perp_cost_as(perp_cost_x(UNVERIFIED if cost_mult == UNVERIFIED else 1.0)):
            Q, d, info = fsim.evaluate(Wm, theta=theta, C=C, days=days, drop_same_minute=drop, **kw)
        extra = {}
        if split:
            try:
                extra = _venue_split(W, Wm, Q, foff, theta, C, days, drop, kw)
            except Exception:
                traceback.print_exc()
        out[name] = (Q, d.reindex(idx_d, fill_value=0.0) / C, info, st, extra)
    s = fsim.lat_share(era, theta)
    d1 = out["minute"][1] + s * (out["instant"][1] - out["minute"][1])
    return d1, out


def _venue_split(W, Wm, Q, foff, theta, C, days, drop, kw):
    with perp_cost_as(_perp_cost_probe):
        Qx, _, ix = fsim.evaluate(Wm, theta=theta, C=C, days=days, drop_same_minute=drop, **kw)
    if not np.array_equal(Qx.fill.to_numpy(), Q.fill.to_numpy()):
        raise RuntimeError("fills changed with the perp cost probe")
    mk = ix["maker_bp"] / 1e4
    fill = Q.fill.to_numpy(float)
    fp = np.clip((Qx.entry_cost.to_numpy(float) - fill * mk) / (1.0 + 1e-4 - mk), 0.0, fill)
    # deeper rungs the live book filled at a later trade-through than the research's first one: their perp capacity
    # is still the research's (hsim.with_live_fills refreshes only the spot columns)
    late = {(W.at[r, "ts"], W.at[r, "coin"], W.at[r, "k"]) for r, off in foff.items()
            if not (np.isfinite(W.at[r, "f_off"]) and int(off) == int(W.at[r, "f_off"]))}
    lm = np.array([(t, c, k) in late for t, c, k in zip(Q.ts, Q.coin, Q.k)], bool)
    return dict(fill_perp=fp, late=lm)


def c5_book(P, era, pan=None, adv_=None, theta=0.5, C=250e3, today=False, cost_mult=1.0, perp=True, record=True):
    d, out = book_perp(P, era, theta=theta, C=C, today=today, cost_mult=cost_mult, adv=adv_, pan=pan, perp=perp,
                       split=record)
    if record:
        try:
            cfg = cfg_of(theta, C, today, cost_mult)
            REC["c5"].append(pd.DataFrame(dict(cfg=cfg, era=era, date=d.index, c5=d.to_numpy())))
            for b in ("minute", "instant"):
                Q, _, info, st, ex = out[b]
                _record_rows("C5", cfg, era, b, Q, ex.get("fill_perp", np.full(len(Q), np.nan)),
                             ex.get("late", np.zeros(len(Q), bool)), info, st)
        except Exception:
            traceback.print_exc()
    return d


# ---------------------------------------------------------------------------------------------------- diagnostics
SUMS = ["fill", "fill_perp", "tp_fill", "gross", "fee_maker", "fee_taker", "cost_hs", "cost_imp", "pnl"]


def _record_rows(variant, cfg, era, bound, Q, fill_perp, late, info, st):
    q = Q[["ts", "coin", "k", "fill_t", "fill", "tp_fill", "gross", "fee_maker", "fee_taker", "cost_hs", "cost_imp",
           "pnl"]].copy()
    q["fill_perp"] = fill_perp
    q["late"] = late
    q["late_perp"] = np.where(late, fill_perp, 0.0)
    q["n"] = (q.fill > 0).astype(int)
    q = q[q.fill > 0]
    g = q.groupby("k")[SUMS + ["late_perp", "n"]].sum().reset_index()
    g["n_late"] = q.groupby("k").late.sum().reindex(g.k).to_numpy()
    for c, v in (("bound", bound), ("era", era), ("cfg", cfg), ("variant", variant)):
        g.insert(0, c, v)
    REC["rungs"].append(g)
    REC["hsim"].append(dict(variant=variant, cfg=cfg, era=era, bound=bound, maker_bp=info.get("maker_bp"),
                            taker_bp=info.get("taker_bp"), v30=info.get("v30"), **st))
    if cfg == "S_0.5":
        q = q.assign(variant=variant, era=era, bound=bound, day=q.fill_t.dt.floor("D"))
        REC["slim"].append(q)


def write_diagnostics():
    os.makedirs(OUTD, exist_ok=True)
    c4 = pd.concat(REC["c4"]) if REC["c4"] else pd.DataFrame(columns=["cfg", "era", "date"])
    c5 = pd.concat(REC["c5"]) if REC["c5"] else pd.DataFrame(columns=["cfg", "era", "date"])
    daily = c4.merge(c5, on=["cfg", "era", "date"], how="outer")
    inc = []
    for (cfg, era), g in daily.groupby(["cfg", "era"]):
        s = gates.incumbent_cached(era, cfg)
        inc.append(pd.DataFrame(dict(cfg=cfg, era=era, date=s.index, inc=s.to_numpy())))
    daily = daily.merge(pd.concat(inc), on=["cfg", "era", "date"], how="left")
    daily.to_csv(os.path.join(OUTD, "daily.csv"), index=False, float_format="%.10g")
    pd.concat(REC["rungs"]).to_csv(os.path.join(OUTD, "rungs.csv"), index=False, float_format="%.6g")
    pd.DataFrame(REC["hsim"]).to_csv(os.path.join(OUTD, "hsim_stats.csv"), index=False, float_format="%.6g")
    chk = {}
    for (cfg, era), g in daily.groupby(["cfg", "era"]):
        chk[f"{cfg}/{era}"] = dict(
            c4_trading_vs_cached_incumbent=float((g.c4_trading - g.inc).abs().max()) if "c4_trading" in g else None,
            c5_vs_cached_incumbent=float((g.c5 - g.inc).abs().max()) if "c5" in g else None)
    # cascade days: the S_0.5 days with the largest |C5 - incumbent| (1-second blend), detail by coin and rung
    if REC["slim"] and "c5" in daily:
        d = daily[daily.cfg == "S_0.5"].assign(diff=lambda x: x.c5 - x.inc)
        top = d.reindex(d["diff"].abs().sort_values(ascending=False).index).head(8)
        sl = pd.concat(REC["slim"])
        sl = sl[sl.day.isin(top.date) & (sl.bound == "instant")]
        det = sl.groupby(["day", "coin", "k", "variant"])[["fill", "fill_perp", "tp_fill", "pnl"]].sum().unstack("variant")
        det.columns = [f"{a}_{b}" for a, b in det.columns]
        det.reset_index().to_csv(os.path.join(OUTD, "cascade_days_S05.csv"), index=False, float_format="%.6g")
        top[["era", "date", "inc", "c5", "diff"]].to_csv(os.path.join(OUTD, "top_days_S05.csv"), index=False,
                                                         float_format="%.6g")
    usdc_close()
    json.dump(dict(reproduction=chk, usdc=_U.get("info")), open(os.path.join(OUTD, "diag.json"), "w"), indent=1,
              default=float)
    print(json.dumps(chk, indent=1, default=float))


# ---------------------------------------------------------------------------------------------------- modes
NOTES = {"C4_usdc": "scenario A: (max(0; T-bill - 0.5%)/365 halved when cost_mult 2 + Bitstamp usdcusd daily change) "
                    "x (1 - day-average positions/C); positions from hsim.book instant Q",
         "C5_perp_venue": "perp capacity restored (in_perp_raw; tp_perp_raw); perp fee and half-spread x2 when "
                          "cost_mult 2; holds unchanged; hsim positions include perp fills"}


def check(era="chk", cfg="S_0.5"):
    """Off switches in one era and configuration: C4 with rate 0 and no USDC mark, C5 with no perp capacity, against
    the cached live incumbent (max daily difference must be 0)."""
    tag = fsim.ERAS[era][0]
    P, pan = gates.data(tag)
    kw = gates.CONFIGS[cfg]
    inc = gates.incumbent_cached(era, cfg)
    res = {}
    for name, fn in (("C4_usdc off (rate 0, no USDC mark)",
                      lambda: c4_book(P, era, pan=pan, adv_=gates.adv(tag, era), rate=False, mark=False, record=False,
                                      **kw)),
                     ("C5_perp_venue off (perp capacity 0)",
                      lambda: c5_book(P, era, pan=pan, adv_=gates.adv(tag, era), perp=False, record=False, **kw))):
        t0 = time.time()
        d = fn()
        diff = float(np.abs(d.reindex(inc.index, fill_value=0.0) - inc).max())
        res[name] = dict(era=era, cfg=cfg, max_abs_daily_diff=diff, days=len(inc), seconds=round(time.time() - t0))
        print(name, res[name], flush=True)
    os.makedirs(OUTD, exist_ok=True)
    json.dump(res, open(os.path.join(OUTD, f"offswitch_{era}_{cfg}.json"), "w"), indent=1)
    return res


def main():
    os.makedirs(OUTD, exist_ok=True)
    usdc_close()
    print("USDC/USD data:", json.dumps(_U["info"]), flush=True)
    log = []
    for name, fn in (("C4_usdc", c4_book), ("C5_perp_venue", c5_book)):
        out = gates.run(name, fn, path="return", note=NOTES[name])
        s = gates.summary(out)
        print(s, f"({out['seconds']} s)", flush=True)
        log.append(s)
        open(os.path.join(OUTD, "trials_log.txt"), "w").write("\n\n".join(log) + "\n")
    try:
        write_diagnostics()
    except Exception:
        traceback.print_exc()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "check":
        check(*sys.argv[2:4])
    else:
        main()
