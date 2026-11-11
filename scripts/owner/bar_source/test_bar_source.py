"""Offline tests of build.py's row assembly and compare.py's measures, on made-up records, tables and logs.
Run: python scripts/owner/bar_source/test_bar_source.py (prints ok / FAIL per check, ends with "all passed")."""
import importlib.util
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, HERE)

import numpy as np          # noqa: E402
import pandas as pd         # noqa: E402

import build                # noqa: E402
import fetch_and_compute as fac   # noqa: E402  (on the path through build)


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


bc = _load("bar_source_compare", os.path.join(HERE, "compare.py"))     # same file name as the reconciliation's

FAILS = []
MIN = pd.Timedelta(minutes=1)
T0 = pd.Timestamp("2026-11-10 22:00")


def m(k):
    return T0 + k * MIN


def check(name, ok, info=""):
    print(("ok   " if ok else "FAIL ") + name + ("" if ok else f"  [{info}]"))
    if not ok:
        FAILS.append(name)


def bar(o, v=1.0):
    return dict(open=o, high=o + 0.5, low=o - 0.5, close=o + 0.1, volume=v)


# ------------------------------------------------------------------------------------------------ a small record
def small_record():
    """DOGE: trades bars m0 (3 trades), m1 (verified empty), m2 (not verified), m3 absent, m4 (2 trades).
    First-seen candles of m0, m2, m4; candle answers in fetch minutes m1, m2, m3, m5 (none in m4, so the
    first-seen candle of m3 has no answer). Final candles m-2 .. m5 at 100 + k."""
    tb = pd.DataFrame([dict(coin="DOGE", minute=m(0), n=3, verified=True, **bar(200)),
                       dict(coin="DOGE", minute=m(1), n=0, verified=True, open=np.nan, high=np.nan, low=np.nan,
                            close=np.nan, volume=0.0),
                       dict(coin="DOGE", minute=m(2), n=5, verified=False, **bar(202)),
                       dict(coin="DOGE", minute=m(4), n=2, verified=True, **bar(204))])
    cd = pd.DataFrame([dict(coin="DOGE", minute=m(k), seen=m(k + 1) + pd.Timedelta(seconds=7), rev=0, **bar(300 + k))
                       for k in (0, 2, 4)]
                      + [dict(coin="DOGE", minute=m(1), seen=m(3) + pd.Timedelta(seconds=7), rev=0, **bar(301))])
    cf = pd.DataFrame([dict(coin="DOGE", minute=m(k), seen=m(k) + pd.Timedelta(seconds=7),
                            cache="HIT" if k == 3 else "MISS", age=np.nan, newest=m(k - 1)) for k in (1, 2, 3, 5)])
    final = pd.DataFrame([bar(100 + k) for k in range(-2, 6)], index=pd.DatetimeIndex([m(k) for k in range(-2, 6)]))
    return tb, cd, cf, final


