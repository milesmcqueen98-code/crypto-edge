#!/usr/bin/env python3
"""Live-path simulation on the release inputs, compared line for line with the candle run. No network, no keys.

Runs bot/spot/live_sim_test.py on the same window, in one process, against the same fake exchange set-up:
  A  candle mode, as release 2 tested it;
  B  the input settings of --inputs (default bot/spot/config.json, taken the way the live bot takes them) from the
     start, with a trades feed made from the same candles: every trades bar equals its candle, no answer is old, so a
     trades row that the venue's candle replaces afterwards ("trades_rows": "candle_after") is not changed by it;
  C1 candle mode until --switch (default one hour after the start), then a fresh process on B's inputs on the same
     state folder (a VM that skipped release 3, at wickctl update);
  C2 release 3's inputs until --switch (trades kept for BTC, ETH, SOL, XRP and ZEC, stale guard on; written out
     below), then a fresh process on B's inputs on the same state folder (the main paper book, and a VM that took
     release 3);
  D  only without --death, and only when the inputs have "trades_rows": "candle_after": B's inputs with a feed in
     which some trades bars differ from their candles (every 37th traded minute of ETH and SOL has a trades close
     three ticks above the candle's, and one traded minute of XRP has a trades bar but no candle in any answer);
  E  B's inputs with the setting "candles_at_s" the other way round: 45 when the inputs do not set it, absent when
     they do (the candle pass between steps, bot/spot/README.md);
  F  only without --death: B's inputs with release 3's five coins on the trades list, without and with the setting
     (for the modelled clock below).
Checks: every run passes live_sim_test's own checks; B, C1, C2 and D asked the trades feed; the event log of B equals
A's line for line, heartbeats aside, with order ids masked (they are random), and its heartbeats equal A's apart
from the counters and step timing; the entries and exits of C1 and C2 equal A's, and both kept their open ladders
across the switch. With "candle_after": B's candle replaced trades rows, none of them differed and none was dropped.
D: after the run the engine's table holds the candle's values for every altered minute at least three minutes old,
the candle-less minute has no row, and tb_replaced_diff and tb_dropped count exactly the altered and candle-less
minutes the feed handed out. D need not equal A. E and F: the same checks as B (their decisions equal A's, so
the setting changes no decision), and in the runs with the setting no candle request for a coin built from trades
in a step whose minute before had a candle pass. On a difference it prints the first differing line and adjusts
nothing.
Modelled clock (a model, not a measurement): for B, E and F, the second after the minute at which each step's data
part would end if it started at 6 s and its requests ran one after another at a runner's medians today: 0.19 s per
candle request, 0.58 s for BTC's trades request, 0.15 s for every other coin's (the fake feed records each request;
the cash request and the day's volume requests are left out). Printed as the median and the largest over the steps,
with the median number of candle and trades requests per step.

Usage: python bot/spot/live_sim_inputs_test.py "2025-10-10 20:00" "2025-10-11 02:00" "--death=2025-10-10 21:10"
       [--inputs=bot/spot/config.json] [--switch=2025-10-10 21:00]
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
from bot.spot import live_sim_test as L  # noqa: E402
from bot.spot import release_inputs as RI  # noqa: E402

FAILS = []
HEX = re.compile(r"[0-9a-f]{12,}")
COLS = ["open", "high", "low", "close", "volume"]
# release 3's input settings (bot/spot/config.json on main at release 3, commit 39f7c56a), written out by hand so the
# test needs no git: trades kept for good (no "trades_rows"), five listed coins, stale guard on
RELEASE3 = {"newest_bar": "trades", "stale_guard": True, "trades_coins": ["BTC", "ETH", "SOL", "XRP", "ZEC"]}
COUNTERS = ("tb_built", "tb_replaced", "tb_replaced_diff", "tb_dropped", "tb_pending", "btc_stale", "skip_old",
            "pre_fetched", "pre_missing", "pre_ondemand", "step_candles")
AT_S = 45                                                  # E and F: the candle pass at second 45
MODEL = {"candles": 0.19, "BTC": 0.58, "trades": 0.15, "start": 6.0}   # seconds; a runner's medians today


def check(name, ok, extra=""):
    print(("PASS  " if ok else "FAIL  ") + name + (f"  {extra}" if extra else ""), flush=True)
    if not ok:
        FAILS.append(name)


def lines(sd):
    """The event log without heartbeats, order ids masked."""
    out = []
    for x in open(os.path.join(sd, "events.jsonl")):
        e = json.loads(x)
        if e["kind"] != "heartbeat":
            out.append(HEX.sub("<id>", x.strip()))
    return out


def first_diff(a, b):
    for i, (x, y) in enumerate(zip(a, b)):
        if x != y:
            return i, x, y
    return (min(len(a), len(b)), a[len(b)] if len(a) > len(b) else None, b[len(a)] if len(b) > len(a) else None) \
        if len(a) != len(b) else None


def compare(tag, a, b):
    d = first_diff(a, b)
    check(f"{tag}: every log line equals the candle run's (heartbeats aside, order ids masked)", d is None,
          f"{len(b)} vs {len(a)} lines")
    if d is not None:
        print(f"  first difference at line {d[0]}:\n    candle run: {d[1]}\n    {tag}:        {d[2]}", flush=True)


def heartbeats(sd):
    return [json.loads(x) for x in open(os.path.join(sd, "events.jsonl")) if '"kind": "heartbeat"' in x]


def totals(sd):
    """Counters summed over the heartbeats; fallbacks (every tb_fb_ counter) as one number."""
    hb = heartbeats(sd)
    t = {k: sum(h.get("counts", {}).get(k, 0) for h in hb) for k in COUNTERS}
    t["fallbacks"] = sum(v for h in hb for k, v in h.get("counts", {}).items() if k.startswith("tb_fb"))
    return len(hb), t


def differ(start, end):
    """Case D's feed: made-up differences between the trades list and the venue's candles."""
    t0, t1 = pd.Timestamp(start), pd.Timestamp(end)

    def setup(mkt):
        for c in ("ETH", "SOL"):
            d, tick = mkt.D[c], mkt.ticks[c]
            ms = [m for m in d.index[(d.index >= t0) & (d.index < t1)] if d.loc[m, "volume"] > 0]
            for m in ms[::37]:                             # every 37th traded minute: the close three ticks above
                b = {k: float(d.loc[m, k]) for k in COLS}
                b["close"] += 3 * tick
                b["high"] = max(b["high"], b["close"])
                mkt.alter[(c, m)] = b
        d = mkt.D["XRP"]
        ms = [m for m in d.index[(d.index >= t0) & (d.index < t1)] if d.loc[m, "volume"] > 0]
        mkt.no_candle.add(("XRP", ms[100]))                # traded, but no candle in any answer
    return setup


def case_d(start, end, inputs):
    print(f"\n=== D: inputs of {inputs} from the start; trades bars that differ from their candles", flush=True)
    sdD, okD = L.main(start, end, inputs=inputs, feed=differ(start, end))
    eng, mkt = L.LAST["eng"], L.LAST["mkt"]
    last = pd.Timestamp(eng.state["last_minute"])           # the last step; rows are held through last - 1
    old = sorted(k for k in mkt.alter if k[1] <= last - pd.Timedelta(minutes=4))
    bad = [k for k in old if k[1] not in eng.spot[k[0]].index or
           [float(eng.spot[k[0]].loc[k[1], x]) for x in COLS] != [float(mkt.D[k[0]].loc[k[1], x]) for x in COLS]]
    hb = heartbeats(sdD)
    cnt = {k: sum(h.get("counts", {}).get(k, 0) for h in hb) + eng.counts.get(k, 0)
           for k in ("tb_replaced", "tb_replaced_diff", "tb_dropped", "tb_pending")}
    served_alt = sorted(k for k in mkt.served if k in mkt.alter)
    served_gone = sorted(k for k in mkt.served if k in mkt.no_candle)
    gone = sorted(mkt.no_candle)
    print(f"  D: last step {last}; {len(mkt.alter)} altered minutes ({len(served_alt)} handed out as trades bars, "
          f"{len(old)} at least three minutes old at the end); candle-less minute {gone} (handed out: "
          f"{len(served_gone)}); counters over the run (heartbeats and the minutes after the last one): {cnt}",
          flush=True)
    check("D: live-path checks pass", okD)
    check("D: every altered minute was handed out as a trades bar", len(served_alt) == len(mkt.alter) > 0,
          f"{len(served_alt)} of {len(mkt.alter)}")
    check("D: the engine's table holds the candle's values for every altered minute at least three minutes old",
          not bad and len(old) > 0, str(bad[:5]))
    check("D: the candle-less minute was dropped (no row)", served_gone == gone and all(
        m not in eng.spot[c].index for c, m in gone), str(gone))
    check("D: tb_replaced_diff counts exactly the altered minutes handed out",
          cnt["tb_replaced_diff"] == len(served_alt), f"{cnt['tb_replaced_diff']} vs {len(served_alt)}")
    check("D: tb_dropped counts exactly the candle-less minute", cnt["tb_dropped"] == len(served_gone) == 1,
          str(cnt["tb_dropped"]))
    return sdD


def steps(mkt):
    """The requests the feed saw inside each step: {minute: {"candle_coins": [...], "trades_coins": [...]}}."""
    out = {}
    for ph, m, kind, c in mkt.calls:
        if ph == "step":
            r = out.setdefault(m, {"candle_coins": [], "trades_coins": []})
            r["candle_coins" if kind == "candles" else "trades_coins"].append(c)
    return out


def model(st):
    """Modelled end of each step's data part (seconds after the minute) and its request counts (MODEL above)."""
    e, nc, nt = [], [], []
    for r in st.values():
        tr = sum(MODEL["BTC"] if c == "BTC" else MODEL["trades"] for c in r["trades_coins"])
        e.append(MODEL["start"] + MODEL["candles"] * len(r["candle_coins"]) + tr)
        nc.append(len(r["candle_coins"]))
        nt.append(len(r["trades_coins"]))
    return e, nc, nt


