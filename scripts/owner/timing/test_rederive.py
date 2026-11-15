#!/usr/bin/env python3
"""Offline tests of the part 3 runner (rederive_runner.py) on synthetic prints laid out as the first fetch's
artifacts (art/<run>/hunt2-timing-s<n>-<run>/prints_<n>.parquet); the rows on file are made by the part 1 code
(prints_runner.derive_window with the six old starts). No request is made.
usage: python scripts/owner/timing/test_rederive.py
"""
import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import prints_derive as PD  # noqa: E402
import prints_runner as PR  # noqa: E402
import rederive_runner as RR  # noqa: E402

TICK = 0.01
Q0 = pd.Timestamp("2025-03-01 12:00:00")
HAND = Q0 + pd.Timedelta(minutes=30)                      # the hand-made minute of window 3


def synth(root, seed=3):
    """Two shards, four windows: random prints (with runs of prints in the same microsecond), a window whose second
    minute has no print, and one hand-made minute. Returns (art, rows path, derived dir)."""
    rng = np.random.default_rng(seed)
    art, ddir = os.path.join(root, "art"), os.path.join(root, "derived")
    os.makedirs(ddir)
    rows, prints, pres = [], {}, {}
    tid = 1000
    specs = [(0, 0, Q0, 3), (1, 0, Q0 + pd.Timedelta(minutes=10), 2), (2, 1, Q0 + pd.Timedelta(minutes=20), 2),
             (3, 1, HAND, 1)]
    for wid, shard, q, nmin in specs:
        start, end = q, q + pd.Timedelta(minutes=nmin - 1, seconds=70)
        if wid == 3:
            # hand-made: prints at 1 s (100.05), exactly 11.7 s (99.97), 11.7 s again (99.95), 30 s (99.90)
            t = [start + pd.Timedelta(milliseconds=x) for x in (1000, 11700, 11700, 30000)]
            p = [100.05, 99.97, 99.95, 99.90]
        elif wid == 1:
            # second minute without any print in its [q, q + 70 s): prints in [q, q + 50 s) only
            n = 60
            t = sorted([start + pd.Timedelta(microseconds=int(x)) for x in rng.uniform(0, 50e6, n)])
            p = list(100 + np.cumsum(rng.normal(0, 0.03, len(t))))
        else:
            n = 400
            base = np.sort(rng.uniform(0, (end - start).total_seconds() * 1e6, n)).astype(np.int64)
            base = np.repeat(base, rng.integers(1, 4, n))           # several prints in one microsecond
            t = [start + pd.Timedelta(microseconds=int(x)) for x in base]
            p = list(np.round(100 + np.cumsum(rng.normal(0, 0.03, len(t))), 2))
        ids = list(range(tid, tid + len(t)))
        tid += len(t) + 10
        D = pd.DataFrame(dict(trade_id=np.array(ids, np.int64), time=pd.to_datetime(t).astype("datetime64[ns]"),
                              price=np.array(p, float), size=1.0, side="BUY"))
        if wid == 0:                                       # a duplicated page: the same trade twice
            D = pd.concat([D, D.iloc[5:8]], ignore_index=True)
        prints[wid] = (shard, D)
        pres[wid] = pd.Series(dict(trade_id=1, time=start - pd.Timedelta(seconds=2), price=100.2))
        for m in range(nmin):
            qq = q + pd.Timedelta(minutes=m)
            L = 100.0 - 0.03 * m if wid != 3 else 100.0
            rows.append(dict(tag="main", coin=f"C{wid}", q=qq, L_prev=L + 0.02, L=L, tick=TICK, window_id=wid))
    R = pd.DataFrame(rows)
    rpath = os.path.join(root, "rows.csv.gz")
    R.to_csv(rpath, index=False)
    for shard in (0, 1):
        run = 4280000000 + shard
        sub = os.path.join(art, str(run), f"hunt2-timing-s{shard}-{run}")
        os.makedirs(sub)
        P = pd.concat([D.assign(window_id=np.int32(w)) for w, (s, D) in prints.items() if s == shard],
                      ignore_index=True)
        P = P[["window_id"] + [c for c in P.columns if c != "window_id"]]
        P.to_parquet(os.path.join(sub, f"prints_{shard}.parquet"), index=False)
        out, st = [], []
        for w, (s, D) in prints.items():
            if s != shard:
                continue
            dv = PR.derive_window(D, pres[w], R[R.window_id == w])
            for x in dv:
                x["status"] = "complete"
            out += dv
            st.append(dict(window_id=w, product=f"C{w}-USD", status="complete"))
        Dd = pd.DataFrame(out)
        front = ["tag", "coin", "q", "window_id", "status"]
        Dd = Dd[front + [c for c in Dd.columns if c not in front]]
        Dd.to_parquet(os.path.join(ddir, f"derived_{shard}.parquet"), index=False, compression="zstd")
        pd.DataFrame(st).to_csv(os.path.join(ddir, f"status_{shard}.csv"), index=False)
    return art, rpath, ddir


