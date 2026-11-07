#!/usr/bin/env python3
"""H1 fetch + trade-print simulation for one shard (runs on GitHub Actions).

  python scripts/hunt/h1pb/run_shard.py <stage> <shard> <n_shards> [--modes minute,sync] [--coins A,B] [--mock]

stage dev : candidates from each perp's start to 2026-06-01 00:00; nothing at or after HOLD0 is loaded or fetched.
stage hold: candidates from 2026-05-31 10:00 to the end of the data (run only after the freeze commit).
For each chunk of this shard: fetch the perp prints of its windows and (spot-synchronous mode) the spot prints of its
spot windows, compute every trigger and its outcome for k in {3, 4, 6}, long and short, minute and spot-synchronous
latency, H in {60, 15} minutes and theta in {0.5, 0.25}, and the candle-vs-print confirmation of minute-mode
candle-implied fills. Writes reports/hunt/h1pb/<stage>/{entries,confirm,fetchlog}_<shard>.* (small) and the compact
print tapes to out/ (uploaded as a workflow artifact, never committed).
--mock replaces the fetcher with prints synthesised from 1-minute candles (local plumbing test only).
"""
import argparse
import os
import sys
import time

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
import common  # noqa: E402
import kernel  # noqa: E402
import levels as LV  # noqa: E402
import plan as PL  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
HOLD0 = pd.Timestamp("2026-06-01")
KS = (3.0, 4.0, 6.0)
THETAS = np.array([0.5, 0.25])
HS = np.array([60, 15], np.int64) * 60 * kernel.NS
TARGET_USD = 10_000.0
NS = kernel.NS
MIN_NS = 60 * NS


def ts_ns(x):
    return pd.DatetimeIndex(x).asi8 if not isinstance(x, (int, np.integer)) else x


# ------------------------------------------------------------------ fetching
def fetch_prints(pid, segs, mock=None, scale=1.0):
    """Prints of pid in the union of [start, end) Timestamp segments: arrays t (ns), p, q, plus a fetch log."""
    if mock is not None:
        d = mock(pid, segs)
        stt = dict(pid=pid, segments=len(segs), trades=len(d), requests=0, lost_seconds=0, secs=0.0)
    else:
        import fetch
        d, stt = fetch.fetch_segments(pid, segs, threads=4, rate=9.0)
    t = d["time"].to_numpy("datetime64[ns]").astype(np.int64)
    return t, d["price"].to_numpy(np.float64) / scale, d["size"].to_numpy(np.float64), stt


def mock_from_candles(st, kind):
    """Synthetic prints from candles: open at :05, low/high at :20/:35 (order by direction), close at :50."""
    idx = st["idx"]
    pre = "p_" if kind == "perp" else "s_"
    o, h, lo, c = (st[pre + k] for k in ("open", "high", "low", "close"))
    vol = st["p_vol"] if kind == "perp" else np.where(np.isfinite(c), 1.0, 0.0)
    t0 = idx[0].value

    def f(pid, segs):
        rows = []
        for a, b in segs:
            ia, ib = idx.get_indexer([a])[0], idx.get_indexer([b - pd.Timedelta(minutes=1)])[0] + 1
            for i in range(max(ia, 0), ib):
                if not np.isfinite(c[i]):
                    continue
                down = c[i] < o[i]
                seq = [(5, o[i]), (20, h[i] if down else lo[i]), (35, lo[i] if down else h[i]), (50, c[i])]
                for s_, px in seq:
                    rows.append((t0 + i * MIN_NS + s_ * NS, px, max(1.0, vol[i] / 4)))
        d = pd.DataFrame(rows, columns=["t", "price", "size"])
        d["time"] = pd.to_datetime(d["t"])
        return d
    return f


# ------------------------------------------------------------------ one chunk
def tape(st, segs_min, t, p, q):
    """Perp tape with a synthetic print at each segment start (the last price before it, from candles)."""
    t0 = st["idx"][0].value
    pcf = st["p_cf"]
    parts_t, parts_p, parts_q, parts_s, parts_y = [], [], [], [], []
    for sid, (s, e) in enumerate(segs_min):
        lo_ns, hi_ns = t0 + s * MIN_NS, t0 + e * MIN_NS
        a, b = np.searchsorted(t, lo_ns, "left"), np.searchsorted(t, hi_ns, "left")
        prev = pcf[s - 1] if s >= 1 else np.nan
        parts_t.append(np.r_[lo_ns - 1, t[a:b]])
        parts_p.append(np.r_[prev, p[a:b]])
        parts_q.append(np.r_[0.0, q[a:b]])
        parts_s.append(np.full(b - a + 1, sid, np.int32))
        parts_y.append(np.r_[True, np.zeros(b - a, bool)])
    if not parts_t:
        z = np.zeros(0)
        return z.astype(np.int64), z, z, z.astype(np.int32), z.astype(bool)
    return (np.concatenate(parts_t), np.concatenate(parts_p), np.concatenate(parts_q), np.concatenate(parts_s),
            np.concatenate(parts_y))


