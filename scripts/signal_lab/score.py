#!/usr/bin/env python3
"""Signal lab (reports/signal_lab/prereg.md): screen statistics, the engine-faithful binding test, gates and scorecard.

  python scripts/signal_lab/score.py screenstats            SPA / StepM / deflated Sharpe of the development screen
  python scripts/signal_lab/score.py cells NAME [CFG ...] [--eras sel,chk,early]
        engine-faithful daily series of one book (NAME = R2-08 or a finalist spec) -> reports/signal_lab/cells/
  python scripts/signal_lab/score.py report                 gates and the 100-point scorecard from the cells

The engine-faithful book is ladder v6's frozen replay (scripts/ladder_v6x/frozen/rt_live.py through lsim): resting
bids hold cash, 1-second blend. A finalist's dataset lives under the tag <era tag>_<spec> (built by model.py chain).
Each cell is stored with the remainder's market exit priced two ways: "model" (the same rule for every book; primary)
and "print" (R2-08's own fills on Coinbase prints, any other fill on the model; information).
"""
import json
import math
import os
import sys

import numpy as np
import pandas as pd
from scipy.stats import norm

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "scripts", "ladder_v6x"))
import lsim  # noqa: E402
from edge import book as edge_book  # noqa: E402

fsim, RL = lsim.fsim, lsim.RL
sim = fsim.sim
OUT = os.path.join(ROOT, "reports", "signal_lab")
CELLS = os.path.join(OUT, "cells")
CFGS = ("S_0.5", "S_0.25", "cap_1M", "base_0.5")
ERAS = ("sel", "chk", "early")
INC = "R2-08"
EULER = 0.5772156649


# ------------------------------------------------------------------------------------------------ helpers
def fix_scale():
    orig = fsim.today_scale
    cache = {}

    def fixed(P, lo, hi):
        k = (str(lo), str(hi))
        if k not in cache:
            base = "early" if pd.Timestamp(lo).year < 2024 else "main"
            cache[k] = orig(fsim.load(base), lo, hi)
        return cache[k]

    fsim.today_scale = fixed


def excess(d, era):
    lo, hi = fsim.ERAS[era][1]
    idx = pd.date_range(lo, hi, freq="D")
    r = d.reindex(idx, fill_value=0.0)
    return r, r.to_numpy() - edge_book.rf_daily(idx).to_numpy()


def stationary_idx(n, rng, mean_block=7):
    out = np.empty(n, int)
    i = rng.integers(n)
    for t in range(n):
        out[t] = i
        i = rng.integers(n) if rng.random() < 1.0 / mean_block else (i + 1) % n
    return out


def sharpe(e):
    return float(e.mean() / e.std(ddof=1) * math.sqrt(365))