def run(art, rpath, ddir, out):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = RR.main(art, rpath, ddir, out)
    info = json.load(open(os.path.join(out, "rederive_run.json")))
    return rc, info, buf.getvalue()


def load3(out):
    D = pd.concat([pd.read_parquet(os.path.join(out, f)) for f in sorted(os.listdir(out)) if f.startswith("derived3_")],
                  ignore_index=True)
    D["q"] = pd.to_datetime(D.q)
    return D


def test_reproduces_and_old_starts():
    with tempfile.TemporaryDirectory() as root:
        art, rpath, ddir = synth(root)
        out = os.path.join(root, "out")
        rc, info, _ = run(art, rpath, ddir, out)
        assert rc == 0 and info["reproduced"] is True, info
        assert info["rows_compared"] == 8 and info["rows_differing"] == 0 and info["union_recovery_bad"] == 0
        assert info["starts"] == sorted(set(PD.STARTS) | set(RR.NEW)) and len(info["starts"]) == 15
        C = pd.read_csv(os.path.join(out, "rederive_check.csv"))
        assert C.identical.all() and (C.rows_differing == 0).all()
        D3 = load3(out)
        F = pd.concat([pd.read_parquet(os.path.join(ddir, f"derived_{s}.parquet")) for s in (0, 1)], ignore_index=True)
        F["q"] = pd.to_datetime(F.q)
        assert set(zip(D3.coin, D3.q)) == set(zip(F.coin, F.q))
        R = pd.read_csv(rpath, parse_dates=["q"]).set_index(["coin", "q"])
        art_p = pd.concat([pd.read_parquet(os.path.join(dp, f)) for dp, _, fs in os.walk(art) for f in fs])
        for x in D3.itertuples():
            r = R.loc[(x.coin, x.q)]
            P = art_p[art_p.window_id == x.window_id].drop_duplicates("trade_id").sort_values(["time", "trade_id"])
            ms = ((P.time.to_numpy().astype("datetime64[ns]").astype(np.int64) - x.q.value) / 1e6)
            k = (ms >= 0) & (ms < PD.WIN_MS)
            old = PD.derive(ms[k], P.price.to_numpy()[k], x.pre_ms, x.pre_px, r.L_prev, r.L, r.tick)   # old default
            rec = RR.paths_from_union(x.un_ms, x.un_px, PD.STARTS)
            for s in PD.STARTS:
                assert RR.same_list(rec[s][0], old[f"rl_ms_{s}"]) and RR.same_list(rec[s][1], old[f"rl_px_{s}"])
                for c in RR.SCALAR:
                    assert RR.same_scalar(getattr(x, f"{c}_{s}"), old[f"{c}_{s}"]), (s, c)
            new = PD.derive(ms[k], P.price.to_numpy()[k], x.pre_ms, x.pre_px, r.L_prev, r.L, r.tick,
                            starts=RR.STARTS)
            rec = RR.paths_from_union(x.un_ms, x.un_px, RR.STARTS)
            for s in RR.STARTS:
                assert RR.same_list(rec[s][0], new[f"rl_ms_{s}"]) and RR.same_list(rec[s][1], new[f"rl_px_{s}"])