def spot_last(st, ssegs_min, st_t, st_p, tq):
    """Last spot price at or before each time in tq (ns) inside a fetched spot segment, else NaN."""
    t0 = st["idx"][0].value
    out = np.full(len(tq), np.nan)
    if not len(ssegs_min):
        return out
    starts = np.array([t0 + s * MIN_NS for s, _ in ssegs_min], np.int64)
    ends = np.array([t0 + e * MIN_NS for _, e in ssegs_min], np.int64)
    k = np.searchsorted(starts, tq, "right") - 1
    inside = (k >= 0) & (tq < ends[np.maximum(k, 0)])
    j = np.searchsorted(st_t, tq, "right") - 1
    has = inside & (j >= 0) & (st_t[np.maximum(j, 0)] >= starts[np.maximum(k, 0)])
    out[has] = st_p[j[has]]
    fb = inside & ~has
    s_min = np.array([s for s, _ in ssegs_min], np.int64)[np.maximum(k, 0)]
    prev_close = st["s_cf"][np.maximum(s_min - 1, 0)]
    out[fb] = np.where(s_min[fb] >= 1, prev_close[fb], np.nan)
    return out


def run_chunk(ch, pl, mock, out_dir, tag, modes, ks=KS, sides=("long", "short")):
    coin, st = ch["coin"], pl["st"]
    pid, cs, tick = common.PERP[coin]
    sc = LV.PX_SCALE.get(coin, 1.0)
    idx = st["idx"]
    t0 = idx[0].value
    n_rows = len(idx)
    to_ts = lambda segs: [(idx[0] + pd.Timedelta(minutes=int(s)), idx[0] + pd.Timedelta(minutes=int(e))) for s, e in segs]  # noqa: E731
    logs = []
    pt, pp, pq, lg = fetch_prints(pid, to_ts(ch["psegs"]), mock and mock(st, "perp"), sc)
    logs.append(dict(lg, coin=coin, kind="perp", a=str(idx[ch["a"]]), b=str(idx[min(ch["b"], n_rows - 1)])))
    T, P, Q, SEG, SYN = tape(st, ch["psegs"], pt, pp, pq)
    # completeness: print contracts vs candle contracts over the fetched minutes
    pm = np.zeros(n_rows, bool)
    for s_, e_ in ch["psegs"]:
        pm[s_:e_] = True
    logs[-1].update(print_contracts=float(Q[~SYN].sum()), candle_contracts=float(np.nansum(st["p_vol"][pm])),
                    fetched_minutes=int(pm.sum()))
    row = ((T - NS - t0) // MIN_NS).astype(np.int64)
    okr = (row >= 0) & (row < n_rows)
    rowc = np.clip(row, 0, n_rows - 1)
    cmin = ((T - t0) // MIN_NS).astype(np.int64)                 # candle minute of each print
    keep_lo, keep_hi = t0 + ch["a"] * MIN_NS, t0 + ch["b"] * MIN_NS
    S = np.full(len(T), np.nan)
    if "sync" in modes and len(ch["ssegs"]):
        st_t, st_p, _, lg2 = fetch_prints(f"{coin}-USD", to_ts(ch["ssegs"]), mock and mock(st, "spot"), 1.0)
        logs.append(dict(lg2, coin=coin, kind="spot", a=str(idx[ch["a"]]), b=str(idx[min(ch["b"], n_rows - 1)])))
        o = np.argsort(st_t, kind="stable")
        S = spot_last(st, ch["ssegs"], st_t[o], st_p[o], T - NS)
        S[SYN | ~okr] = np.nan
    bb, sg = st["bbar"][rowc], st["sig"][rowc]
    ents, conf = [], []
    for mode in modes:
        for k in ks:
            for side in sides:
                is_long = side == "long"
                if mode == "minute":
                    Lrow = LV.level(st, k, side)
                    L = np.where(okr, Lrow[rowc], np.nan)
                    F = np.where(okr, st["F"][rowc], np.nan)
                else:
                    with np.errstate(invalid="ignore"):
                        F = S * np.exp(bb)
                        if is_long:
                            L = LV.round_down(F * np.exp(-k * sg), tick)
                            ok = L >= (1 - LV.FVL) * S
                        else:
                            L = LV.round_up(F * np.exp(k * sg), tick)
                            ok = L <= (1 + LV.FVL) * S
                        ok &= np.isfinite(L) & (sg > 0) & okr
                    L = np.where(ok, L, np.nan)
                L[SYN] = np.nan
                if pl.get("delta_mask") is not None:          # delta run: only triggers on changed rows
                    L[~pl["delta_mask"][rowc]] = np.nan
                r = kernel.entries(T, P, Q, SYN, SEG, L, F, is_long, tick, cs, TARGET_USD, THETAS, HS, keep_lo, keep_hi)
                ii, run, ntg, tp, nn, tpn, gross, tclose, remnot, chours, valid = r
                E = pd.DataFrame({"coin": coin, "mode": mode, "k": k, "side": 1 if is_long else -1,
                                  "t_fill": T[ii], "row": row[ii].astype(np.int32), "L": L[ii], "F": F[ii], "TP": tp,
                                  "S": S[ii], "run": run.astype(np.float32), "ntg": ntg.astype(np.int32)})
                for a_, th in enumerate(("50", "25")):
                    E[f"n{th}"] = nn[:, a_].astype(np.int32)
                    for b_, hh in enumerate(("60", "15")):
                        E[f"tpn{hh}_{th}"] = tpn[:, b_, a_].astype(np.int32)
                        E[f"gross{hh}_{th}"] = gross[:, b_, a_]
                        E[f"tclose{hh}_{th}"] = tclose[:, b_, a_]
                        E[f"remnot{hh}_{th}"] = remnot[:, b_, a_]
                        E[f"chours{hh}_{th}"] = chours[:, b_, a_].astype(np.float32)
                for b_, hh in enumerate(("60", "15")):
                    E[f"valid{hh}"] = valid[:, b_]
                if mode == "minute":
                    cf = confirm(st, ch, k, side, Lrow, E, cs, tick)
                    if pl.get("delta_mask") is not None:
                        cf = cf[pl["delta_mask"][cf.row.to_numpy()]]
                    conf.append(cf)
                logs.append(dict(coin=coin, kind=f"triggers_{mode}_{k}_{side}", trades=len(E),
                                 requests=int((E.n50 >= 1).sum()), a=str(idx[ch["a"]])))
                E = E[E.n50 >= 1]
                for c_ in ("L", "F", "TP", "S"):
                    E[c_] = E[c_].astype(np.float32) if coin not in ("BTC",) else E[c_]
                ents.append(E)
    E = pd.concat(ents, ignore_index=True) if ents else pd.DataFrame()
    C = pd.concat(conf, ignore_index=True) if conf else pd.DataFrame()
    if out_dir:
        pd.DataFrame({"t": T, "p": P, "q": Q.astype(np.float32), "seg": SEG, "syn": SYN, "S": S}).to_parquet(
            os.path.join(out_dir, f"tape_{tag}.parquet"), index=False)
    return E, C, logs


def confirm(st, ch, k, side, Lrow, E, cs, tick):
    """Candle-implied minute-mode fills in [a, b) and what the prints say (row u = prints in [u + 1 s, u + 61 s))."""
    a, b = ch["a"], ch["b"]
    u = np.arange(a, b)
    Lu = Lrow[u]
    o, hi, lo, vol = st["p_open"][u], st["p_high"][u], st["p_low"][u], st["p_vol"][u]
    h = 0.5 * tick
    with np.errstate(invalid="ignore", divide="ignore"):
        if side == "long":
            rule = (o > Lu) & (lo < Lu - h)
            frac = np.where(hi > lo, (Lu - lo) / (hi - lo), 1.0)
        else:
            rule = (o < Lu) & (hi > Lu + h)
            frac = np.where(hi > lo, (hi - Lu) / (hi - lo), 1.0)
        rule &= np.isfinite(Lu) & (Lu * cs >= 150.0)
    u, Lu, vol, frac = u[rule], Lu[rule], vol[rule], np.clip(frac[rule], 0, 1)
    first = E.drop_duplicates("row")[["row", "n50", "run", "ntg"]].set_index("row")
    j = first.reindex(u)
    return pd.DataFrame({"coin": ch["coin"], "k": k, "side": 1 if side == "long" else -1, "row": u.astype(np.int32),
                         "price_conf": j["n50"].notna().to_numpy(), "n50_first": j["n50"].fillna(0).to_numpy(np.int32),
                         "run_first": j["run"].fillna(0).to_numpy(np.float32),
                         "ntg": np.floor(10_000.0 / (Lu * cs) + 1e-9).astype(np.int32),
                         "vol_candle": vol.astype(np.float32), "cap_candle50": (0.5 * vol * frac).astype(np.float32)})


# ------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["dev", "dev2", "hold"])
    ap.add_argument("shard", type=int)
    ap.add_argument("n_shards", type=int)
    ap.add_argument("--modes", default="minute,sync")
    ap.add_argument("--coins", default="")
    ap.add_argument("--mock", action="store_true")
    ap.add_argument("--d0", default="")
    ap.add_argument("--d1", default="")
    ap.add_argument("--delta", action="store_true")      # only rows in reports/hunt/h1pb/delta_rows.parquet
    ap.add_argument("--sub", default="")              # "j/m": only chunk j, j+m, ... of this shard (split a slow shard)
    ap.add_argument("--ks", default="3,4,6")
    ap.add_argument("--cand_k", type=float, default=3.0)   # candidate superset depth (hold stage: the frozen k)
    ap.add_argument("--window", default="")              # "lo,hi" ET minutes: candidates only there (frozen tod)
    ap.add_argument("--sides", default="long,short")
    args = ap.parse_args()
    modes = tuple(args.modes.split(","))
    if args.stage in ("dev", "dev2"):
        d0, d1 = pd.Timestamp(args.d0 or "2025-07-01"), pd.Timestamp(args.d1 or HOLD0)
        assert d1 <= HOLD0, "dev stage must end before HOLD"
    else:
        d0, d1 = pd.Timestamp(args.d0 or "2026-05-31 10:00"), pd.Timestamp(args.d1 or LV.GRID_END)
    coins = args.coins.split(",") if args.coins else LV.coins()
    t_start = time.time()
    deltas = None
    if args.delta:
        D = pd.read_parquet(os.path.join(ROOT, "reports", "hunt", "h1pb", "delta_rows.parquet"))
        deltas = {c: np.sort(g.row.to_numpy(np.int64)) for c, g in D.groupby("coin")}
        coins = [c for c in coins if c in deltas]
    kw = dict(cand_k=args.cand_k, cand_sides=tuple(args.sides.split(",")),
              window=tuple(int(x) for x in args.window.split(",")) if args.window else None)
    chs, plans, load = PL.make(coins, d0, d1, args.n_shards, modes, verbose=(args.shard == 0), deltas=deltas, **kw)
    mine = [c for c in chs if c["shard"] == args.shard]
    tag = ("delta" if args.delta else "") + str(args.shard)
    if args.sub:
        j, m = (int(x) for x in args.sub.split("/"))
        mine = [c for i, c in enumerate(mine) if i % m == j]
        tag = f"{tag}_{j}of{m}"
    print(f"plan: {len(chs)} chunks, est. requests per shard {np.round(load).astype(int).tolist()}; this shard "
          f"{len(mine)} chunks ({time.time() - t_start:.0f}s)", flush=True)
    out_rep = os.path.join(os.environ.get("H1_REP") or os.path.join(ROOT, "reports", "hunt", "h1pb"), args.stage)
    os.makedirs(out_rep, exist_ok=True)
    out_raw = os.environ.get("H1_OUT") or os.path.join(ROOT, "out")
    os.makedirs(out_raw, exist_ok=True)
    mock = mock_from_candles if args.mock else None
    E_all, C_all, L_all = [], [], []
    for n_, ch in enumerate(mine):
        t1 = time.time()
        E, C, logs = run_chunk(ch, plans[ch["coin"]], mock, out_raw, f"{args.stage}_{tag}_{n_}", modes,
                               tuple(float(x) for x in args.ks.split(",")), tuple(args.sides.split(",")))
        E_all.append(E)
        C_all.append(C)
        L_all += [dict(l_, chunk=n_, est_cost=ch["cost"]) for l_ in logs]
        print(f"chunk {n_ + 1}/{len(mine)} {ch['coin']} est {ch['cost']:.0f} req: {len(E)} trigger rows, "
              f"{len(C)} candle rows, {time.time() - t1:.0f}s (total {time.time() - t_start:.0f}s)", flush=True)
    E = pd.concat(E_all, ignore_index=True) if E_all else pd.DataFrame()
    C = pd.concat(C_all, ignore_index=True) if C_all else pd.DataFrame()
    E.to_parquet(os.path.join(out_rep, f"entries_{tag}.parquet"), index=False)
    C.to_parquet(os.path.join(out_rep, f"confirm_{tag}.parquet"), index=False)
    pd.DataFrame(L_all).to_csv(os.path.join(out_rep, f"fetchlog_{tag}.csv"), index=False)
    print(f"done: {len(E)} trigger rows, {len(C)} candle rows, {time.time() - t_start:.0f}s", flush=True)


if __name__ == "__main__":
    main()
