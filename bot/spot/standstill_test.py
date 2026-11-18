#!/usr/bin/env python3
"""Test of the setting "standstill_candles" (bot/spot/README.md, "Standstill of the trades list"). No network, no
keys, no real clock: the fake clock market of candle_pass_test.py (a candle request is answered as the venue would
answer it then: made at the request's time, no row for the minute open then), three coins (BTC, ETH, SOL), trades
for all of them, the candle pass at second 45, the stale guard on.

Each case: the candle pass for minute T runs, then the step of T + 1 (closed minute T) with the trades answers the
case sets. Checks, with the switch on and (as the comparison) off:
  - BTC verified empty, its candle traded: the frozen path; the marks for T taken away; on-demand requests for BTC
    and exactly the verified-empty coins the step had left out; tb_frozen 1; the rows judged as candle rows;
  - BTC verified empty, its candle without a row for T: stale as today (the mark put back, stale_input, the same
    log as with the switch off), one BTC request and nothing more;
  - BTC verified empty when the step itself had asked BTC's candle (no candle pass for BTC): the row already there
    is used, no second BTC request, the other coins handled the same;
  - a coin whose on-demand answer is old (made before T ended): skipped for the minute (_skip_old), the others not;
  - a refusal or a rate limit in the trades pass: no on-demand request, stale as today;
  - a coin other than BTC verified empty with BTC built: nothing happens (no request, no counter);
  - the switch off: today's behaviour in every one of these (no new request or counter, the log as without the key);
  - inert without candles_at_s or with newest_bar "candles": no warning, no event, no request, as with it off;
  - a value that is not true or false stops the start in every mode;
  - the key is in INPUT_KEYS and taken from the release's config by release_inputs like candles_at_s.

Usage: python bot/spot/standstill_test.py
"""
import json
import os
import re
import shutil
import sys
import tempfile

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
from bot import market as BM  # noqa: E402
from bot.spot import candle_pass_test as CP  # noqa: E402
from bot.spot import engine as E  # noqa: E402
from bot.spot import newest_bar_test as NB  # noqa: E402
from bot.spot import release_inputs as RI  # noqa: E402

MIN = pd.Timedelta(minutes=1)
T = CP.T                                  # the closed minute of the step tested (the step is T + 1)
FAILS = []
NPASS = [0]
HEX = re.compile(r"[0-9a-f]{12,}")
NEWC = ("tb_frozen", "pre_ondemand", "step_candles")


def check(name, ok, extra=""):
    print(("PASS  " if ok else "FAIL  ") + name + (f"  {extra}" if extra else ""), flush=True)
    if ok:
        NPASS[0] += 1
    else:
        FAILS.append(name)


ABSENT = "<absent>"


def engine(sw, at=45, newest_bar="trades"):
    """sw: the value of standstill_candles, or ABSENT (None here means the key holds null). The fake clock market of
    candle_pass_test.py."""
    cfg = dict(NB.CFG, newest_bar=newest_bar, stale_guard=True, trades_rows="candle_after")
    cfg.pop("standstill_candles", None)
    if sw is not ABSENT:
        cfg["standstill_candles"] = sw
    if at is not None:
        cfg["candles_at_s"] = at
    sd = tempfile.mkdtemp(prefix="standstill_")
    F = [CP.ep(T) + 6.0]
    eng = E.Engine(mode="paper", cfg=cfg, state_dir=sd, market=None, broker=E.PaperBroker(0.5),
                   clock=lambda: pd.Timestamp(F[0], unit="s"), echo=False)
    eng.coins = ["ETH", "SOL"]
    eng.tradable = list(eng.coins)
    eng.market = CP.ClockMarket(["BTC"] + eng.coins, F)
    eng.refresh_adv = lambda t: None
    eng._timer = lambda: NB.CLOCK[0]
    eng.update_spot(T)                                      # start-up: backfill and the trades pass of T - 1
    if newest_bar == "trades":
        eng.trades_pass(T - MIN)
    eng.counts = {}
    return eng, sd, F


def events(sd):
    return [HEX.sub("<id>", x.strip()) for x in open(os.path.join(sd, "events.jsonl"))
            if '"kind": "heartbeat"' not in x] if os.path.exists(os.path.join(sd, "events.jsonl")) else []


def kinds(sd, k):
    return [x for x in events(sd) if f'"kind": "{k}"' in x]