def test_row_assembly():
    tb, cd, cf, final = small_record()
    tbar, first, answers = build.split_record(tb, cd, cf, m(1), m(5))
    dec = pd.date_range(m(1), m(5), freq="min")
    nf = build.newest_frames("DOGE", dec, tbar, first, answers)
    sa, st = nf["A"][1], nf["T"][1]
    check("rule A sources of rows t-1 = m0..m4: first, answer without the minute, first, no answer, first",
          list(sa.values) == ["first", "first_absent", "first", "no_answer", "first"], list(sa.values))
    check("rules B/C sources: trades, verified empty, fall-back first-seen (not verified), fall-back with no answer "
          "(no trades row), trades",
          list(st.values) == ["trades", "empty", "fb_first", "fb_no_answer", "trades"], list(st.values))
    check("a first-seen sighting later than minute t is not first-seen (m1 was first seen in minute m3)",
          m(1) not in first["DOGE"].index)
    check("rule A rows: the first-seen candles of m0, m2, m4 only",
          list(nf["A"][0].index) == [m(0), m(2), m(4)] and list(nf["A"][0].open) == [300, 302, 304])
    check("rule T rows: trades m0, first-seen m2 (fall-back), trades m4",
          list(nf["T"][0].index) == [m(0), m(2), m(4)] and list(nf["T"][0].open) == [200, 302, 204],
          nf["T"][0])
    oldB, kinds = build.old_b_frame("DOGE", final, m(0), m(4), tbar)
    check("rule B older rows: final before the record, trades m0, none at m1 (verified empty), final m2 and m3 "
          "(no verified bar), trades m4",
          list(oldB.index) == [m(-2), m(-1), m(0), m(2), m(3), m(4)]
          and list(oldB.open) == [98, 99, 200, 102, 103, 204], oldB)
    check("record counts: 2 trades, 1 empty, 2 fall-backs", kinds == dict(trades=2, empty=1, fallback=2), kinds)

    # tables per pass, through the engine driver's own data structure
    fac._G["candles"] = {"DOGE": final}
    build._W["frames"] = {"DOGE": dict(oldB=oldB, newA=nf["A"][0], srcA=sa, newT=nf["T"][0], srcT=st)}
    build._W["ways"] = {"R": {}, "A": {"DOGE": "A"}, "B": {"DOGE": "B"}, "C": {"DOGE": "C"}}
    tab = lambda p, t: build.table_for(p, t)["DOGE"]  # noqa: E731
    check("pass R table = final candles through t-1", list(tab("R", m(5)).open) == [98, 99, 100, 101, 102, 103, 104])
    check("pass B at t=m5: older rows trades-kept, row m4 the trades bar",
          list(tab("B", m(5)).open) == [98, 99, 200, 102, 103, 204])
    check("pass B at t=m4: row m3 missing (fall-back with no candle answer: no row)",
          list(tab("B", m(4)).open) == [98, 99, 200, 102])
    check("pass B at t=m2: verified empty m1 has no row (no fall-back to its candle)",
          list(tab("B", m(2)).open) == [98, 99, 200])
    check("pass A at t=m3: final through m1, row m2 first-seen", list(tab("A", m(3)).open) == [98, 99, 100, 101, 302])
    check("pass A at t=m2: first-seen answer without m1: no row m1 (the engine carries the close forward)",
          list(tab("A", m(2)).open) == [98, 99, 100])
    check("pass C at t=m3: final through m1, row m2 the fall-back first-seen candle",
          list(tab("C", m(3)).open) == [98, 99, 100, 101, 302])
    check("pass C at t=m5: final through m3, row m4 the trades bar (older trades bars not kept)",
          list(tab("C", m(5)).open) == [98, 99, 100, 101, 102, 103, 204])
    build._W["ways"]["C18"] = {c: w for c, w in build.passes()["C18"].items() if c == "DOGE"}
    check("pass C18 (DOGE on way C): the same rows as pass C at every decision",
          all(tab("C18", m(k)).equals(tab("C", m(k))) for k in range(1, 6)))
    src = build.sources_table(dec, ["DOGE"], build._W["frames"], {"A": {"DOGE": "A"}, "B": {"DOGE": "B"}}, answers)
    a = src[src["pass"] == "A"].set_index("ts")
    check("inputs_ok False only where the first-seen answer is missing (t = m4)",
          list(a.index[~a.inputs_ok]) == [m(4)])
    check("answer_old: a MISS made in minute t is not old; t=m3 has no Age on a HIT (unknown age): old",
          a.at[m(1), "answer_old"] is False and a.at[m(3), "answer_old"] is True and pd.isna(a.at[m(2), "answer_old"]),
          a.answer_old.tolist())


