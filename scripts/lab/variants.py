"""Round-1 variant list for the wick v2 lab: single changes to v1, as pre-registered
(reports/wick_v2_prereg.md), plus finer neighbours of the base settings."""
from copy import deepcopy

import core  # noqa: E402  (sets up the import path)
from edge import wick  # noqa: E402

BASE = dict(
    ls=dict(L=60, k=4.0, wsig=4320, wbeta=4320, ref="btc", side=1, coins=tuple(core.COINS17)),
    exit=dict(theta=0.6, H=60),
    ai=dict(label="net_base", feats=tuple(wick.FEATS), thr_q=0.5),
    port=dict(cap=6, target=core.TARGET),
)


def v(name, family, ls=None, exit=None, ai=None, port=None, books=None, filt=None):
    d = deepcopy(BASE)
    for key, upd in (("ls", ls), ("exit", exit), ("ai", ai), ("port", port)):
        if upd:
            d[key] = {**d[key], **upd}
    d.update(name=name, family=family)
    if books:
        d["books"] = books            # list of (ls, exit, ai) overrides combined in one portfolio
    if filt:
        d["filt"] = filt
    return d


E1, E2, E3 = core.EXTRA1, core.EXTRA2, core.EXTRA3
F = tuple(wick.FEATS)
TOP12 = None                          # filled at run time from the 2024-trained model's importance
C17 = tuple(core.COINS17)