def scenario(sw, tb=(), no_btc_candle=False, btc_in_step=False, old=(), at=45, newest_bar="trades", start=False):
    """The step of T + 1 after the candle pass for T. tb: {coin: trades answer for T} (None: verified empty, an
    exception: raised). no_btc_candle: no BTC candle row for T in any answer. btc_in_step: the candle pass did not
    cover BTC (the step asks BTC's candle itself). old: coins whose candle answers in the step are made before T
    ended. Returns (engine, state folder, the step's candle requests as (coin, end))."""
    eng, sd, F = engine(sw, at=at, newest_bar=newest_bar)
    mk = eng.market
    if start:
        F[0] = CP.ep(T) + 10.0
        eng.start()
        eng.counts = {}
    for c, v in dict(tb).items():
        mk.tb[(c, T)] = v
    if no_btc_candle:
        mk.first[("BTC", T)] = None                          # every answer ending at T + 1 leaves T out
    if eng.candles_at_s is not None:
        F[0] = CP.ep(T) + 45
        eng.candle_pass(T)
        if btc_in_step:
            eng._cpass.pop("BTC", None)
        eng.counts = {}
    real = mk.spot_candles

    def spot_candles(coin, start, end, **kw):
        out = real(coin, start, end, **kw)
        if coin in old and pd.Timestamp(end) == T + MIN:
            mk.candle_meta[coin]["gen"] = T + pd.Timedelta(seconds=30)   # made before T ended
        return out
    mk.spot_candles = spot_candles
    F[0] = CP.ep(T + MIN) + 6.0
    n = len(mk.req)
    eng.step(T + MIN)
    rq = [(r["coin"], r["end"]) for r in mk.req[n:]]
    return eng, sd, rq


def mark(eng, c):
    return eng._prov.get(c, {}).get(T)


def same_as_off(tag, on_sd, **kw):
    """The same case with the switch off and with the key absent: today's behaviour, the same log either way."""
    off, sd0, rq0 = scenario(False, **kw)
    ab, sd1, rq1 = scenario(ABSENT, **kw)
    check(f"{tag}, switch off: no new counter, the log and the requests as without the key",
          not set(NEWC[:2]) & set(off.counts) and events(sd0) == events(sd1) and rq0 == rq1,
          f"{off.counts} {rq0} {rq1}")
    for d in (sd0, sd1):
        shutil.rmtree(d, ignore_errors=True)
    return off, rq0, events(on_sd)


def frozen():
    eng, sd, rq = scenario(True, tb={"BTC": None, "ETH": None})
    check("frozen: on-demand requests for BTC and the verified-empty coin the step left out (ETH), nothing for SOL",
          rq == [("BTC", T + MIN), ("ETH", T + MIN)], str(rq))
    check("frozen: tb_frozen 1, pre_ondemand 2, step_candles 2",
          eng.counts.get("tb_frozen") == 1 and eng.counts.get("pre_ondemand") == 2
          and eng.counts.get("step_candles") == 2, str(eng.counts))
    check("frozen: the marks for T taken away (BTC and ETH rows are candle rows); SOL's row still trades-built",
          not mark(eng, "BTC")[1] and not mark(eng, "ETH")[1] and mark(eng, "SOL")[1], str(eng._prov.get("BTC")))
    fin = eng.market.final
    check("frozen: BTC's and ETH's rows for T are the candles' rows",
          all(T in eng.spot[c].index and eng.spot[c].loc[T, "close"] == fin[c].loc[T, "close"]
              for c in ("BTC", "ETH")))
    check("frozen: not stale, no coin skipped, no stale_input", not eng._skip_old and not kinds(sd, "stale_input")
          and "btc_stale" not in eng.counts, f"{eng._skip_old} {eng.counts}")
    off, rq0, _ = same_as_off("frozen", sd, tb={"BTC": None, "ETH": None})
    check("frozen, switch off: no candle request in the step, BTC stale (stale_input), as today",
          rq0 == [] and off.counts.get("btc_stale") == 1 and mark(off, "BTC") == (None, True), f"{rq0} {off.counts}")
    shutil.rmtree(sd)


def btc_no_row():
    eng, sd, rq = scenario(True, tb={"BTC": None, "ETH": None}, no_btc_candle=True)
    off, rq0, ev = same_as_off("BTC without a candle row", sd, tb={"BTC": None, "ETH": None}, no_btc_candle=True)
    check("BTC without a candle row: one BTC request, nothing for the other coins, tb_frozen absent",
          rq == [("BTC", T + MIN)] and "tb_frozen" not in eng.counts and eng.counts.get("pre_ondemand") == 1, str(rq))
    check("BTC without a candle row: the marks put back (BTC and ETH verified empty), BTC stale, stale_input",
          mark(eng, "BTC") == (None, True) and mark(eng, "ETH") == (None, True) and eng.counts.get("btc_stale") == 1
          and len(kinds(sd, "stale_input")) == 1, f"{mark(eng, 'BTC')} {eng.counts}")
    _, sd0, _ = scenario(False, tb={"BTC": None, "ETH": None}, no_btc_candle=True)
    check("BTC without a candle row: the log, the tables and the marks for T as with the switch off",
          ev == events(sd0) and all(eng.spot[c].equals(off.spot[c]) for c in ("BTC", "ETH", "SOL"))
          and all(mark(eng, c) == mark(off, c) for c in ("BTC", "ETH", "SOL")))
    shutil.rmtree(sd0)
    shutil.rmtree(sd)