# ------------------------------------------------------------------------------------------------ screen statistics
def screenstats():
    S = pd.read_csv(os.path.join(OUT, "screen.csv"))
    D = [pd.read_parquet(os.path.join(OUT, f)) for f in sorted(os.listdir(OUT))
         if f.startswith("screen_daily_") and "incumbent" not in f]
    D = pd.concat(D, axis=1)
    D = D.loc[:, ~D.columns.duplicated()]
    lo, hi = fsim.ERAS["sel"][1]
    idx = pd.date_range(lo, hi, freq="D")
    rf = edge_book.rf_daily(idx).to_numpy()
    E = D.reindex(idx).fillna(0.0).to_numpy() - rf[:, None]
    cols = D.columns.tolist()
    j0 = cols.index("RF0")
    Z = E / E.std(0, ddof=1)
    d = np.delete(Z - Z[:, [j0]], j0, axis=1)
    names = [c for c in cols if c != "RF0"]
    n = len(d)
    rng = np.random.default_rng(7)
    B = 2000
    boots = np.empty((B, d.shape[1]))
    for b in range(B):
        boots[b] = d[stationary_idx(n, rng)].mean(0)
    dbar, om = d.mean(0), boots.std(0, ddof=1)
    t = dbar / om
    T = max(float(np.nanmax(t)), 0.0)
    mu_c = np.where(t <= -math.sqrt(2 * math.log(math.log(n))), dbar, 0.0)
    p_spa = float(np.mean(np.maximum(np.nanmax((boots - dbar + mu_c) / om, axis=1), 0) >= T))
    cen = (boots - dbar) / om
    active, rej = np.ones(len(names), bool), np.zeros(len(names), bool)
    while active.any():
        q = np.nanquantile(np.nanmax(cen[:, active], axis=1), 0.95)
        new = active & (t > q)
        if not new.any():
            break
        rej |= new
        active &= ~new
    srd = d.mean(0) / d.std(0, ddof=1)
    var_d = float(np.var(srd, ddof=1))

    def sr0(nn):
        return math.sqrt(var_d) * ((1 - EULER) * norm.ppf(1 - 1 / nn) + EULER * norm.ppf(1 - 1 / (nn * math.e)))

    def dsr(x, s0):
        sr = x.mean() / x.std(ddof=1)
        z = (x - x.mean()) / x.std(ddof=0)
        g3, g4 = float((z ** 3).mean()), float((z ** 4).mean())
        return float(norm.cdf((sr - s0) * math.sqrt(len(x) - 1) / math.sqrt(max(1 - g3 * sr + (g4 - 1) / 4 * sr ** 2, 1e-12))))

    rows = []
    for j, nm in enumerate(names):
        rows.append(dict(spec=nm, t_vm=float(t[j]), stepm=bool(rej[j]), dsr_n=dsr(d[:, j], sr0(len(names))),
                         dsr_n_plus_9700=dsr(d[:, j], sr0(len(names) + 9700))))
    R = S.merge(pd.DataFrame(rows), on="spec", how="left").sort_values("sharpe", ascending=False)
    R.to_csv(os.path.join(OUT, "screen_stats.csv"), index=False)
    lines = [f"Development screen (selection era, frozen simulator, S* theta 0.5, $250K): {len(names)} trials",
             f"Hansen SPA vs the incumbent (vol-matched daily difference): T {T:.2f}, p {p_spa:.3f}; StepM rejections at 5%: "
             f"{int(rej.sum())}", f"cross-spec SD of the improvement's annualized Sharpe {math.sqrt(var_d * 365):.3f}", "",
             R[["spec", "sharpe", "d_sharpe", "ret_yr", "maxdd", "trades", "share_kept", "overlap", "t_vm", "stepm",
                "dsr_n", "dsr_n_plus_9700"]].round(3).to_string(index=False)]
    S["h"] = S.spec.str.endswith("H")
    piv = S[~S.h].pivot(index="label", columns="fset", values="d_sharpe").reindex(index=["R", "S4", "LD", "LS"])
    g1 = piv[["F0", "F1", "F2", "F3", "F4"]]
    lines += ["", "ΔSharpe vs the incumbent, label x feature set (no added history):", piv.round(3).to_string(),
              "", "Round-1 grid (F0-F4) mean by label: " + ", ".join(f"{k} {v:+.3f}" for k, v in g1.mean(1).items()),
              "Round-1 grid mean by feature set: " + ", ".join(f"{k} {v:+.3f}" for k, v in g1.mean(0).items())]
    H = S[S.h].copy()
    H["twin"] = H.spec.str[:-1]
    H = H.merge(S[~S.h][["spec", "sharpe"]].rename(columns={"spec": "twin", "sharpe": "sharpe_twin"}), on="twin")
    H["gain_from_history"] = H.sharpe - H.sharpe_twin
    lines += ["", "With the 2021-23 candidates added to training (H):",
              H[["spec", "sharpe", "d_sharpe", "sharpe_twin", "gain_from_history"]].round(3).to_string(index=False)]
    txt = "\n".join(lines) + "\n"
    open(os.path.join(OUT, "screen_stats.txt"), "w").write(txt)
    print(txt)


# ------------------------------------------------------------------------------------------------ binding cells
def twin(name, era):
    """The book whose dataset a spec uses in an era: an H spec runs without H in 2022-23 (no earlier history exists),
    so RF0H is R2-08 there and RF2H is RF2."""
    if fsim.ERAS[era][0] == "early" and name.endswith("H"):
        return INC if name == "RF0H" else name[:-1]
    return name


def tag_of(name, era):
    base = fsim.ERAS[era][0]
    name = twin(name, era)
    if name == INC:
        return base
    t2 = f"{base}_{name}"
    sim.PERIODS[t2] = sim.PERIODS[base]
    return t2


def cell(name, cfg, era):
    kw = lsim.CONFIGS[cfg]
    A = RL.era_arrays(tag_of(name, era), era, kw["theta"], kw["C"], kw["today"])
    d, meta = {}, {}
    for bound in ("minute", "instant"):
        R = RL.replay(A, theta=kw["theta"], C=kw["C"], bound=bound, policy="engine")
        _, Qo, info = RL.evaluate_live(A, R, kw["theta"], kw["C"], era, kw["cost_mult"])
        for c in ("model", "print"):
            d[(bound, c)], hit, _ = lsim.rem_daily(Qo, info, cfg, era, kw["C"], cost=c)
            if c == "print":
                meta[f"print_share_{bound}"] = float(hit) if np.isfinite(hit) else float("nan")
        meta[f"fills_{bound}"] = int((Qo.fill > 0).sum())
        meta[f"fill_usd_{bound}"] = float(Qo.fill.sum())
    out = pd.DataFrame({c: lsim.blend(era, kw["theta"], d[("minute", c)], d[("instant", c)]) for c in ("model", "print")})
    return out, meta