# ------------------------------------------------------------------------------------------------ engine
def synth_candles(n_extra=12, seed=3):
    from bot.spot.engine import WINDOW_MIN
    rng = np.random.default_rng(seed)
    idx = pd.date_range(T0 - pd.Timedelta(minutes=WINDOW_MIN + 5), T0 + n_extra * MIN, freq="min")
    out = {}
    import json
    coins = json.load(open(os.path.join(ROOT, "bot", "v2", "model_meta.json")))["coins"]
    b = np.cumsum(rng.normal(0, 8e-4, len(idx)))
    for i, c in enumerate(["BTC"] + coins):
        x = np.log(10.0 + i) + 0.8 * b + np.cumsum(rng.normal(0, 1e-3, len(idx)))
        cl = np.exp(x)
        op = np.r_[cl[0], cl[:-1]]
        out[c] = pd.DataFrame(dict(open=op, high=np.maximum(op, cl) * 1.0005, low=np.minimum(op, cl) * 0.9995,
                                   close=cl, volume=rng.uniform(1, 5, len(idx))), index=idx)
    return out, coins


def test_engine():
    candles, coins = synth_candles()
    tmp = tempfile.mkdtemp(prefix="bs_test_")
    build.init_worker(candles, coins, tmp, {}, {"R": {}})
    t = m(8)
    ref = pd.DataFrame(fac.compute_at(t))                       # the reconciliation's own compute, unchanged
    got = pd.DataFrame(build.work(("R", t))).drop(columns="pass")
    check("pass R = the reconciliation's compute_at on the same table (every coin, every column)",
          ref.equals(got) and len(ref) == len(coins), (ref.head(2), got.head(2)))
    # a pass whose newest rows equal the final candles reproduces R exactly
    frames = {c: dict(oldB=df, newA=df.loc[m(-5):], newT=df.loc[m(-5):]) for c, df in candles.items()}
    ways = {"R": {}, "A": {c: "A" for c in build.TWELVE}, "B": {c: "B" for c in ["BTC"] + coins}}
    build.init_worker(candles, coins, tmp, frames, ways)
    for p in ("A", "B"):
        got = pd.DataFrame(build.work((p, t))).drop(columns="pass")
        check(f"pass {p} with first-seen / trades rows equal to the final candles = pass R",
              ref.equals(got), got.compare(ref) if len(got) == len(ref) else len(got))
    check("fac.table_at restored after a pass", fac.table_at is build._TABLE_AT)
    # cross-sectional: change only DOGE's row t-1; ETH's level stays, ETH's alts features move
    from edge import wick
    d2 = dict(frames)
    nd = candles["DOGE"].loc[m(-5):].copy()
    nd.loc[t - MIN, ["close", "low"]] *= 0.97
    d2["DOGE"] = dict(oldB=candles["DOGE"], newA=nd, newT=nd)
    build.init_worker(candles, coins, tmp, d2, {"R": {}, "X": {"DOGE": "A"}})
    eng = fac._G["eng"]
    pn = {}
    for p in ("R", "X"):
        eng.spot = build.table_for(p, t) if p == "X" else fac.table_at(t)
        idx, cf, vol = eng.arrays(t)
        pn[p] = wick.panel(cf, vol, coins, idx, k=eng.k, lookback=eng.lookback, coin_codes=eng.codes,
                           wbeta=eng.wbeta)
    e0, e1 = pn["R"]["ETH"].iloc[-1], pn["X"]["ETH"].iloc[-1]
    check("a coin's features depend on other coins' rows: ETH's alts_mean_z60 moves when only DOGE's row t-1 moves",
          e0["alts_mean_z60"] != e1["alts_mean_z60"], (e0["alts_mean_z60"], e1["alts_mean_z60"]))
    own = [f for f in wick.FEATS if f not in ("alts_mean_z60", "alts_below_2sd")] + ["level", "sig"]
    check("... and every other ETH feature, its level and sigma are unchanged",
          all((e0[f] == e1[f]) or (np.isnan(e0[f]) and np.isnan(e1[f])) for f in own),
          [f for f in own if e0[f] != e1[f]])


