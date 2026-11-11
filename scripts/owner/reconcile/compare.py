"""Paper against research: the plan's measures 1 to 4 (reports/owner/paper_reconcile_plan.md). Light; runs offline.

Inputs: <book>/events.jsonl (the bot's log; book default paper_spot), research_minutes.csv.gz and
late_btc_at_arms.csv in --dir (default reports/owner/reconcile; from fetch_and_compute.py on a runner),
<book>/state.json (the engine's specs: the tick of each coin, as spec(c).tick returned it), bot/v2/model_meta.json
(threshold).

Parameters (defaults reproduce the first reconciliation byte for byte): --book (folder), --start and --end (UTC
minutes, both included; default: the book's first event to common.END = 2026-11-10 13:30), --dir (research input),
--out (output folder; default --dir).

A period that starts after the book's first event (common.py): start-ups, logged gaps, the armed-bid reset, busy
intervals (open rung-4 ladders) and each bot ladder's P&L come from the whole log; the minutes, bids, fills and
cash_short events compared are those inside the period. The first minute of the period: a research bid there is
"new" when the research was not armed at the book's previous decision minute (common.prev_decision_minute, which may
lie before the period; the research table must hold it, else compute raises), or when a logged gap lies in between.
Matching windows (one minute either side, three minutes after a cash_short) do not look across the period's edges:
only bot arms and cash_short events inside the period are matched. The research's own fill episodes start afresh at
the period's first minute (a research dip just before the period does not hold the coin busy into it). The research
table is limited to the book's own brief live minutes in the period (and that previous minute), so a research file
computed for several books gives each book what a file for it alone would.

stale_input (books run with stale_guard): when the book's log has stale_input events (or stale=True is passed), the
research new first bids at a minute with a stale_input event (exact minute: that step placed no bid for any coin) are
listed apart, as bids near a cash_short are: they leave the denominator of share_research_in_bot and research_matched
(with the cash-blocked ones), and nothing else. Columns stale_input_t, stale_input_pm1 and m3 keys
research_stale_blocked, research_near_stale_pm1, research_new_bids_ex_blocked, stale_input_minutes are added; the
heartbeats' skip_old totals in the period are reported (out["stale"]). Without stale_input events nothing changes.

How the live-minute set is built (common.py):
  - The brief's set: every minute from the book's first event (the backfill at Nov 6 22:30) to Nov 10 13:30, both
    included, less each logged gap. A catch_up event at ts b with gap_minutes g says the bot's last stepped minute was
    a = b - g; the gap is (a, b], g minutes. This is the figure reported as "live hours (brief)".
  - The decision minutes used for the comparison (README deviations D1, D2) are that set less (D1) the start-up
    minutes of each paper job, from its backfill minute b up to its first step s (the bot was downloading 11 days of
    candles and made no decision; s from the first event only a step writes, at most 6 minutes after b, else b + 6),
    and less (D2) the one minute whose step raised before the AI ran (Nov 7 21:19).
  - A research bid is "new" at t when it is armed at t and was not armed at the previous decision minute, or a logged
    gap lies in between (catch_up cancels all armed bids). Across a start-up with no logged gap the bot keeps its armed
    bids, so the research is compared with its own state at the previous decision minute.

Rules:
  - Tick: the engine's spec(c).tick, read from paper_spot/state.json ("specs"). Research price = floor to the tick of
    the research level, as the engine's _arm_plan does. A price difference within one tick (1e-9 relative slack) is 0.
  - Research armed at t: the engine's inputs are valid (fresh BTC and coin, finite level, sig, z_res60, bid_depth_bp),
    score > threshold, and the coin has no open 4-sigma rung in the bot's log at t (common.busy_intervals); cash and
    slot limits are not modelled (the bot's cash_short events are listed apart).
  - Research new first bid: see common.research_new_bids. Matching a bid: same coin, minute t-1, t or t+1.
  - First-bid fill (research): research armed at minute m and the final candle's low of minute m at or below the
    research price. After such a fill the research coin is treated as busy until the first later minute whose final
    high reaches the research take-profit (price x exp(0.6 x 4 x sigma)) or for 60 minutes, so one dip counts once.
    Only minutes the bot settled count (step m+1 settles minute m; the last decision minute before a start-up or a
    gap, and the final minute, were never settled, so no bot fill can be seen in them).
    Bot fill: the first rung-4 fill_entry of each ladder. "Both" (the plan's rule, per bot fill): research armed at
    the bot's fill minute and the final low at or below the research price. "Research only": a research fill episode
    with no bot first-bid fill on the coin from one minute before it until the research rung would have closed (so one
    dip is not counted on both sides when the two fill a few minutes apart).
"""
import argparse
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, HERE)