def cells(name, cfgs, eras):
    lsim.ensure_frozen()
    fix_scale()
    os.makedirs(CELLS, exist_ok=True)
    mp = os.path.join(CELLS, "meta.csv")
    for cfg in cfgs:
        for era in eras:
            tw = os.path.join(CELLS, f"{twin(name, era)}__{cfg}__{era}.parquet")
            if twin(name, era) != name and os.path.exists(tw):       # same dataset: reuse the twin's cell
                pd.read_parquet(tw).to_parquet(os.path.join(CELLS, f"{name}__{cfg}__{era}.parquet"))
                print(f"{name} {cfg} {era}: = {twin(name, era)}", flush=True)
                continue
            out, meta = cell(name, cfg, era)
            out.to_parquet(os.path.join(CELLS, f"{name}__{cfg}__{era}.parquet"))
            st = fsim.stats(out["model"], lsim.CONFIGS[cfg]["C"], era)
            sp = fsim.stats(out["print"], lsim.CONFIGS[cfg]["C"], era)
            row = dict(book=name, cfg=cfg, era=era, sharpe_model=st["sharpe"], ret_model=st["ret_yr"],
                       sharpe_print=sp["sharpe"], ret_print=sp["ret_yr"], **meta)
            pd.DataFrame([row]).to_csv(mp, mode="a", header=not os.path.exists(mp), index=False)
            print(f"{name} {cfg} {era}: model {st['sharpe']:.3f} / {100 * st['ret_yr']:.2f}%, print {sp['sharpe']:.3f} / "
                  f"{100 * sp['ret_yr']:.2f}%", flush=True)


# ------------------------------------------------------------------------------------------------ report
def load_cell(name, cfg, era, cost="model"):
    return pd.read_parquet(os.path.join(CELLS, f"{name}__{cfg}__{era}.parquet"))[cost]