# ------------------------------------------------------------------------------------------------ compare
def table(rows):
    T = pd.DataFrame(rows)
    for k, v in dict(level=1.0, res_level=1.0, inputs_ok=True, valid=True, res_valid=True).items():
        if k not in T:
            T[k] = v
    return T


def test_arming():
    thr = 30.0
    g = table([dict(score=40, res_score=40), dict(score=40, res_score=20), dict(score=20, res_score=40),
               dict(score=20, res_score=20), dict(score=40, res_score=35), dict(score=np.nan, valid=False, res_score=31),
               dict(score=30.0, res_score=30.0001)])
    r = bc.arming(g, thr)
    check("arming: den = minutes where either is armed (6), num = exactly one (4)", r["den"] == 6 and r["num"] == 4, r)
    check("arming split: way only 1, research only 3 (an invalid way score is not armed; > thr strictly)",
          r["way_only"] == 1 and r["res_only"] == 3, r)


def clause_table():
    """Three day blocks; per coin and way the (misses, minutes both valid) of each day. A miss is |diff| = 2.0, a
    non-miss exactly 1.0 (the boundary: not a miss)."""
    start = pd.Timestamp("2026-11-11 02:00")
    plan = {"DOGE": {"C": [(2, 10), (2, 10), (0, 10)], "A": [(1, 10), (1, 10), (1, 10)]},   # period and 2 days
            "LINK": {"C": [(2, 10), (1, 10), (1, 10)], "A": [(1, 10), (1, 10), (1, 10)]},   # period, only 1 day
            "BCH": {"C": [(2, 20), (2, 20), (2, 20)], "A": [(1, 10), (1, 10), (1, 10)]},    # equal shares
            "SUI": {"C": [(2, 10), (2, 10), (2, 10)], "A": [(1, 10), (1, 10), (0, 0)]},     # day 3: A has none
            "XLM": {"C": [(2, 10), (2, 10), (2, 10)], "A": [(0, 0), (0, 0), (0, 0)]}}       # A has no minute
    rows = []
    for c, ways in plan.items():
        for w, per_day in ways.items():
            for d, (miss, n) in enumerate(per_day):
                base = start + d * pd.Timedelta(hours=24)
                for i in range(n):
                    rows.append(dict(ts=base + i * MIN, coin=c, **{"pass": w}, way=w,
                                     score=40.0 + (2.0 if i < miss else 1.0), res_score=40.0))
    return table(rows), start


