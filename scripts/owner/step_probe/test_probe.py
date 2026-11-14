"""Offline tests of probe.py: a fake market and a fake clock that moves only through the fake sleep and by a fixed
0.2 s per fake call. No network, no real sleep. Run: python scripts/owner/step_probe/test_probe.py
(one line per check, last line "N checks, F failed", non-zero exit on a failure)."""
import argparse
import contextlib
import csv
import io
import json
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import pandas as pd     # noqa: E402

import probe            # noqa: E402

BASE = 1_700_000_040            # a whole UTC minute (divisible by 60)
CALL_S = 0.2
FAILS = []
COUNT = [0]
SYM = probe.SYMBOLS


def check(name, ok, info=""):
    COUNT[0] += 1
    print(("ok   " if ok else "FAIL ") + name + ("" if ok else f"  [{info}]"))
    if not ok:
        FAILS.append(name)


class Refused(RuntimeError):
    pass


class Limited(Refused):
    pass


class Clock:
    def __init__(self, t):
        self.t = float(t)
        self.slept = []

    def now(self):
        return self.t

    def sleep(self, s):
        self.slept.append(s)
        self.t += s


class FakeMarket:
    """minute_trades_bar calls get once (so the wrapper sees a first page), then the clock moves CALL_S."""
    Refused = Refused
    Limited = Limited

    def __init__(self, clock, call_s=CALL_S, raiser=None, age="2", bar_fn=None):
        self.clock = clock
        self.call_s = call_s
        self.raiser = raiser            # function(call_number, coin, minute) -> exception or None
        self.age = age
        self.bar_fn = bar_fn
        self.TRADES_RATE = 7.0
        self._last_req = [0.0]
        self.calls = []                 # (coin, minute, clock at start)
        self.get_results = []

    def _get_h(self, url, params=None, tries=2):
        self._last_req[0] = self.clock.t
        hd = {"Date": "Sat, 14 Nov 2026 11:00:00 GMT"}
        if self.age is not None:
            hd["Age"] = self.age
        out = ([], hd)
        self.get_results.append(out)
        return out

    def minute_trades_bar(self, coin, m, get=None):
        n = len(self.calls) + 1
        self.calls.append((coin, pd.Timestamp(m), self.clock.t))
        got = get(f"https://fake/products/{coin}-USD/trades", {"limit": 1000})
        assert got is self.get_results[-1], "get result not passed through"
        self.clock.t += self.call_s
        if self.raiser is not None:
            exc = self.raiser(n, coin, pd.Timestamp(m))
            if exc is not None:
                raise exc
        bar = self.bar_fn(coin, m) if self.bar_fn else dict(open=0.1 + 0.2, high=2.5, low=0.1, close=1e-9, volume=3.0)
        return dict(bar=bar, verified=True, reason=None, pages=1, gen=pd.Timestamp(m) + pd.Timedelta(seconds=61),
                    newest=pd.Timestamp(m), n=0 if bar is None else 7)


def args_for(minutes, **kw):
    d = dict(minutes=minutes, out="unused", early_at=1.0, standard_at=6.0, ref_at=35.0)
    d.update(kw)
    return argparse.Namespace(**d)


def do_run(minutes, t_start=BASE + 10, call_s=CALL_S, raiser=None, tmp=None, **kw):
    clk = Clock(t_start)
    mk = FakeMarket(clk, call_s=call_s, raiser=raiser)
    out = tempfile.mkdtemp(dir=tmp)
    rc = probe.run(args_for(minutes, **kw), mk, clk.now, clk.sleep, out)
    with open(os.path.join(out, "calls.csv"), newline="") as f:
        rows = list(csv.DictReader(f))
    with open(os.path.join(out, "run.json")) as f:
        rj = json.load(f)
    return rc, rows, rj, mk, clk, out


def sel(rows, pname, q=None):
    return [r for r in rows if r["pass"] == pname and (q is None or r["q"] == probe.iso(q))]