import numpy as np          # noqa: E402
import pandas as pd         # noqa: E402

import common               # noqa: E402

OUT = os.path.join(ROOT, "reports", "owner", "reconcile")
MIN = common.MIN
THETA, K, HOLD = 0.6, 4.0, 60
ARM_COLS = ["ts", "coin", "ladder", "bot_px", "bot_pred", "bot_sigma_bp", "in_decision", "res_level", "res_px",
            "res_score", "res_valid", "res_sigma_bp", "beta", "btc_r1_bp", "btc_r2_bp", "tick", "diff_ticks", "err_bp",
            "err_raw_bp", "pred_late1_bp", "pred_late2_bp", "score_diff", "res_other_side", "research_new_pm1",
            "research_armed_t", "cash_short_prev"]          # the per-bid table's columns when a book has no bid


def floor_to(x, inc):
    return math.floor(x / inc + 1e-9) * inc       # the engine's floor_to


def same_px(a, b, tick):
    return abs(a - b) <= tick * (1 + 1e-9)


def dist(x):
    x = pd.Series(x, dtype=float).dropna()
    if not len(x):
        return dict(n=0)
    return dict(n=int(len(x)), median=x.median(), p5=x.quantile(0.05), p95=x.quantile(0.95),
                median_abs=x.abs().median(), share_abs_gt5=(x.abs() > 5).mean(), share_abs_gt20=(x.abs() > 20).mean())


def ols(y, x):
    d = pd.DataFrame(dict(y=y, x=x)).dropna()
    if len(d) < 3 or d.x.std() == 0:
        return dict(n=len(d), corr=np.nan, slope=np.nan, intercept=np.nan, r2=np.nan)
    b, a = np.polyfit(d.x, d.y, 1)
    c = float(np.corrcoef(d.x, d.y)[0, 1])
    return dict(n=int(len(d)), corr=c, slope=float(b), intercept=float(a), r2=c * c)


def empty_arms():
    """The per-bid table of a book with no bid in the period, with typed columns."""
    bools = {"in_decision", "res_other_side", "research_new_pm1", "research_armed_t", "cash_short_prev"}
    return pd.DataFrame({c: pd.Series(dtype="datetime64[ns]" if c == "ts" else object if c in ("coin", "ladder")
                                      else bool if c in bools else float) for c in ARM_COLS})


def m1_stats(A):
    """Measure 1 on a per-bid table (compute's out["arms"] or a filtered copy): bids in decision minutes with a
    research level."""
    Ad = A[A.in_decision & A.err_bp.notna()]
    m1 = dist(Ad.err_bp)
    m1.update({f"raw_{k}": v for k, v in dist(Ad.err_raw_bp).items() if k != "n"})
    return m1


def m1_explain(A):
    Ad = A[A.in_decision & A.err_bp.notna()]
    expl = []
    for name, x in (("beta x BTC 1-min return to t-1 (sign flipped)", "pred_late1_bp"),
                    ("beta x BTC 2-min return to t-1 (sign flipped)", "pred_late2_bp")):
        for yname in ("err_raw_bp", "err_bp"):
            expl.append(dict(x=name, y=yname, **ols(Ad[yname], Ad[x])))
    if "late1_err_bp" in Ad:
        for lag in (1, 2):
            expl.append(dict(x=f"replayed level error, BTC {lag} min late (engine code)", y="err_raw_bp",
                             **ols(Ad.err_raw_bp, Ad[f"late{lag}_err_bp"])))
    return pd.DataFrame(expl)