def test_hand_minute():
    with tempfile.TemporaryDirectory() as root:
        art, rpath, ddir = synth(root)
        out = os.path.join(root, "out")
        run(art, rpath, ddir, out)
        D3 = load3(out).set_index(["coin", "q"])
        x = D3.loc[("C3", HAND)]
        rec = RR.paths_from_union(x.un_ms, x.un_px, RR.STARTS)
        # a print exactly at the start time (11.7 s) belongs to the path from 11.7 s, not to the last print before it
        assert x.last_px_11700 == 100.05 and x.last_ms_11700 == 1000.0
        assert list(rec[11700][0]) == [11700.0, 11700.0, 30000.0] and list(rec[11700][1]) == [99.97, 99.95, 99.90]
        # 12.15 s: both 11.7 s prints are before it
        assert x.last_px_12150 == 99.95 and x.last_ms_12150 == 11700.0
        assert list(rec[12150][0]) == [30000.0] and list(rec[12150][1]) == [99.90]
        # no print before the start: the last print is the one before q (on file)
        assert x.pre_px == 100.2 and x.pre_ms == -2000.0
        assert x.last_px_0 == 100.2 and x.last_ms_0 == -2000.0
        # level 100, one tick: first through at 99.99 or below -> 11.7 s for every start up to 11.7 s
        for s in (0, 2000, 5200, 10200, 11080, 11700):
            assert getattr(x, f"ft_cur_{s}") == 11700.0, s
        for s in (12150, 13900, 17250, 24000):
            assert getattr(x, f"ft_cur_{s}") == 30000.0, s
        # path from 24 s: the 30 s print only; the start-0 path holds 100.05, 99.97, 99.95, 99.90
        assert list(rec[24000][1]) == [99.90] and list(rec[0][1]) == [100.05, 99.97, 99.95, 99.90]
        # a minute with no print: empty paths, the last print is the one before q, n70 = 0
        y = D3.loc[("C1", Q0 + pd.Timedelta(minutes=11))]
        assert y.n60 == 0 and y.n70 == 0 and np.isnan(y.min60)
        assert len(y.un_ms) == 0
        for s in RR.STARTS:
            assert np.isnan(getattr(y, f"ft_cur_{s}")) and getattr(y, f"last_px_{s}") == y.pre_px
        assert y.pre_ms < -10000                          # the last print of the minute before


def test_changed_row_caught():
    with tempfile.TemporaryDirectory() as root:
        art, rpath, ddir = synth(root)
        f = os.path.join(ddir, "derived_1.parquet")
        F = pd.read_parquet(f)
        v = list(F.at[0, "rl_px_10000"])
        assert len(v)
        v[-1] = v[-1] + 0.01                               # one path element changed
        F.at[0, "rl_px_10000"] = np.array(v)
        F.at[1, "ft_cur_0"] = 12345.0
        F.to_parquet(f, index=False)
        out = os.path.join(root, "out")
        rc, info, txt = run(art, rpath, ddir, out)
        assert rc == 0 and info["reproduced"] is False and "reproduced: false" in txt
        C = pd.read_csv(os.path.join(out, "rederive_check.csv")).set_index("shard")
        assert C.at[1, "rows_differing"] == 2 and C.at[1, "diff_rl_px_10000"] == 1 and C.at[1, "diff_ft_cur_0"] == 1
        assert C.at[1, "diff_rl_ms_10000"] == 0 and not C.at[1, "identical"]
        assert C.at[0, "rows_differing"] == 0 and C.at[0, "identical"]
        assert os.path.exists(os.path.join(out, "derived3_0.parquet"))
        assert os.path.exists(os.path.join(out, "derived3_1.parquet"))
        # a row missing on file is caught too
        F = pd.read_parquet(os.path.join(ddir, "derived_0.parquet")).iloc[1:]
        F.to_parquet(os.path.join(ddir, "derived_0.parquet"), index=False)
        out2 = os.path.join(root, "out2")
        rc, info, _ = run(art, rpath, ddir, out2)
        C = pd.read_csv(os.path.join(out2, "rederive_check.csv")).set_index("shard")
        assert rc == 0 and info["reproduced"] is False and C.at[0, "missing_on_file"] == 1