VARIANTS = [v("V000 base (v1)", "base")]
# ---- A: entry level and reference
VARIANTS += [
    v("A01 k=3.5", "A", ls=dict(k=3.5)), v("A02 k=4.5", "A", ls=dict(k=4.5)), v("A03 k=5", "A", ls=dict(k=5.0)),
    v("A04 L=30", "A", ls=dict(L=30)), v("A05 L=45", "A", ls=dict(L=45)), v("A06 L=90", "A", ls=dict(L=90)),
    v("A07 L=120", "A", ls=dict(L=120)), v("A08 sigma 1 day", "A", ls=dict(wsig=1440)),
    v("A09 sigma 7 days", "A", ls=dict(wsig=10080)), v("A10 beta 1 day", "A", ls=dict(wbeta=1440)),
    v("A11 beta 7 days", "A", ls=dict(wbeta=10080)), v("A12 raw reference", "A", ls=dict(ref="raw")),
    v("A13 basket reference", "A", ls=dict(ref="basket")), v("A14 BTC+ETH reference", "A", ls=dict(ref="btceth")),
    v("A15 add BTC", "A", ls=dict(coins=C17 + ("BTC",))),
    v("A16 ladder k=4 + k=6", "A", books=[{}, {"ls": dict(k=6.0)}]),
    v("A17 BTC-perp beta hedge", "A", port=dict(hedged=True)),
    v("A18 k=3", "A", ls=dict(k=3.0)), v("A19 k=3.75", "A", ls=dict(k=3.75)), v("A20 k=4.25", "A", ls=dict(k=4.25)),
    v("A21 L=75", "A", ls=dict(L=75)), v("A22 sigma 2 days", "A", ls=dict(wsig=2880)),
    v("A23 beta 2 days", "A", ls=dict(wbeta=2880)),
]
# ---- B: exits
VARIANTS += [
    v("B01 take-profit 0.4", "B", exit=dict(theta=0.4)), v("B02 take-profit 0.5", "B", exit=dict(theta=0.5)),
    v("B03 take-profit 0.7", "B", exit=dict(theta=0.7)), v("B04 take-profit 0.8", "B", exit=dict(theta=0.8)),
    v("B05 hold 30", "B", exit=dict(H=30)), v("B06 hold 45", "B", exit=dict(H=45)), v("B07 hold 90", "B", exit=dict(H=90)),
    v("B08 two-stage TP 0.4/0.8", "B", exit=dict(theta=0.4, theta2=0.8, w1=0.5)),
    v("B09 TP tracks fair value - 1 sigma", "B", exit=dict(dyn_z=1.0)),
    v("B10 TP tracks fair value - 0.5 sigma", "B", exit=dict(dyn_z=0.5)),
    v("B11 stop at 30m if < -1 sigma", "B", exit=dict(stop_t=30, stop_k=1.0)),
    v("B12 stop at 15m if < -1.5 sigma", "B", exit=dict(stop_t=15, stop_k=1.5)),
    v("B13 take-profit 0.6, hold 120", "B", exit=dict(H=120)),
    v("B14 take-profit 1.0, hold 120", "B", exit=dict(theta=1.0, H=120)),
    v("B15 no take-profit", "B", exit=dict(theta=None)),
    v("B16 take-profit 0.55", "B", exit=dict(theta=0.55)), v("B17 take-profit 0.65", "B", exit=dict(theta=0.65)),
    v("B18 hold 50", "B", exit=dict(H=50)), v("B19 hold 75", "B", exit=dict(H=75)),
]
# ---- C: AI model
VARIANTS += [
    v("C01 threshold 40th pct", "C", ai=dict(thr_q=0.4)), v("C02 threshold 60th pct", "C", ai=dict(thr_q=0.6)),
    v("C03 threshold 75th pct", "C", ai=dict(thr_q=0.75)), v("C04 threshold pred > 0", "C", ai=dict(thr_abs=0.0)),
    v("C05 threshold pred > 15 bp", "C", ai=dict(thr_abs=15.0)),
    v("C06 label realistic-cost net", "C", ai=dict(label="net_real")),
    v("C07 label take-profit hit (classifier)", "C", ai=dict(label="tp_hit", objective="binary")),
    v("C08 label net / sigma", "C", ai=dict(label="net_per_sig")), v("C09 label clip 200", "C", ai=dict(clip=200)),
    v("C10 num_leaves 3", "C", ai=dict(params=dict(num_leaves=3))),
    v("C11 num_leaves 15", "C", ai=dict(params=dict(num_leaves=15))),
    v("C12 500 rounds, half learning rate", "C", ai=dict(params=dict(learning_rate=0.015), rounds=500)),
    v("C13 min_data_in_leaf 200", "C", ai=dict(params=dict(min_data_in_leaf=200))),
    v("C14 feature_fraction 0.5", "C", ai=dict(params=dict(feature_fraction=0.5))),
    v("C15 huber alpha 30", "C", ai=dict(params=dict(alpha=30.0))),
    v("C16 huber alpha 120", "C", ai=dict(params=dict(alpha=120.0))),
    v("C17 monotone on top 2 features", "C", ai=dict(monotone={"dist_1d_high_bp": -1, "bid_depth_bp": 1})),
    v("C18 monthly retraining", "C", ai=dict(freq="M")),
    v("C19 rolling 12-month window", "C", ai=dict(window_days=365)),
    v("C20 time-decay weights (180d)", "C", ai=dict(halflife=180)),
    v("C21 no episode weighting", "C", ai=dict(weight="none")),
    v("C22 extra features: price structure", "C", ai=dict(feats=F + tuple(E1))),
    v("C23 extra features: flow", "C", ai=dict(feats=F + tuple(E2))),
    v("C24 extra features: calendar", "C", ai=dict(feats=F + tuple(E3))),
    v("C25 extra features: all", "C", ai=dict(feats=F + tuple(E1) + tuple(E2) + tuple(E3))),
    v("C26 top-12 features (2024 model)", "C", ai=dict(feats="TOP12")),
    v("C27 LightGBM + logistic ensemble", "C", ai=dict(logit_ens=True)),
    v("C28 no AI (rule only)", "C", ai=dict(off=True)),
    v("C29 realistic label + 60th pct", "C", ai=dict(label="net_real", thr_q=0.6)),
    v("C30 5 seeds", "C", ai=dict(seeds=(7, 11, 23, 42, 101))),
    v("C31 threshold 45th pct", "C", ai=dict(thr_q=0.45)), v("C32 threshold 55th pct", "C", ai=dict(thr_q=0.55)),
    v("C33 150 rounds", "C", ai=dict(rounds=150)),
    v("C34 learning rate 0.06, 125 rounds", "C", ai=dict(params=dict(learning_rate=0.06), rounds=125)),
]
# ---- D: sizing and portfolio
VARIANTS += [
    v("D01 size by prediction", "D", port=dict(size="pred")), v("D02 size by prediction^2", "D", port=dict(size="pred2")),
    v("D03 equal risk (1/sigma)", "D", port=dict(size="invsig")), v("D04 prediction / sigma", "D", port=dict(size="pred_sig")),
    v("D05 4 x $3,750", "D", port=dict(cap=4, target=3750.0)), v("D06 8 x $1,875", "D", port=dict(cap=8, target=1875.0)),
    v("D07 10 x $1,500", "D", port=dict(cap=10, target=1500.0)),
    v("D08 max 2 new fills per minute", "D", port=dict(max_new_per_min=2)),
    v("D09 volatility-regime scaling", "D", port=dict(regime=True)),
    v("D10 drawdown throttle 5%", "D", port=dict(throttle=0.05)),
    v("D11 prediction-priority slots", "D", port=dict(priority="pred")),
    v("D12 fractional sizing (diagnostic)", "D", port=dict(fractional=True)),
    v("D13 3 x $5,000", "D", port=dict(cap=3, target=5000.0)),
    v("D14 5 x $3,000", "D", port=dict(cap=5, target=3000.0)), v("D15 7 x $2,143", "D", port=dict(cap=7, target=2143.0)),
]
# ---- E: universe
VARIANTS += [
    v("E01 6 core coins", "E", ls=dict(coins=("ETH", "SOL", "XRP", "DOGE", "LTC", "LINK"))),
    v("E02 17 + AVAX + ADA", "E", ls=dict(coins=C17 + ("AVAX", "ADA"))),
    v("E03 17 without ZEC", "E", ls=dict(coins=tuple(c for c in C17 if c != "ZEC"))),
    v("E04 size by perp liquidity", "E", port=dict(size_liq=True)),
    v("E05 ETH, SOL, XRP only", "E", ls=dict(coins=("ETH", "SOL", "XRP"))),
]
# ---- F: rhyming books
VARIANTS += [
    v("F01 sell-the-rip mirror", "F", ls=dict(side=-1)),
    v("F02 15-minute book", "F", ls=dict(L=15)), v("F03 240-minute book", "F", ls=dict(L=240)),
    v("F04 joint 30/60/120 books", "F", books=[{"ls": dict(L=30)}, {}, {"ls": dict(L=120)}]),
    v("F05 dips + rips", "F", books=[{}, {"ls": dict(side=-1)}]),
    v("F06 weekends only (diagnostic)", "F", filt="weekend"), v("F07 weekdays only (diagnostic)", "F", filt="weekday"),
    v("F08 60-minute + 15-minute k=5 books", "F", books=[{}, {"ls": dict(L=15, k=5.0)}]),
]