def main():
    tmp = tempfile.mkdtemp()
    try:
        # a normal run of 3 minutes: start at BASE + 10, so the first q is BASE + 60
        rc, rows, rj, mk, clk, out = do_run(3, tmp=tmp)
        qs = [BASE + 60, BASE + 120, BASE + 180]
        check("normal run: exit code 0, completed, stopped is null", rc == 0 and rj["stopped"] is None)
        check("normal run: q done are the three boundaries", rj["q_done"] == [probe.iso(q) for q in qs], rj["q_done"])
        check("first boundary is at least 5 s after the start (start 10 s past a minute: next minute)",
              rj["q_done"][0] == probe.iso(BASE + 60))
        rc2, _, rj2, *_ = do_run(1, t_start=BASE + 55, tmp=tmp)
        check("start exactly 5 s before a boundary: that boundary is used", rj2["q_done"] == [probe.iso(BASE + 60)])
        rc3, _, rj3, *_ = do_run(1, t_start=BASE + 55.5, tmp=tmp)
        check("start 4.5 s before a boundary: the next one is used", rj3["q_done"] == [probe.iso(BASE + 120)])
        check("calls: 18 per pass, 3 passes per q, plus the final reference pass",
              len(rows) == 18 * (3 * 3 + 1) and rj["calls_by_pass"] == {"early": 54, "standard": 54, "reference": 72},
              rj["calls_by_pass"])

        # pass start seconds
        e0, s0, r0 = sel(rows, "early", qs[0]), sel(rows, "standard", qs[0]), sel(rows, "reference", qs[0])
        check("early pass starts at q + 1.0 s", e0[0]["sent_s"] == "1.000", e0[0]["sent_s"])
        check("early pass: one call after another, 0.2 s apart", [r["sent_s"] for r in e0[:3]] == ["1.000", "1.200", "1.400"])
        check("standard pass starts at q + 6.0 s (early ended at 4.6 s)", s0[0]["sent_s"] == "6.000", s0[0]["sent_s"])
        check("reference pass starts at q + 35.0 s, measured from this q", r0[0]["sent_s"] == "35.000", r0[0]["sent_s"])
        check("places are 0-based positions", [r["place"] for r in e0] == [str(i) for i in range(18)])

        # order and rotation
        others = SYM[1:]
        for i, q in enumerate(qs):
            want = [SYM[0]] + others[i:] + others[:i]
            e = [r["coin"] for r in sel(rows, "early", q)]
            s = [r["coin"] for r in sel(rows, "standard", q)]
            check(f"q index {i}: early order is BTC then the 17 rotated left by {i}", e == want, e)
            check(f"q index {i}: standard order equals the early order", s == want)
            check(f"q index {i}: BTC first in both", e[0] == "BTC" and s[0] == "BTC")
        check("reference pass keeps the list order", [r["coin"] for r in r0] == SYM)
        big = sorted({tuple(r["coin"] for r in sel(rows, "early", q)[1:3]) for q in qs})
        check("rotation moves on by one place (second and third coins of three minutes)",
              big == sorted({("ETH", "SOL"), ("SOL", "XRP"), ("XRP", "DOGE")}), big)

        # minutes
        e_min = {r["minute"] for r in sel(rows, "early")}
        check("early and standard ask for m = q - 60 s",
              sel(rows, "early", qs[1])[0]["minute"] == probe.iso(qs[1] - 60)
              and sel(rows, "standard", qs[1])[0]["minute"] == probe.iso(qs[1] - 60))
        check("reference pass asks for the minute before m (q - 120 s)",
              r0[0]["minute"] == probe.iso(qs[0] - 120) and sel(rows, "reference", qs[2])[0]["minute"] == probe.iso(qs[2] - 120))
        final = [r for r in rows if r["pass"] == "reference" and r["q"] == probe.iso(qs[-1] + 60)]
        check("extra reference pass after the last q, for the last m",
              len(final) == 18 and final[0]["minute"] == probe.iso(qs[-1] - 60) and final[0]["sent_s"] == "35.000",
              final[:1])
        ref_min = {(r["coin"], r["minute"]) for r in sel(rows, "reference")}
        check("every probed minute has a reference row for every coin",
              all((c, m) in ref_min for c in SYM for m in e_min))
        check("final_reference_done is recorded", rj["final_reference_done"] is True)

        # row content
        r = e0[0]
        check("row: coin, verified, reason, pages, n, error", (r["coin"], r["verified"], r["reason"], r["pages"], r["n"], r["error"]) == ("BTC", "1", "", "1", "7", ""), r)
        check("row: gen_s is the first page's generation time minus q (m + 61 s - q = 1)", r["gen_s"] == "1.000", r["gen_s"])
        check("row: Age header kept as received", r["age"] == "2", r["age"])
        check("row: dur_s is the call time", r["dur_s"] == "0.200", r["dur_s"])
        check("header is exactly the columns in the brief",
              open(os.path.join(out, "calls.csv")).readline().strip().split(",") == probe.COLUMNS)
        check("floats round-trip exactly through repr",
              [float(r[k]) for k in ("open", "high", "low", "close", "volume")] == [0.1 + 0.2, 2.5, 0.1, 1e-9, 3.0]
              and r["open"] == "0.30000000000000004" and r["close"] == "1e-09", r)
        check("q and minute are ISO (UTC, Z)", r["q"] == probe.iso(BASE + 60) and r["minute"] == probe.iso(BASE) and r["q"].endswith("Z"), r["q"])

        # run.json
        check("run.json: rate, python, args, start", rj["trades_rate"] == 7.0 and rj["python"] == sys.version
              and rj["args"]["minutes"] == 3 and rj["started"] == probe.iso(BASE + 10))
        check("run.json: largest requests in any second is at most 7 (fake paces at 5 a second)",
              rj["max_requests_in_one_second"] in (5, 6) and rj["requests_sent"] == len(rows), rj["max_requests_in_one_second"])
        check("max_in_window: 7 at the pace, boundary exact, and 8 is seen", probe.max_in_window([i / 7 for i in range(7)]) == 7
              and probe.max_in_window([0.0, 0.25, 0.5, 0.75, 1.0]) == 4
              and probe.max_in_window([0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7]) == 8 and probe.max_in_window([]) == 0)

        # standard pass after a long early pass
        rc, rows_b, rj_b, *_ = do_run(1, tmp=tmp, standard_at=3.0)
        sb = sel(rows_b, "standard")
        check("standard pass starts when the early pass ends if that is after standard-at (3.0 s: ends at 4.6 s)",
              sb[0]["sent_s"] == "4.600", sb[0]["sent_s"])
        rc, rows_c, *_ = do_run(1, tmp=tmp, early_at=2.0, ref_at=20.0)
        check("--early-at and --ref-at are honoured", sel(rows_c, "early")[0]["sent_s"] == "2.000" and sel(rows_c, "reference")[0]["sent_s"] == "20.000")

        # Limited stops the run
        def lim(n, coin, m):
            return Limited("HTTP 429 on x") if n == 25 else None
        rc, rows_l, rj_l, mk_l, *_ = do_run(3, raiser=lim, tmp=tmp)
        check("Limited: no further call after the refusal", len(mk_l.calls) == 25, len(mk_l.calls))
        check("Limited: stopped is limited, message kept, run returned normally (code 0)",
              rj_l["stopped"] == "limited" and "429" in rj_l["stopped_message"] and rc == 0, rj_l["stopped"])
        check("Limited: rows kept, last row carries the error and is unverified",
              len(rows_l) == 25 and rows_l[-1]["error"].startswith("HTTP 429") and rows_l[-1]["verified"] == "0")
        check("Limited: no reference pass, no extra pass after it", not rj_l["final_reference_done"] and len(rj_l["q_done"]) == 0)

        def ref(n, coin, m):
            return Refused("HTTP 403 on x") if n == 3 else None
        rc, rows_f, rj_f, mk_f, *_ = do_run(3, raiser=ref, tmp=tmp)
        check("Refused: stopped is refused, no further call", rj_f["stopped"] == "refused" and len(mk_f.calls) == 3 and rc == 0)

        # other errors
        def val(n, coin, m):
            return ValueError("trades page is not a list: x") if n == 2 else None
        rc, rows_v, rj_v, mk_v, *_ = do_run(1, raiser=val, tmp=tmp)
        check("ValueError is recorded (verified 0, error text) and the run goes on",
              rows_v[1]["verified"] == "0" and rows_v[1]["error"].startswith("trades page") and rj_v["stopped"] is None
              and len(rows_v) == 18 * 4 and rows_v[2]["verified"] == "1")

        def many(n, coin, m):
            return ValueError("x" * 300) if n <= 40 else None
        rc, rows_m, rj_m, mk_m, *_ = do_run(3, raiser=many, tmp=tmp)
        check("40 errors in a row stop the run with stopped errors", rj_m["stopped"] == "errors" and len(mk_m.calls) == 40 and rc == 0
              and len(rows_m) == 40, (rj_m["stopped"], len(mk_m.calls)))
        check("error text is cut to 200 characters", len(rows_m[0]["error"]) == 200)

        def many39(n, coin, m):
            return ValueError("x") if n <= 39 or n == 41 else None
        rc, rows_n, rj_n, *_ = do_run(1, raiser=many39, tmp=tmp)
        check("39 in a row then a good call: the count starts again (call 41 is an error but alone)", rj_n["stopped"] is None and len(rows_n) == 72)

        # skipped passes: every call takes 4 s
        rc, rows_s, rj_s, mk_s, *_ = do_run(1, call_s=4.0, tmp=tmp)
        check("a pass that cannot start by q + 55 s is skipped and counted (slow calls: standard and reference)",
              rj_s["skipped_passes"] == {"early": 0, "standard": 1, "reference": 1}, rj_s["skipped_passes"])
        check("skipped passes make no request; the extra reference pass still runs",
              rj_s["calls_by_pass"] == {"early": 18, "standard": 0, "reference": 18} and len(mk_s.calls) == 36, rj_s["calls_by_pass"])
        rc, rows_t, rj_t, mk_t, *_ = do_run(1, tmp=tmp, early_at=56.0)
        check("a start later than q + 55 s is skipped at once", rj_t["skipped_passes"]["early"] == 1
              and sel(rows_t, "early") == [])

        # an existing calls.csv is never overwritten
        clk = Clock(BASE + 10)
        mk = FakeMarket(clk)
        try:
            probe.run(args_for(1), mk, clk.now, clk.sleep, out)
            ok = False
        except FileExistsError:
            ok = True
        check("an existing calls.csv is refused, not overwritten", ok and len(mk.calls) == 0)

        # the wrapper
        clk = Clock(BASE)
        mk = FakeMarket(clk, age=None)
        info = {"pages": 0, "sent": None, "date": None, "age": None}
        sends = []
        g = probe.make_get(mk, info, sends)
        clk.t = BASE + 3.5
        res = g("u", {"limit": 1000})
        check("wrapper: returns the result unchanged, notes send time, Date, no Age", res is mk.get_results[-1]
              and info["sent"] == BASE + 3.5 and info["age"] is None and info["date"].startswith("Sat") and sends == [BASE + 3.5])
        clk.t = BASE + 4.0
        g("u", {"limit": 1000, "after": 5})
        check("wrapper: later pages add a send time but do not change the first", info["sent"] == BASE + 3.5 and len(sends) == 2)

        # the guard around run()
        def guard_case(exc_type):
            clk = Clock(BASE + 10)
            mk = FakeMarket(clk)
            o = tempfile.mkdtemp(dir=tmp)
            orig, n = probe.append_rows, [0]

            def bad(path, rows):
                n[0] += 1
                if n[0] == 2:
                    raise exc_type("disk went away")
                return orig(path, rows)
            probe.append_rows = bad
            try:
                err = io.StringIO()
                with contextlib.redirect_stderr(err):
                    rc_ = probe.guarded_run(args_for(2), mk, clk.now, clk.sleep, o)
            finally:
                probe.append_rows = orig
            return rc_, o, err.getvalue()
        rc_g, og, errtext = guard_case(RuntimeError)
        with open(os.path.join(og, "crash.json")) as f:
            cj = json.load(f)
        with open(os.path.join(og, "calls.csv"), newline="") as f:
            kept = list(csv.DictReader(f))
        check("guard: an escaping RuntimeError returns 0 and writes crash.json (type, text, traceback tail, UTC time)",
              rc_g == 0 and cj["type"] == "RuntimeError" and cj["text"] == "disk went away" and "Traceback" in cj["traceback_tail"]
              and len(cj["traceback_tail"]) <= 2000 and cj["time_utc"].endswith("Z"), cj)
        check("guard: the traceback goes to stderr", "RuntimeError: disk went away" in errtext)
        check("guard: rows already appended (the early pass, 18 rows) are still in calls.csv and run.json exists",
              len(kept) == 18 and os.path.exists(os.path.join(og, "run.json")), len(kept))
        try:
            guard_case(KeyboardInterrupt)
            ok = False
        except KeyboardInterrupt:
            ok = True
        check("guard: KeyboardInterrupt is not caught", ok)
        clk = Clock(BASE + 10)
        mk = FakeMarket(clk)
        try:
            probe.guarded_run(args_for(1), mk, clk.now, clk.sleep, og)
            ok = False
        except FileExistsError:
            ok = True
        check("guard: an existing calls.csv still raises FileExistsError (non-zero exit), no request made", ok and not mk.calls)
        clk = Clock(BASE + 10)
        mk = FakeMarket(clk)
        o_ok = tempfile.mkdtemp(dir=tmp)
        rc_ok = probe.guarded_run(args_for(1), mk, clk.now, clk.sleep, o_ok)
        check("guard: a normal run through guarded_run returns 0 and writes no crash.json",
              rc_ok == 0 and not os.path.exists(os.path.join(o_ok, "crash.json")) and len(mk.calls) == 72)

        # the real module is not touched by the tests
        check("tests never import bot.market", "bot.market" not in sys.modules)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print(f"{COUNT[0]} checks, {len(FAILS)} failed")
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