def med(x):
    return float(pd.Series(x).median()) if len(x) else float("nan")


def main():
    a = [x for x in sys.argv[1:] if not x.startswith("--")]
    start, end = a[0], a[1]
    death = next((x.split("=", 1)[1] for x in sys.argv[1:] if x.startswith("--death=")), None)
    inputs = next((x.split("=", 1)[1] for x in sys.argv[1:] if x.startswith("--inputs=")),
                  os.path.join(HERE, "config.json"))
    switch = next((x.split("=", 1)[1] for x in sys.argv[1:] if x.startswith("--switch=")),
                  str(pd.Timestamp(start) + pd.Timedelta(hours=1)))
    src = json.load(open(inputs))
    if src.get("newest_bar") != "trades":
        check(f"{inputs} is on newest_bar trades (nothing to compare otherwise)", False, str(src.get("newest_bar")))
        return
    after = src.get("trades_rows") == "candle_after"
    tmp = tempfile.mkdtemp(prefix="lsi_r3_")
    r3 = os.path.join(tmp, "release3_inputs.json")
    with open(r3, "w") as f:
        json.dump(RELEASE3, f)
    print(f"=== A: candle mode", flush=True)
    sdA, okA = L.main(start, end, death=death)
    print(f"\n=== B: inputs of {inputs} from the start", flush=True)
    sdB, okB = L.main(start, end, death=death, inputs=inputs)
    mB = L.LAST["mkt"]
    print(f"\n=== C1: candle mode until {switch}, then the inputs of {inputs}", flush=True)
    sdC1, okC1 = L.main(start, end, death=death, inputs=inputs, switch=switch)
    sw1 = dict(L.SWITCH_SEEN)
    L.SWITCH_SEEN.clear()
    print(f"\n=== C2: release 3's inputs until {switch}, then the inputs of {inputs}", flush=True)
    sdC2, okC2 = L.main(start, end, death=death, inputs=inputs, switch=switch, switch_from=r3)
    sw2 = dict(L.SWITCH_SEEN)
    print(flush=True)
    check("A: live-path checks pass", okA)
    check("B: live-path checks pass", okB)
    check("C1: live-path checks pass", okC1)
    check("C2: live-path checks pass", okC2)
    A, B, C1, C2 = lines(sdA), lines(sdB), lines(sdC1), lines(sdC2)
    compare("B", A, B)
    fills = lambda x: [y for y in x if '"kind": "fill_' in y]  # noqa: E731
    for tag, C, sw in (("C1", C1, sw1), ("C2", C2, sw2)):
        compare(f"{tag}, entries and exits", fills(A), fills(C))
        d = first_diff(A, C)
        print(f"  {tag}, whole log (the new process at the switch logs its own start-up): {len(C)} vs {len(A)} lines; "
              + ("identical" if d is None else f"first difference at line {d[0]}:\n    candle run: {d[1]}\n    {tag}:"
                                                f"         {d[2]}"), flush=True)
        check(f"{tag}: the switch happened, with no exception, and the open ladders were kept",
              sw.get("t") is not None and sw.get("before") == sw.get("after"),
              f"{len(sw.get('before') or [])} before, {len(sw.get('after') or [])} after")
    for tag, sd in (("B", sdB), ("C1", sdC1), ("C2", sdC2)):
        n, t = totals(sd)
        print(f"  {tag}: heartbeats {n}; bars built from trades {t['tb_built']}, trades rows the candle replaced "
              f"{t['tb_replaced']} (differed {t['tb_replaced_diff']}), dropped {t['tb_dropped']}, still waiting "
              f"{t['tb_pending']}, fallbacks {t['fallbacks']}, btc_stale {t['btc_stale']}, skip_old {t['skip_old']}",
              flush=True)
        check(f"{tag}: bars were built from trades", t["tb_built"] > 0)
        if after:
            check(f"{tag}: the venue's candle replaced trades rows, none differed, none was dropped",
                  t["tb_replaced"] > 0 and t["tb_replaced_diff"] == 0 and t["tb_dropped"] == 0, str(t))
    hA = [{k: v for k, v in h.items() if k != "counts" and k != "step_s"} for h in heartbeats(sdA)]
    hB = [{k: v for k, v in h.items() if k != "counts" and k != "step_s"} for h in heartbeats(sdB)]
    check("B: heartbeats equal A's apart from the counters and step timing", hA == hB)
    on = RI.apply({}, src)[0].get("candles_at_s") is not None   # B has the setting (as the live bot takes it)
    runs = [("B", sdB, mB, on, src.get("trades_coins"))]
    print(f"\n=== E: the inputs of {inputs} " + ("without candles_at_s" if on else f"with candles_at_s {AT_S}"),
          flush=True)
    # without candles_at_s, standstill_candles goes too (it needs candles_at_s; kept, it is ignored with a warning)
    sdE, okE = L.main(start, end, death=death, inputs=inputs, over=dict({"candles_at_s": None if on else AT_S},
                                                                       **({"standstill_candles": None} if on else {})))
    runs.append(("E", sdE, L.LAST["mkt"], not on, src.get("trades_coins")))
    if death is None:
        for k, at in (("F0", False), ("F1", True)):
            print(f"\n=== {k}: the inputs of {inputs} with release 3's five coins on the trades list, "
                  + (f"candles_at_s {AT_S}" if at else "without candles_at_s"), flush=True)
            sdF, okF = L.main(start, end, inputs=inputs, over=dict({"trades_coins": RELEASE3["trades_coins"],
                                                                    "candles_at_s": AT_S if at else None},
                                                                   **({} if at else {"standstill_candles": None})))
            check(f"{k}: live-path checks pass", okF)
            runs.append((k, sdF, L.LAST["mkt"], at, RELEASE3["trades_coins"]))
    else:
        print("  F: not run with --death (run without it)", flush=True)
    check("E: live-path checks pass", okE)
    for tag, sd, mkt, at, tl in runs[1:]:
        compare(tag, A, lines(sd))
        h = [{k: v for k, v in x.items() if k != "counts" and k != "step_s"} for x in heartbeats(sd)]
        check(f"{tag}: heartbeats equal A's apart from the counters and step timing", hA == h)
    print(flush=True)
    every = ["BTC"] + list(L.LAST["eng"].coins)
    for tag, sd, mkt, at, tl in runs:
        n, t = totals(sd)
        print(f"  {tag}: candles_at_s {'on' if at else 'off'}; heartbeats {n}; bars built from trades {t['tb_built']}, "
              f"replaced by the candle {t['tb_replaced']} (differed {t['tb_replaced_diff']}), dropped "
              f"{t['tb_dropped']}, still waiting {t['tb_pending']}, fallbacks {t['fallbacks']}; candle pass: coins "
              f"fetched {t['pre_fetched']}, pre_missing {t['pre_missing']}, on demand {t['pre_ondemand']}; candle "
              f"requests in the step (counter) {t['step_candles']}", flush=True)
        st = steps(mkt)
        ps = {m for ph, m, kind, c in mkt.calls if ph == "pass"}
        tbc = every if tl is None else [c for c in every if c in tl]
        aft = [r for m, r in st.items() if m - pd.Timedelta(minutes=1) in ps]
        bad = sum(1 for r in aft for c in r["candle_coins"] if c in tbc)
        print(f"    {tag}: steps {len(st)}, after a candle pass {len(aft)}; candle requests in those steps for "
              f"coins built from trades: {bad}; in all steps: {sum(len(r['candle_coins']) for r in st.values())}",
              flush=True)
        if at:
            check(f"{tag}: no candle request for a coin built from trades in a step after a candle pass",
                  bad == 0 and len(aft) > 0, f"{bad} in {len(aft)} steps")
            check(f"{tag}: the candle pass ran and fetched coins", t["pre_fetched"] > 0)
        else:
            check(f"{tag}: without the setting no candle pass and no new counter",
                  not ps and not any(t[k] for k in ("pre_fetched", "pre_missing", "pre_ondemand", "step_candles")))
    print("\n  modelled clock (a model, not a measurement: the data step starts at 6 s; 0.19 s per candle request, "
          "0.58 s for BTC's trades request, 0.15 s for every other coin's, one after another):", flush=True)
    for tag, sd, mkt, at, tl in runs:
        e, nc, nt = model(steps(mkt))
        print(f"  model {tag}: {len(every) if tl is None else len(tl)} coins on the trades list, candles_at_s "
              f"{'on' if at else 'off'}: data step ends at {med(e):.2f} s median, {max(e):.2f} s at most; per "
              f"step {med(nc):g} candle and {med(nt):g} trades requests (median)", flush=True)
    for sd in [x[1] for x in runs[1:]]:
        if not FAILS:
            shutil.rmtree(sd, ignore_errors=True)
    sdD = None
    if not after:
        print(f"  D: not run ({inputs} does not set \"trades_rows\": \"candle_after\")", flush=True)
    elif death is not None:
        print("  D: not run with --death (run without it)", flush=True)
    else:
        sdD = case_d(start, end, inputs)
    shutil.rmtree(tmp, ignore_errors=True)
    if not FAILS:
        for sd in (sdA, sdB, sdC1, sdC2, sdD):
            if sd:
                shutil.rmtree(sd, ignore_errors=True)


if __name__ == "__main__":
    main()
    print("LIVE-PATH INPUTS TEST " + ("FAILED: " + ", ".join(FAILS) if FAILS else "PASSED"))
    sys.exit(1 if FAILS else 0)