def m2_stats(A):
    """Measure 2 on a per-bid table: bids in decision minutes with a research score."""
    S = A[A.in_decision & A.res_score.notna()]
    m2 = dict(n=int(len(S)), median_abs_diff=float(S.score_diff.abs().median()) if len(S) else np.nan,
              median_diff=float(S.score_diff.median()) if len(S) else np.nan,
              p90_abs_diff=float(S.score_diff.abs().quantile(0.9)) if len(S) else np.nan,
              share_other_side=float(S.res_other_side.mean()) if len(S) else np.nan,
              n_other_side=int(S.res_other_side.sum()))
    if "late1_score" in S:
        for lag in (1, 2):
            dd = (S.bot_pred - S[f"late{lag}_score"]).abs()
            m2[f"median_abs_diff_vs_btc{lag}late"] = float(dd.median())
    return m2


def m3_stats(A, rn):
    """Measure 3 from a per-bid table and a research-new-bids table (compute's out["research_new"])."""
    Ab = A[A.in_decision]
    stale = "stale_input_t" in rn
    rn_nc = rn[~rn.cash_short_pm1.astype(bool)]
    rn_nb = rn_nc[~rn_nc.stale_input_t.astype(bool)] if stale else rn_nc       # left out of the share: blocked
    m3 = dict(bot_new_bids=int(len(Ab)), bot_matched=int(Ab.research_new_pm1.sum()),
              share_bot_in_research=float(Ab.research_new_pm1.mean()) if len(Ab) else np.nan,
              bot_research_armed_at_t=float(Ab.research_armed_t.mean()) if len(Ab) else np.nan,
              bot_after_cash_short=int(Ab.cash_short_prev.sum()),
              research_new_bids=int(len(rn)), research_cash_blocked=int(rn.cash_short_pm1.astype(bool).sum()),
              research_new_bids_ex_cash=int(len(rn_nc)), research_matched=int(rn_nb.bot_arm_pm1.sum()),
              share_research_in_bot=float(rn_nb.bot_arm_pm1.mean()) if len(rn_nb) else np.nan,
              bot_arms_outside_decision_minutes=int((~A.in_decision).sum()))
    if stale:
        m3.update(research_stale_blocked=int(rn.stale_input_t.astype(bool).sum()),
                  research_near_stale_pm1=int(rn.stale_input_pm1.astype(bool).sum()),
                  research_new_bids_ex_blocked=int(len(rn_nb)))
    return m3


def m4_stats(F):
    m4 = []
    for g in ("both", "bot_only", "research_only"):
        x = F[F.group == g] if len(F) else F
        m4.append(dict(group=g, n=int(len(x)), bot_rung4_pnl=float(x.rung4_pnl.sum()) if len(x) else 0.0,
                       bot_ladder_pnl=float(x.ladder_pnl.sum()) if len(x) else 0.0,
                       n_open_above_res_px=int(x.open_above_res_px.sum()) if len(x) else 0))
    return pd.DataFrame(m4)