def test_clause():
    sh = bc.strictly_higher
    check("equal shares are not strictly higher (2/10 vs 1/5)", sh(dict(num=2, den=10), dict(num=1, den=5)) is False)
    check("strictly higher on counts (3/10 vs 1/5)", sh(dict(num=3, den=10), dict(num=1, den=5)) is True)
    check("a zero denominator is not higher (None)", sh(dict(num=1, den=5), dict(num=0, den=0)) is None)
    T, start = clause_table()
    P, days_n, counts = bc.compute(T, 30.0, {}, start)
    r = P[(P.coin == "DOGE") & (P.way == "C") & (P.day == 3)].iloc[0]
    check("score-miss: exactly 1.0 is not a miss (DOGE C day 3: 0 of 10)", r.miss == 0 and r.score_n == 10, r.to_dict())
    r = P[(P.coin == "DOGE") & (P.way == "C") & (P.day == "all")].iloc[0]
    check("score-miss share over the period: DOGE C 4 of 30", r.miss == 4 and r.score_n == 30 and
          abs(r.miss_share - 4 / 30) < 1e-15, r.to_dict())
    tw = P[(P.coin == "twelve") & (P.way == "C") & (P.day == "all")].iloc[0]
    check("score-miss for the twelve together: pooled counts", tw.miss == 4 + 4 + 6 + 6 + 6 and tw.score_n == 30 + 30 + 60 + 30 + 30,
          tw.to_dict())
    cl = bc.stays_on_candles(P, {"at_least_90pct": True})
    v = {c: cl["coins"][c]["value"] for c in ["DOGE", "LINK", "BCH", "SUI", "XLM", "PEPE"]}
    check("clause applied when the B check passes", cl["applied"] is True)
    check("clause: higher over the period and on two days -> true (DOGE)", v["DOGE"] is True, cl["coins"]["DOGE"])
    check("clause: higher over the period but on one day only -> false (LINK)", v["LINK"] is False
          and cl["coins"]["LINK"]["period_higher"] is True and cl["coins"]["LINK"]["days_higher"] == 1)
    check("clause: equal shares are not higher -> false (BCH)", v["BCH"] is False
          and cl["coins"]["BCH"]["period_higher"] is False)
    check("clause: a day with A's denominator 0 does not count, two other days do -> true (SUI)", v["SUI"] is True
          and cl["coins"]["SUI"]["by_day"][3] is None and cl["coins"]["SUI"]["days_higher"] == 2)
    check("clause: a period with a zero denominator is not higher -> false (XLM; PEPE has no rows)",
          v["XLM"] is False and cl["coins"]["XLM"]["period_higher"] is None and v["PEPE"] is False)
    for chk, name in ((None, "no --log"), ({"at_least_90pct": False}, "the B check under 90%"),
                      ({"at_least_90pct": None}, "the B check with no bids")):
        cl = bc.stays_on_candles(P, chk)
        check(f"clause not applied with {name}: no value for any coin, reason given",
              cl["applied"] is False and all(x["value"] is None for x in cl["coins"].values())
              and cl["why"].startswith("not applied"), cl["why"])
    check("day blocks counted from the start: three blocks of the period", sorted(days_n) == [1, 2, 3], days_n)


def test_days():
    s = pd.Timestamp("2026-11-11 02:00")
    ts = [s, s + pd.Timedelta(hours=23, minutes=59), s + pd.Timedelta(hours=24), pd.Timestamp("2026-11-14 01:59")]
    check("day blocks: 02:00 and 01:59 next day in block 1, 02:00 next day block 2, Nov 14 01:59 block 3",
          list(bc.day_block(ts, s)) == [1, 1, 2, 3], list(bc.day_block(ts, s)))


def test_errors():
    g = table([dict(coin="DOGE", score=40, res_score=39, level=0.10000, res_level=0.100004),     # within a tick
               dict(coin="DOGE", score=10, res_score=14, level=0.10006, res_level=0.10000),      # 6 ticks: 6 bp
               dict(coin="DOGE", score=30, res_score=30, level=0.10004, res_level=0.10000),      # 4 ticks: 4 bp
               dict(coin="DOGE", score=np.nan, valid=False, res_score=30, level=0.2, res_level=0.1)])
    e = bc.errors(g, {"DOGE": 1e-5})
    check("score error over minutes both valid: median 1, p90 3.4", e["score_n"] == 3 and e["score_med"] == 1.0
          and abs(e["score_p90"] - 3.4) < 1e-12, e)
    check("level error: within a tick = 0; 4 bp is not more than 5; 6 bp is; invalid minute left out",
          e["level_n"] == 3 and e["level_gt5"] == 1, e)