def report():
    F = json.load(open(os.path.join(OUT, "finalists.json")))
    fins = [f["spec"] for f in F["finalists"]]
    rows, tests, score = [], [], []
    pvals = {}
    for cost in ("model", "print"):
        for f in fins:
            for cfg in CFGS:
                C = lsim.CONFIGS[cfg]["C"]
                for era in ERAS:
                    a, b = load_cell(f, cfg, era, cost), load_cell(INC, cfg, era, cost)
                    sa, sb = fsim.stats(a, C, era), fsim.stats(b, C, era)
                    rows.append(dict(cost=cost, spec=f, cfg=cfg, era=era, sharpe=sa["sharpe"], sharpe_inc=sb["sharpe"],
                                     d_sharpe=sa["sharpe"] - sb["sharpe"], ret=sa["ret_yr"], ret_inc=sb["ret_yr"],
                                     maxdd=sa["maxdd"], maxdd_inc=sb["maxdd"], worst=float(a.min()), worst_inc=float(b.min())))
    T = pd.DataFrame(rows)
    T.to_csv(os.path.join(OUT, "holdout_cells.csv"), index=False)
    rng = np.random.default_rng(11)
    for f in fins:
        parts, gains = [], []
        for era in ("early", "chk"):
            ra, ea = excess(load_cell(f, "S_0.5", era), era)
            rb, eb = excess(load_cell(INC, "S_0.5", era), era)
            parts.append(ea / ea.std(ddof=1) - eb / eb.std(ddof=1))
            gains.append((ra - rb).to_numpy())
        d = np.concatenate(parts)
        bs = np.array([d[stationary_idx(len(d), rng)].mean() for _ in range(5000)])
        pvals[f] = float(np.mean((bs - d.mean()) >= d.mean()))
        g = np.concatenate(gains)
        top5 = float(np.sort(g)[-5:].sum())
        tests.append(dict(spec=f, pooled_mean_vm=float(d.mean()), t_boot=float(d.mean() / bs.std(ddof=1)), p_raw=pvals[f],
                          pooled_gain=float(g.sum()), top5_share=(top5 / g.sum() if g.sum() > 0 else float("nan"))))
    cand = [f["spec"] for f in F["finalists"] if f.get("role", "candidate") == "candidate"]
    order = sorted(cand, key=lambda x: pvals[x])
    holm, run = {f: pvals[f] for f in fins}, 0.0          # information-only finalists keep their raw p
    for i, f in enumerate(order):
        run = max(run, min(1.0, (len(order) - i) * pvals[f]))
        holm[f] = run
    lines = ["Signal lab: binding test on the engine-faithful simulator (model-priced exits unless stated)", ""]
    M = T[T.cost == "model"]
    for f in fins:
        m = M[M.spec == f]
        prim = m[m.cfg == "S_0.5"].set_index("era")
        g1 = bool((prim.d_sharpe >= 0.20).all())
        g2 = bool((m[m.cfg != "S_0.5"].d_sharpe >= 0).all())
        risk = [(prim.loc[e, "maxdd"] >= 1.1 * prim.loc[e, "maxdd_inc"], prim.loc[e, "worst"] >= 1.1 * prim.loc[e, "worst_inc"])
                for e in ERAS]
        g3 = all(a and b for a, b in risk)
        ser = pd.concat([load_cell(f, "S_0.5", e) for e in ERAS]).sort_index()
        yrs = ser.groupby(ser.index.year).sum()
        g4 = bool((yrs > 0).all())
        g5 = holm[f] <= 0.05
        tt = next(x for x in tests if x["spec"] == f)
        tt.update(p_holm=holm[f], g1=g1, g2=g2, g3=g3, g4=g4, g5=g5, passed=bool(g1 and g2 and g3 and g4 and g5),
                  years=json.dumps({int(k): round(float(v), 4) for k, v in yrs.items()}))
        hand = next(x for x in F["finalists"] if x["spec"] == f)["hand"]
        hold = prim.loc[["chk", "early"]]
        cap = m[(m.cfg == "cap_1M") & m.era.isin(["chk", "early"])]
        pts = dict(sharpe=25 * float(np.clip(hold.d_sharpe.mean() / 0.40, 0, 1)),
                   capacity=10 * float(np.clip(cap.d_sharpe.mean() / 0.40, 0, 1)),
                   consistency=15 * float((m.d_sharpe > 0).mean()),
                   evidence=15 * float(np.clip((0.20 - holm[f]) / 0.15, 0, 1)),
                   spread=(10 * float(np.clip((1 - tt["top5_share"]) / 0.5, 0, 1)) if tt["pooled_gain"] > 0 else 0.0),
                   risk=8 * float(np.mean([x for pair in risk for x in pair])) + (2 if g4 else 0),
                   mechanism=float(hand[0]), implementation=float(hand[1]))
        pts["total"] = sum(pts.values())
        score.append(dict(spec=f, **pts))
        lines += [f"== {f}: {'PASS' if tt['passed'] else 'FAIL'}  (gates 1-5: {g1} {g2} {g3} {g4} {g5}); score "
                  f"{pts['total']:.1f}/100",
                  m.pivot(index="cfg", columns="era", values="d_sharpe").reindex(index=list(CFGS), columns=list(ERAS))
                  .round(3).to_string(),
                  "primary cells (Sharpe, incumbent, return, incumbent, max DD, incumbent, worst day, incumbent):",
                  prim[["sharpe", "sharpe_inc", "ret", "ret_inc", "maxdd", "maxdd_inc", "worst", "worst_inc"]]
                  .reindex(list(ERAS)).round(4).to_string(),
                  f"pooled holdout: bootstrap t {tt['t_boot']:.2f}, p {tt['p_raw']:.3f}, Holm {holm[f]:.3f}; top-5-day share "
                  f"of the gain {tt['top5_share']:.2f}; by year {tt['years']}",
                  "print-priced (information): " + ", ".join(
                      f"{e} {T[(T.cost == 'print') & (T.spec == f) & (T.cfg == 'S_0.5') & (T.era == e)].d_sharpe.iloc[0]:+.3f}"
                      for e in ERAS), ""]
    pd.DataFrame(tests).to_csv(os.path.join(OUT, "holdout_tests.csv"), index=False)
    Sc = pd.DataFrame(score)
    Sc.to_csv(os.path.join(OUT, "holdout_scorecard.csv"), index=False)
    lines += ["Scorecard:", Sc.round(1).to_string(index=False)]
    txt = "\n".join(lines) + "\n"
    open(os.path.join(OUT, "holdout.txt"), "w").write(txt)
    print(txt)


if __name__ == "__main__":
    mode = sys.argv[1]
    if mode == "screenstats":
        screenstats()
    elif mode == "cells":
        args = sys.argv[2:]
        eras = ERAS
        if "--eras" in args:
            i = args.index("--eras")
            eras = tuple(args[i + 1].split(","))
            args = args[:i] + args[i + 2:]
        cells(args[0], tuple(args[1:]) or CFGS, eras)
    elif mode == "report":
        report()