def compute(ev, R, late, ticks, thr, end=common.END, start=None, stale=None):
    """ev: events (common.load_events). R: research table (ts, coin, level, score, sig, valid, beta, btc_r1_bp,
    btc_r2_bp, open, high, low). late: late-BTC table (ts, coin, btc_lag, level, score) or None.
    start, end: the period (UTC minutes, both included; start None = the book's first event).
    stale: list research new bids at stale_input minutes apart (None: when the log has stale_input events).
    Returns a dict of DataFrames / dicts."""
    out = {}
    end = pd.Timestamp(end)
    p0 = common.period_start(ev, start)                 # the period's first minute
    brief = common.live_minutes_brief(ev, end, start)
    dec, reset = common.live_minutes(ev, end, start)
    pm = common.prev_decision_minute(ev, end, start)     # research state needed there (None: not needed)
    decset = set(dec)
    if stale is None:
        stale = any(e["kind"] == "stale_input" for e in ev)
    out["live"] = dict(brief_minutes=len(brief), brief_hours=len(brief) / 60, decision_minutes=len(dec),
                       decision_hours=len(dec) / 60,
                       startups=[(str(b), str(s), h) for b, s, h in common.startups(ev) if b <= end and s > p0],
                       error_minutes=[str(m) for m in common.error_minutes(ev) if p0 <= m <= end],
                       gaps=[(str(a), str(b)) for a, b in common.logged_gaps(ev) if a < end and b >= p0])
    R = R.copy()
    R["ts"] = pd.to_datetime(R["ts"])
    keep_ts = set(brief) | ({pm} if pm is not None else set())   # the book's own minutes only
    if pm is not None and not (R["ts"] == pm).any():
        raise ValueError(f"the research table has no row at {pm}, the book's decision minute before the period "
                         f"(needed for research new bids at {dec[0]}); compute the research side with this period")
    R = R[R["ts"].isin(keep_ts)]
    R = R.set_index(["ts", "coin"]).sort_index()
    coins = sorted(R.index.get_level_values("coin").unique())
    busy = common.busy_intervals(ev, end)

    def rget(t, c, k):
        try:
            return R.at[(t, c), k]
        except KeyError:
            return np.nan

    def rpx(t, c):
        lv = rget(t, c, "level")
        return floor_to(lv, ticks[c]) if np.isfinite(lv) else np.nan

    # research armed state on decision minutes (and the book's previous decision minute, when needed)
    dx = dec if pm is None else pd.DatetimeIndex([pm]).append(dec)
    arm = pd.DataFrame(False, index=dx, columns=coins)
    for c in coins:
        sub = R.xs(c, level="coin").reindex(dx)
        ok = sub["valid"].fillna(False).astype(bool) & (sub["score"] > thr)
        b = np.array([common.is_busy(busy, c, t) for t in dx])
        arm[c] = ok.to_numpy() & ~b
    rnew = [(t, c) for t, c in common.research_new_bids(arm, dx, reset if pm is None else {pm: True, **reset})
            if t != pm]
    arm = arm.loc[dec] if pm is not None else arm
    rnew_set = set(rnew)

    def inp(e):                                         # an event inside the period
        return e["t"] <= end and e["t"].floor("min") >= p0
    arms = [e for e in ev if e["kind"] == "arm" and inp(e)]
    cash = [e for e in ev if e["kind"] == "cash_short" and inp(e)]
    stale_min = {e["t"].floor("min") for e in ev if e["kind"] == "stale_input" and inp(e)}
    cash_keys = {(e["t"].floor("min"), e["coin"]) for e in cash}
    bot_arm_keys = {(e["t"].floor("min"), e["coin"]) for e in arms}

    # ---------------- measure 1 and 2: per bot arm
    rows = []
    lt = None
    if late is not None and len(late):
        lt = late.copy()
        lt["ts"] = pd.to_datetime(lt["ts"])
        lt = lt.set_index(["ts", "coin", "btc_lag"]).sort_index()
    for e in arms:
        t, c = e["t"].floor("min"), e["coin"]
        tick = ticks[c]
        lv = rget(t, c, "level")
        px_r = rpx(t, c)
        d = dict(ts=t, coin=c, ladder=e["ladder"], bot_px=e["px"], bot_pred=e["pred"], bot_sigma_bp=e["sigma_bp"],
                 in_decision=t in decset, res_level=lv, res_px=px_r, res_score=rget(t, c, "score"),
                 res_valid=rget(t, c, "valid"), res_sigma_bp=rget(t, c, "sig") * 1e4, beta=rget(t, c, "beta"),
                 btc_r1_bp=rget(t, c, "btc_r1_bp"), btc_r2_bp=rget(t, c, "btc_r2_bp"), tick=tick)
        if np.isfinite(px_r):
            diff = e["px"] - px_r
            d["diff_ticks"] = diff / tick
            d["err_bp"] = 0.0 if same_px(e["px"], px_r, tick) else 1e4 * (e["px"] / px_r - 1)
            d["err_raw_bp"] = 1e4 * (e["px"] / lv - 1)          # bot price against the unrounded research level
        d["pred_late1_bp"] = -d["beta"] * d["btc_r1_bp"]        # level error a one-minute-late BTC gives (approx.)
        d["pred_late2_bp"] = -d["beta"] * d["btc_r2_bp"]
        d["score_diff"] = e["pred"] - d["res_score"]
        d["res_other_side"] = bool(np.isfinite(d["res_score"]) and not d["res_score"] > thr)
        if lt is not None:
            for lag in (1, 2):
                try:
                    lv_l = lt.at[(t, c, lag), "level"]
                    sc_l = lt.at[(t, c, lag), "score"]
                except KeyError:
                    lv_l = sc_l = np.nan
                d[f"late{lag}_px"] = floor_to(lv_l, tick) if np.isfinite(lv_l) else np.nan
                d[f"late{lag}_score"] = sc_l
                d[f"late{lag}_err_bp"] = (1e4 * (lv_l / lv - 1)) if np.isfinite(lv_l) and np.isfinite(lv) else np.nan
            same = {lag: (np.isfinite(d.get(f"late{lag}_px", np.nan)) and same_px(e["px"], d[f"late{lag}_px"], tick))
                    for lag in (1, 2)}
            same[0] = bool(np.isfinite(px_r) and same_px(e["px"], px_r, tick))
            d["closest"] = ("final" if same[0] else "btc_1min_late" if same[1] else "btc_2min_late" if same[2]
                            else "none_within_tick")
        d["research_new_pm1"] = any((t + k * MIN, c) in rnew_set for k in (-1, 0, 1))
        d["research_armed_t"] = bool(t in arm.index and c in arm.columns and arm.at[t, c])
        d["cash_short_prev"] = any((t - k * MIN, c) in cash_keys for k in (1, 2, 3))
        rows.append(d)
    A = pd.DataFrame(rows) if rows else empty_arms()
    out["arms"] = A
    Ad = A[A.in_decision & A.err_bp.notna()]
    out["m1"] = m1_stats(A)
    out["m1_explain"] = m1_explain(A)
    if "closest" in Ad:
        out["m1_closest"] = Ad.closest.value_counts().rename_axis("bot price equals (within a tick)").reset_index(
            name="n").assign(share=lambda x: x.n / x.n.sum())
    bc = []
    for c, g in Ad.groupby("coin"):
        bc.append(dict(coin=c, tick=ticks[c], **dist(g.err_bp)))
    out["m1_by_coin"] = pd.DataFrame(bc)
    q = Ad.btc_r1_bp.abs()
    if len(Ad) >= 3:
        terc = pd.qcut(q.rank(method="first"), 3, labels=["low", "mid", "high"])
        bm = []
        for lab in ["low", "mid", "high"]:
            g = Ad[terc == lab]
            bm.append(dict(btc_move_tercile=lab, abs_r1_bp_min=g.btc_r1_bp.abs().min(),
                           abs_r1_bp_max=g.btc_r1_bp.abs().max(), **dist(g.err_bp)))
        out["m1_by_btc_move"] = pd.DataFrame(bm)
    out["m2"] = m2_stats(A)

    # ---------------- measure 3
    rn = pd.DataFrame(rnew, columns=["ts", "coin"])
    rn_cols = ["ts", "coin", "bot_arm_pm1", "cash_short_pm1", "score"] + (
        ["stale_input_t", "stale_input_pm1"] if stale else [])
    if len(rn):
        rn["bot_arm_pm1"] = [any((t + k * MIN, c) in bot_arm_keys for k in (-1, 0, 1)) for t, c in zip(rn.ts, rn.coin)]
        rn["cash_short_pm1"] = [any((t + k * MIN, c) in cash_keys for k in (-1, 0, 1)) for t, c in zip(rn.ts, rn.coin)]
        rn["score"] = [rget(t, c, "score") for t, c in zip(rn.ts, rn.coin)]
        if stale:
            rn["stale_input_t"] = [t in stale_min for t in rn.ts]
            rn["stale_input_pm1"] = [any(t + k * MIN in stale_min for k in (-1, 0, 1)) for t in rn.ts]
    else:
        rn = pd.DataFrame(columns=rn_cols)
    out["research_new"] = rn
    out["m3"] = m3_stats(A, rn)
    if stale:
        out["m3"]["stale_input_minutes"] = len(stale_min)
        hb = [e for e in ev if e["kind"] == "heartbeat" and inp(e)]
        out["stale"] = dict(stale_input_minutes=len(stale_min), heartbeats=len(hb),
                            skip_old_total=int(sum((e.get("counts") or {}).get("skip_old", 0) for e in hb)),
                            note="skip_old: coins given no new bid because their newest row was old, summed over "
                                 "the heartbeats inside the period (each covers the 30 minutes to its ts); not "
                                 "logged per coin, so not matched to research bids")
        sm = []
        for e in ev:
            if e["kind"] == "stale_input" and inp(e):
                t = e["t"].floor("min")
                ins = t in arm.index
                sm.append(dict(ts=t, age_min=e.get("age_min"), decision_minute=t in decset,
                               research_armed=int(arm.loc[t].sum()) if ins else None,
                               research_new=int(sum(1 for x, _ in rnew if x == t))))
        out["stale_minutes"] = pd.DataFrame(sm, columns=["ts", "age_min", "decision_minute", "research_armed",
                                                         "research_new"])
    # cash_short cases, apart
    cs = []
    for e in cash:
        t, c = e["t"].floor("min"), e["coin"]
        cs.append(dict(ts=t, coin=c, bot_pred=e["pred"], want=e["want"], free=e["free"], res_score=rget(t, c, "score"),
                       research_armed=bool(t in arm.index and arm.at[t, c]),
                       research_new_pm1=any((t + k * MIN, c) in rnew_set for k in (-1, 0, 1))))
    out["cash_short"] = pd.DataFrame(cs)

    # ---------------- measure 4: first-bid fills
    fills = {}
    for e in ev:
        if e["kind"] == "fill_entry" and e.get("rung") == 4 and e["ladder"] not in fills and e["t"] <= end:
            fills[e["ladder"]] = e
    fills = {k: e for k, e in fills.items() if inp(e)}     # the ladder's first rung-4 fill, inside the period
    r4pnl, ladpnl = {}, {}
    for e in ev:
        if e["kind"] == "fill_exit" and e.get("rung") == 4:
            r4pnl[e["ladder"]] = r4pnl.get(e["ladder"], 0.0) + e["pnl"]
        if e["kind"] == "ladder_close":
            ladpnl[e["ladder"]] = e["pnl"]
    # A minute's fills are known only if the bot settled it: step m+1 settles minute m. The last decision minute
    # before a start-up or a gap, and the final minute (13:30; the log ends there), were never settled.
    settled = {t for t in dec if (t + MIN) in decset or (t + MIN) in set(common.error_minutes(ev))}
    rfill = []                                          # research first-bid fill episodes
    for c in coins:
        busy_until = None
        sub = R.xs(c, level="coin")
        for t in dec:
            if busy_until is not None and t <= busy_until:
                continue
            if t not in settled or not arm.at[t, c]:
                continue
            lo = sub["low"].get(t, np.nan)
            px = rpx(t, c)
            if np.isfinite(lo) and np.isfinite(px) and lo <= px * (1 + 1e-12):
                sig = sub["sig"].get(t, np.nan)
                tp = floor_to(px * math.exp(THETA * K * sig), ticks[c])
                hi = sub["high"].loc[t + MIN: t + HOLD * MIN]
                hit = hi[hi >= tp]
                busy_until = hit.index[0] if len(hit) else t + HOLD * MIN
                rfill.append((t, c, px, lo, busy_until, sub["open"].get(t, np.nan)))
    rf = pd.DataFrame(rfill, columns=["ts", "coin", "res_px", "final_low", "res_open_until", "final_open"])
    rows = []
    for lad, e in fills.items():
        t, c = e["t"].floor("min"), e["coin"]
        px = rpx(t, c)
        lo = rget(t, c, "low")
        armed = bool(t in arm.index and arm.at[t, c])
        res_fill = bool(armed and np.isfinite(lo) and np.isfinite(px) and lo <= px * (1 + 1e-12))
        rows.append(dict(group="both" if res_fill else "bot_only", ts=t, coin=c, ladder=lad, bot_px=e["px"],
                         res_px=px, final_low=lo, research_armed=armed, rung4_pnl=r4pnl.get(lad),
                         ladder_pnl=ladpnl.get(lad), in_decision=t in decset, settled=t in settled,
                         final_open=rget(t, c, "open"), open_above_res_px=bool(rget(t, c, "open") > px)))
    bot_fill_times = {}
    for r in rows:
        bot_fill_times.setdefault(r["coin"], []).append(r["ts"])
    n_ep_matched = 0
    for t, c, px, lo, until, op in rf.itertuples(index=False):
        # the same dip: a bot first-bid fill on the coin from one minute before the research fill until the research
        # rung would have closed (its take-profit minute or 60 minutes)
        near = [b for b in bot_fill_times.get(c, []) if t - MIN <= b <= until]
        if near:
            n_ep_matched += 1
            for r in rows:
                if r["coin"] == c and r["ts"] in near:
                    r.setdefault("research_fill_ts", t)
            continue
        rows.append(dict(group="research_only", ts=t, coin=c, ladder=None, bot_px=np.nan, res_px=px, final_low=lo,
                         research_armed=True, rung4_pnl=np.nan, ladder_pnl=np.nan, in_decision=True, settled=True,
                         final_open=op, open_above_res_px=bool(op > px),
                         bot_arm_prev60=any((t - k * MIN, c) in bot_arm_keys for k in range(0, 61)),
                         bot_cash_short_pm3=any((t + k * MIN, c) in cash_keys for k in range(-3, 4))))
    F = pd.DataFrame(rows).sort_values(["ts", "coin"]) if rows else pd.DataFrame()
    out["fills"] = F
    out["m4"] = m4_stats(F)
    out["research_fill_episodes"] = int(len(rf))
    out["research_fill_matched"] = int(n_ep_matched)
    # research dips in minutes the bot never settled (listed, not counted)
    uns = []
    for c in coins:
        sub = R.xs(c, level="coin")
        for t in dec:
            if t in settled or not arm.at[t, c]:
                continue
            lo, px = sub["low"].get(t, np.nan), rpx(t, c)
            if np.isfinite(lo) and np.isfinite(px) and lo <= px * (1 + 1e-12):
                uns.append(dict(ts=t, coin=c, res_px=px, final_low=lo))
    out["unsettled_research_dips"] = pd.DataFrame(uns, columns=["ts", "coin", "res_px", "final_low"])
    return out