def test_log_check():
    start, end = pd.Timestamp("2026-11-11 02:00"), pd.Timestamp("2026-11-11 02:10")
    T = table([dict(ts=start + k * MIN, coin=c, **{"pass": p}, score=s, valid=np.isfinite(s))
               for k, c, p, s in [(1, "ETH", "A", 40.0), (2, "ETH", "A", 40.0), (3, "LTC", "A", 35.0),
                                  (4, "DOGE", "A", 50.0), (5, "DOGE", "A", np.nan), (1, "ETH", "B", 99.0)]])
    ev = [dict(kind="arm", ts=str(start + 1 * MIN + pd.Timedelta(seconds=7)), coin="ETH", pred=40.5),     # 0.5: within
          dict(kind="arm", ts=str(start + 2 * MIN), coin="ETH", pred=40.6),                              # 0.6: not
          dict(kind="arm", ts=str(start + 3 * MIN), coin="LTC", pred=34.6),                              # within
          dict(kind="arm", ts=str(start + 4 * MIN), coin="DOGE", pred=50.0),
          dict(kind="arm", ts=str(start + 5 * MIN), coin="DOGE", pred=31.0),                             # no emulation
          dict(kind="arm", ts=str(start - MIN), coin="ETH", pred=1.0),                                   # before
          dict(kind="arm", ts=str(end + MIN), coin="ETH", pred=1.0),                                     # after
          dict(kind="heartbeat", ts=str(start + 1 * MIN))]
    r, rows = bc.log_check(ev, T, bc.CHECK_B, start, end)
    check("check B: 3 bids in the period, 2 within 0.5 (exactly 0.5 counts), pass A used, outside bids ignored",
          r["n"] == 3 and r["within"] == 2 and r["no_valid_emulation"] == 0, r)
    check("check B: 2 of 3 is under 90%", r["at_least_90pct"] is False)
    r2, _ = bc.log_check(ev, T, bc.TWELVE, start, end)
    check("check A on the twelve: 2 bids, 1 within, 1 without a valid emulated score (counted, not within)",
          r2["n"] == 2 and r2["within"] == 1 and r2["no_valid_emulation"] == 1, r2)
    r3, _ = bc.log_check([dict(kind="arm", ts=str(start + MIN), coin="ETH", pred=40.0)] * 9
                         + [dict(kind="arm", ts=str(start + 2 * MIN), coin="ETH", pred=45.0)], T, ["ETH"], start, end)
    check("exactly 90% within passes the B check (9 of 10)", r3["at_least_90pct"] is True and r3["within"] == 9, r3)


def test_passes():
    P = build.passes()
    check("pass A is the third book: twelve on A, BTC ETH SOL XRP LTC ZEC on B",
          all(P["A"][c] == "A" for c in build.TWELVE) and all(P["A"][c] == "B" for c in
                                                             ["BTC", "ETH", "SOL", "XRP", "LTC", "ZEC"]))
    check("LA / LC: the twelve as the third book (A), LTC and ZEC on A / C",
          all(P["LA"][c] == "A" and P["LC"][c] == "A" for c in build.TWELVE)
          and P["LA"]["LTC"] == "A" and P["LC"]["ZEC"] == "C" and P["LC"]["ETH"] == "B")
    check("C18: all 18 coins on way C (the fourth book), canonical for every traded coin",
          set(P["C18"]) == set(["BTC"] + build.TWELVE + build.REPORTED + ["ETH", "SOL", "XRP"])
          and all(v == "C" for v in P["C18"].values())
          and all(build.canonical_pass(c, "C18") == "C18" == bc.canonical_pass(c, "C18")
                  for c in build.TWELVE + build.REPORTED + ["ETH", "SOL", "XRP"]))
    check("canonical passes: DOGE B -> B; LTC A -> LA, B -> A, C -> LC",
          build.canonical_pass("DOGE", "B") == "B" and [build.canonical_pass("LTC", w) for w in "ABC"] == ["LA", "A", "LC"]
          and all(bc.canonical_pass(c, w) == build.canonical_pass(c, w) for c in build.TWELVE + build.REPORTED for w in "ABC"))


def main():
    test_passes()
    test_row_assembly()
    test_arming()
    test_clause()
    test_days()
    test_errors()
    test_log_check()
    test_engine()
    if FAILS:
        print(f"{len(FAILS)} FAILED: {FAILS}")
        sys.exit(1)
    print("test_bar_source: all passed")


if __name__ == "__main__":
    main()