def test_exception_reported():
    with tempfile.TemporaryDirectory() as root:
        art, rpath, ddir = synth(root)
        open(os.path.join(ddir, "status_1.csv"), "w").write("not,a\nstatus file\n")   # no window_id column
        out = os.path.join(root, "out")
        rc, info, _ = run(art, rpath, ddir, out)
        assert rc == 0 and info["reproduced"] is False and "Traceback" in info["error"]
        assert os.path.exists(os.path.join(out, "derived3_0.parquet"))              # what was done is kept
        # through the command line too: exit status 0
        out2 = os.path.join(root, "out2")
        p = subprocess.run([sys.executable, os.path.join(HERE, "rederive_runner.py"), art, rpath,
                            os.path.join(root, "nowhere"), out2], capture_output=True, text=True)
        assert p.returncode == 0, p.stderr
        info = json.load(open(os.path.join(out2, "rederive_run.json")))
        assert info["reproduced"] is False


def test_nothing_raw():
    with tempfile.TemporaryDirectory() as root:
        art, rpath, ddir = synth(root)
        out = os.path.join(root, "out")
        run(art, rpath, ddir, out)
        assert sorted(os.listdir(out)) == ["derived3_0.parquet", "derived3_1.parquet", "rederive_check.csv",
                                           "rederive_run.json"]
        D3 = load3(out)
        assert not {"trade_id", "time", "price", "size", "side"} & set(D3.columns)
        assert not [c for c in D3.columns if c.startswith("rl_")]
        art_p = pd.concat([pd.read_parquet(os.path.join(dp, f)) for dp, _, fs in os.walk(art) for f in fs])
        n_raw = art_p.drop_duplicates(["window_id", "trade_id"]).shape[0]
        assert int(D3.un_ms.map(len).sum()) < n_raw / 2   # record lows only
        for x in D3.itertuples():                          # every stored point is on some start's path
            rec = RR.paths_from_union(x.un_ms, x.un_px, RR.STARTS)
            pts = set()
            for s in RR.STARTS:
                pts.update(zip(rec[s][0].tolist(), rec[s][1].tolist()))
            assert pts == set(zip(list(x.un_ms), list(x.un_px)))


def test_union_exact_random():
    rng = np.random.default_rng(7)
    for _ in range(400):
        n = int(rng.integers(0, 120))
        ms = np.sort(rng.choice(np.arange(0, 70000, 250.0), n))      # many prints share a time
        px = np.round(100 + np.cumsum(rng.normal(0, 0.03, n)), 2)    # and a price
        d = PD.derive(ms, px, -100.0, 100.0, 99.9, 99.8, TICK, starts=RR.STARTS)
        um, up = RR.union_path(d, RR.STARTS)
        rec = RR.paths_from_union(um, up, RR.STARTS)
        for s in RR.STARTS:
            assert RR.same_list(rec[s][0], d[f"rl_ms_{s}"]) and RR.same_list(rec[s][1], d[f"rl_px_{s}"]), s
        dd = PD.derive(ms, px, -100.0, 100.0, 99.9, 99.8, TICK)           # default = the six old starts
        assert set(k for k in dd) == set(k for k in d if not any(k.endswith(f"_{s}") for s in RR.NEW))
        for k, v in dd.items():
            assert RR.same_list(v, d[k]) if k.startswith("rl_") else RR.same_scalar(v, d[k]), k


if __name__ == "__main__":
    n = 0
    for name, f in list(globals().items()):
        if name.startswith("test_"):
            f()
            n += 1
    print(f"rederive tests: all {n} passed")