# ---- round 2: combinations of the best round-1 changes (rule pre-registered in reports/wick_v2_prereg.md)
DIAGNOSTIC = ("D12", "F06", "F07")
PRED_DEPENDENT = {("port", "size"): ("pred", "pred2", "pred_sig"), ("port", "priority"): ("pred",)}
_MISSING = object()


def changes(var):
    """A variant's changes relative to BASE: {(section, key): value} plus books."""
    ch = {}
    for sec in ("ls", "exit", "ai", "port"):
        for k_, val in var[sec].items():
            if BASE[sec].get(k_, _MISSING) != val:
                ch[(sec, k_)] = val
    if var.get("books"):
        ch[("books", None)] = var["books"]
    return ch


def merge(vs):
    """Merge several variants' changes; None if two of them set the same thing differently."""
    out = {}
    for var in vs:
        for k_, val in changes(var).items():
            if k_ in out and out[k_] != val:
                return None
            out[k_] = val
    if out.get(("ai", "off")):
        for (sec, k_), bad in PRED_DEPENDENT.items():
            if out.get((sec, k_)) in bad:
                return None
    return out


def build(name, ch):
    upd = {"ls": {}, "exit": {}, "ai": {}, "port": {}}
    books = None
    for (sec, k_), val in ch.items():
        if sec == "books":
            books = val
        else:
            upd[sec][k_] = val
    return v(name, "R2", ls=upd["ls"], exit=upd["exit"], ai=upd["ai"], port=upd["port"], books=books)