def load_late(path, book):
    """late_btc_at_arms.csv, this book's rows (a file for several books has a `book` column), or None."""
    if not os.path.exists(path):
        return None
    late = pd.read_csv(path)
    if "book" in late.columns:
        late = late[late.book == book].drop(columns="book").reset_index(drop=True)
    return late


def load_inputs(book_dir, research_dir, events=None, state=None):
    """(ev, R, late, ticks, thr) for one book folder and one research folder."""
    ev = common.load_events(events or os.path.join(book_dir, "events.jsonl"))
    meta = json.load(open(os.path.join(ROOT, "bot", "v2", "model_meta.json")))
    thr = float(meta["threshold"])
    ticks = {c: float(v["tick"]) for c, v in json.load(open(state or os.path.join(book_dir, "state.json")))["specs"].items()}
    R = pd.read_csv(os.path.join(research_dir, "research_minutes.csv.gz"))
    late = load_late(os.path.join(research_dir, "late_btc_at_arms.csv"), os.path.basename(os.path.normpath(book_dir)))
    return ev, R, late, ticks, thr


def summary(o, period=None):
    summ = dict(live=o["live"], m1=o["m1"], m2=o["m2"], m3=o["m3"], research_fill_episodes=o["research_fill_episodes"],
                research_fill_matched=o["research_fill_matched"])
    if "stale" in o:
        summ["stale"] = o["stale"]
    if period is not None:
        summ["period"] = period
    return summ