def btc_in_step():
    eng, sd, rq = scenario(True, tb={"BTC": None, "ETH": None}, btc_in_step=True)
    check("BTC asked by the step: its own request first (end T + 1), no second BTC request, ETH on demand",
          rq == [("BTC", T + MIN), ("ETH", T + MIN)], str(rq))
    check("BTC asked by the step: pre_missing 1 (the step's own), pre_ondemand 1 (ETH only), tb_frozen 1",
          eng.counts.get("pre_missing") == 1 and eng.counts.get("pre_ondemand") == 1
          and eng.counts.get("tb_frozen") == 1 and eng.counts.get("step_candles") == 2, str(eng.counts))
    g = eng.market.req[-2]["at"]                             # the step's BTC request
    check("BTC asked by the step: BTC's row for T is judged as that answer's candle row (its answer time back)",
          mark(eng, "BTC") == (pd.Timestamp(g, unit="s"), False) and not mark(eng, "ETH")[1]
          and not eng._skip_old and not kinds(sd, "stale_input"), f"{mark(eng, 'BTC')} {eng._skip_old}")
    off, rq0, _ = same_as_off("BTC asked by the step", sd, tb={"BTC": None, "ETH": None}, btc_in_step=True)
    check("BTC asked by the step, switch off: only the step's BTC request, BTC's mark stays, not stale (as today)",
          rq0 == [("BTC", T + MIN)] and mark(off, "BTC") == (None, True) and "btc_stale" not in off.counts,
          f"{rq0} {off.counts}")
    shutil.rmtree(sd)
    # the step's own BTC answer made before T ended: judged by its age once the mark is replaced (stale)
    eng, sd, rq = scenario(True, tb={"BTC": None, "ETH": None}, btc_in_step=True, old=("BTC",))
    check("BTC asked by the step, its answer made before T ended: stale (judged by the answer's age), "
          "with the switch off not stale", kinds(sd, "stale_input") != [] and rq == [("BTC", T + MIN),
                                                                               ("ETH", T + MIN)], str(rq))
    off, _, _ = same_as_off("BTC asked by the step, old answer", sd, tb={"BTC": None, "ETH": None},
                            btc_in_step=True, old=("BTC",))
    check("BTC asked by the step, old answer, switch off: not stale (the mark passes, as today)",
          "btc_stale" not in off.counts and mark(off, "BTC") == (None, True), str(off.counts))
    shutil.rmtree(sd)


def old_answer():
    eng, sd, rq = scenario(True, tb={"BTC": None, "ETH": None, "SOL": None}, old=("SOL",))
    check("old on-demand answer: BTC, ETH and SOL asked on demand, tb_frozen 1",
          rq == [("BTC", T + MIN), ("ETH", T + MIN), ("SOL", T + MIN)] and eng.counts.get("tb_frozen") == 1, str(rq))
    check("old on-demand answer: SOL skipped for the minute (_skip_old), ETH not; no stale_input",
          eng._skip_old == {"SOL"} and eng.counts.get("skip_old") == 1 and not kinds(sd, "stale_input"),
          f"{eng._skip_old} {eng.counts}")
    same_as_off("old on-demand answer", sd, tb={"BTC": None, "ETH": None, "SOL": None}, old=("SOL",))
    shutil.rmtree(sd)


def stopped():
    for tag, exc in (("rate limit", BM.Limited("HTTP 429")), ("refusal", BM.Refused("HTTP 403"))):
        eng, sd, rq = scenario(True, tb={"BTC": None, "ETH": exc})
        off, rq0, ev = same_as_off(f"{tag} in the trades pass", sd, tb={"BTC": None, "ETH": exc})
        check(f"{tag} in the trades pass: no on-demand request, no new counter, BTC's mark stays, stale",
              rq == [] and not set(NEWC[:2]) & set(eng.counts) and not eng.counts.get("step_candles") and mark(eng, "BTC") == (None, True)
              and len(kinds(sd, "stale_input")) == 1, f"{rq} {eng.counts}")
        _, sd0, _ = scenario(False, tb={"BTC": None, "ETH": exc})
        check(f"{tag} in the trades pass: the log as with the switch off", ev == events(sd0))
        shutil.rmtree(sd0)
        shutil.rmtree(sd)