def make_round2(V=None, max_n=20, min_gain=0.05):
    import itertools
    import os
    import pandas as pd
    if V is None:
        ps = [os.path.join(core.ROOT, "reports", "lab", f"results_val_{t}.csv") for t in ("round1", "round1b")]
        if not os.path.exists(ps[0]):
            return []
        V = pd.concat([pd.read_csv(p) for p in ps if os.path.exists(p)], ignore_index=True)
    byname = {x["name"]: x for x in VARIANTS + ROUND1B}
    b0 = V.loc[V.variant == "V000 base (v1)", "val_real_sharpe"].iloc[0]
    E = V[(V.val_trades >= 150) & (V.val_real_sharpe >= b0 + min_gain) & (V.family != "base")
          & ~V.variant.str[:3].isin(DIAGNOSTIC)].sort_values("val_real_sharpe", ascending=False)
    fam = {}
    for r in E.itertuples():
        fam.setdefault(r.family, [])
        if len(fam[r.family]) < 2:
            fam[r.family].append((r.variant, r.val_real_sharpe))
    leads = sorted(((f, xs[0]) for f, xs in fam.items()), key=lambda t: -t[1][1])
    code = lambda n: n.split()[0]  # noqa: E731
    combos = []
    lead_names = [x[1][0] for x in leads]
    if len(lead_names) >= 2:
        combos.append(lead_names)
    combos += [list(p) for p in itertools.combinations(lead_names, 2)]
    if len(lead_names) >= 3:
        combos.append(lead_names[:3])
    for f, xs in fam.items():
        if len(xs) > 1 and len(lead_names) >= 2:
            combos.append([xs[1][0] if n == xs[0][0] else n for n in lead_names])
    out, seen = [], set()
    for names in combos:
        key_ = tuple(sorted(names))
        if key_ in seen:
            continue
        seen.add(key_)
        ch = merge([byname[n] for n in names])
        if ch is None:
            continue
        out.append(build(f"R2-{len(out) + 1:02d} " + "+".join(code(n) for n in names), ch))
        if len(out) >= max_n:
            break
    return out


# ---- round 1b: five more single changes, defined 2026-11-06 ~10:45 ET, before any round-1 result was read
LOW_FEE13 = tuple(c for c in C17 if c not in ("ETH", "LTC", "BCH", "ZEC"))     # contract fee > 3 bp/side at Dec-2024 prices
ROUND1B = [
    v("B20 passive time exit (5 min, then market)", "B", exit=dict(pw=5)),
    v("B21 passive time exit (15 min, then market)", "B", exit=dict(pw=15)),
    v("E06 drop the 4 dearest contracts per $ (ETH, LTC, BCH, ZEC)", "E", ls=dict(coins=LOW_FEE13)),
    v("E07 no bid while a contract is under $667 (fee > 3 bp/side)", "E", ls=dict(minc=667.0)),
    v("A24 sigma scaled by hour-of-day volatility", "A", ls=dict(hod=True)),
]


# ---- round 3 (reports/wick_v3_prereg.md): refinements of R2-08, tested on the fresh 2021-2023 era
R208 = dict(ls=dict(wbeta=10080), ai=dict(label="net_real", thr_q=0.6))
E4 = core.EXTRA4


def r3(name, ls=None, exit=None, ai=None, port=None):
    return v(name, "R3", ls={**R208["ls"], **(ls or {})}, exit=exit, ai={**R208["ai"], **(ai or {})}, port=port)


ROUND3 = [
    r3("R3-01 R2-08 + threshold 65th pct", ai=dict(thr_q=0.65)),
    r3("R3-02 R2-08 + threshold 70th pct", ai=dict(thr_q=0.70)),
    r3("R3-03 R2-08 + threshold 75th pct", ai=dict(thr_q=0.75)),
    r3("R3-04 R2-08 + predicted net > 0 bp", ai=dict(thr_floor=0.0)),
    r3("R3-05 R2-08 + prediction-priority slots", port=dict(priority="pred")),
    r3("R3-06 R2-08 + 8 slots x $1,875", port=dict(cap=8, target=1875.0)),
    r3("R3-07 R2-08 + trend-regime features", ai=dict(feats=F + tuple(E4))),
    r3("R3-08 R2-08 + size by perp liquidity", port=dict(size_liq=True)),
    r3("R3-09 R2-08 + 10 seeds", ai=dict(seeds=(7, 11, 23, 42, 101, 3, 5, 13, 17, 19))),
]


def fresh_variants():
    """The 14 variants of the fresh-era test: incumbents, earlier finalists, round-3 refinements."""
    allv = {x["name"]: x for x in VARIANTS + ROUND1B}
    r2 = {x["name"]: x for x in make_round2()}
    names = ["R2-08 C29+A11", "R2-07 C29+B13", "R2-20 E07+C29+B08+A11+D02+F08", "R2-03 E07+B13"]
    return [allv["V000 base (v1)"]] + [r2[n] for n in names] + ROUND3


FRESH = None  # built lazily (make_round2 reads the round-1 results)