def write_outputs(o, out_dir, period=None):
    """The files of the first reconciliation (m1 to m4 CSVs, summary.json), same names and formats."""
    os.makedirs(out_dir, exist_ok=True)
    o["arms"].to_csv(os.path.join(out_dir, "m1_m2_bot_arms.csv"), index=False, float_format="%.6g")
    pd.DataFrame([o["m1"]]).to_csv(os.path.join(out_dir, "m1_level_error.csv"), index=False, float_format="%.4g")
    o["m1_explain"].to_csv(os.path.join(out_dir, "m1_explained_by_late_btc.csv"), index=False, float_format="%.4g")
    if "m1_closest" in o:
        o["m1_closest"].to_csv(os.path.join(out_dir, "m1_closest_input.csv"), index=False, float_format="%.4g")
    o["m1_by_coin"].to_csv(os.path.join(out_dir, "m1_by_coin.csv"), index=False, float_format="%.4g")
    if "m1_by_btc_move" in o:
        o["m1_by_btc_move"].to_csv(os.path.join(out_dir, "m1_by_btc_move.csv"), index=False, float_format="%.4g")
    pd.DataFrame([o["m2"]]).to_csv(os.path.join(out_dir, "m2_score_error.csv"), index=False, float_format="%.4g")
    pd.DataFrame([o["m3"]]).to_csv(os.path.join(out_dir, "m3_bids.csv"), index=False, float_format="%.4g")
    o["research_new"].to_csv(os.path.join(out_dir, "m3_research_new_bids.csv"), index=False, float_format="%.6g")
    o["cash_short"].to_csv(os.path.join(out_dir, "m3_cash_short.csv"), index=False, float_format="%.6g")
    if "stale_minutes" in o:                            # only for a book with stale_input events (or stale=True)
        o["stale_minutes"].to_csv(os.path.join(out_dir, "m3_stale_input.csv"), index=False)
    o["fills"].to_csv(os.path.join(out_dir, "m4_fills.csv"), index=False, float_format="%.8g")
    o["m4"].to_csv(os.path.join(out_dir, "m4_summary.csv"), index=False, float_format="%.2f")
    o["unsettled_research_dips"].to_csv(os.path.join(out_dir, "m4_unsettled_minutes.csv"), index=False,
                                        float_format="%.8g")
    summ = summary(o, period)
    json.dump(summ, open(os.path.join(out_dir, "summary.json"), "w"), indent=1, default=float)
    return summ


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--book", default=os.path.join(ROOT, "paper_spot"), help="paper book folder (events, state)")
    ap.add_argument("--events", default=None, help="default <book>/events.jsonl")
    ap.add_argument("--state", default=None, help="default <book>/state.json")
    ap.add_argument("--start", default=None, help="first UTC minute (default: the book's first event)")
    ap.add_argument("--end", default=None, help=f"last UTC minute (default {common.END})")
    ap.add_argument("--dir", default=OUT, help="folder with research_minutes.csv.gz and late_btc_at_arms.csv")
    ap.add_argument("--out", default=None, help="output folder (default: --dir)")
    a = ap.parse_args()
    ev, R, late, ticks, thr = load_inputs(a.book, a.dir, a.events, a.state)
    end = pd.Timestamp(a.end) if a.end else common.END
    start = pd.Timestamp(a.start) if a.start else None
    o = compute(ev, R, late, ticks, thr, end=end, start=start)
    period = None
    if a.start or a.end:
        period = dict(book=os.path.basename(os.path.normpath(a.book)), start=str(common.period_start(ev, start)),
                      end=str(end))
    summ = write_outputs(o, a.out or a.dir, period)
    pd.set_option("display.width", 200)
    print(json.dumps(summ, indent=1, default=float))
    for k in ("m1_explain", "m1_closest", "m1_by_coin", "m1_by_btc_move", "m4"):
        if k in o:
            print(k)
            print(o[k].to_string(index=False))


if __name__ == "__main__":
    main()