def other_coin():
    eng, sd, rq = scenario(True, tb={"ETH": None})
    check("another coin verified empty, BTC built: no request, no counter, ETH's mark stays",
          rq == [] and not set(NEWC[:2]) & set(eng.counts) and not eng.counts.get("step_candles") and mark(eng, "ETH") == (None, True), f"{rq} {eng.counts}")
    off, rq0, ev = same_as_off("another coin verified empty", sd, tb={"ETH": None})
    _, sd0, _ = scenario(False, tb={"ETH": None})
    check("another coin verified empty: the log as with the switch off", ev == events(sd0))
    shutil.rmtree(sd0)
    shutil.rmtree(sd)


def inert():
    for tag, kw in (("without candles_at_s", dict(at=None)), ('newest_bar "candles"', dict(at=None,
                                                                                            newest_bar="candles")),
                    ('newest_bar "candles" with candles_at_s', dict(at=45, newest_bar="candles"))):
        eng, sd, rq = scenario(True, tb={"BTC": None, "ETH": None}, start=True, **kw)
        ab, sd1, rq1 = scenario(ABSENT, tb={"BTC": None, "ETH": None}, start=True, **kw)
        ss = [x for x in events(sd) if "standstill" in x]
        check(f"inert ({tag}): standstill off in the engine, no event naming it, no warning beyond the key-absent run",
              eng.standstill is False and not ss and kinds(sd, "warning") == kinds(sd1, "warning"),
              str(kinds(sd, "warning")))
        check(f"inert ({tag}): the requests, counters and log as with the key absent",
              rq == rq1 and eng.counts == ab.counts and events(sd) == events(sd1) and "tb_frozen" not in eng.counts,
              f"{rq} {rq1} {eng.counts}")
        shutil.rmtree(sd)
        shutil.rmtree(sd1)


def bad_values():
    for nb, at in (("trades", 45), ("trades", None), ("candles", None), ("candles", 45)):
        for v in ("true", 1, 0, None, "false"):
            try:
                eng, sd, F = engine(v, at=at, newest_bar=nb)
                shutil.rmtree(sd)
                ok = False
            except ValueError as e:
                ok = "standstill_candles" in str(e)
            check(f"bad value {v!r} (newest_bar {nb}, candles_at_s {at}): the start stops (ValueError)", ok)
    for nb, at in (("trades", 45), ("trades", None), ("candles", None)):
        for v in (True, False):
            eng, sd, F = engine(v, at=at, newest_bar=nb)
            check(f"value {v} (newest_bar {nb}, candles_at_s {at}): builds; on only with trades and candles_at_s",
                  eng.standstill is (v and nb == "trades" and at is not None))
            shutil.rmtree(sd)


def release_key():
    check("INPUT_KEYS holds standstill_candles, right after candles_at_s",
          "standstill_candles" in RI.INPUT_KEYS
          and RI.INPUT_KEYS.index("standstill_candles") == RI.INPUT_KEYS.index("candles_at_s") + 1)
    base = json.load(open(os.path.join(HERE, "config.json")))
    check("config.json sets standstill_candles true, with candles_at_s and newest_bar trades",
          base.get("standstill_candles") is True and base.get("candles_at_s") is not None
          and base.get("newest_bar") == "trades")
    live = {"capital": 1000.0}
    for k, v in (("candles_at_s", 45), ("standstill_candles", True)):
        new, notes = RI.apply(live, {k: v})
        new2, notes2 = RI.apply(dict(live, **{k: "x"}), {k: v})
        new3, notes3 = RI.apply(dict(live, **{k: v}), {})
        check(f"release_inputs: {k} taken from the release (added; a different live value replaced and noted; "
              "dropped and noted when the release lacks it)",
              new[k] == v and not notes and new2[k] == v and len(notes2) == 1 and k in notes2[0]
              and k not in new3 and len(notes3) == 1 and k in notes3[0], f"{notes2} {notes3}")
    new, notes = RI.apply(dict(live, inputs_local=True, standstill_candles=False), {"standstill_candles": True})
    check("release_inputs: inputs_local keeps the live file's own value", new["standstill_candles"] is False)


def main():
    E.WINDOW_MIN = 30
    try:
        frozen()
        btc_no_row()
        btc_in_step()
        old_answer()
        stopped()
        other_coin()
        inert()
        bad_values()
        release_key()
    finally:
        E.WINDOW_MIN = 11 * 1440
    print(f"standstill_test: {NPASS[0]} passed, {len(FAILS)} failed")
    print("STANDSTILL TEST " + ("FAILED: " + ", ".join(FAILS) if FAILS else "PASSED"))
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
