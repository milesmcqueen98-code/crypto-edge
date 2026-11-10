"""Paper against research: the plan's measures 1 to 4 (reports/owner/paper_reconcile_plan.md). Light; runs offline.

Inputs: paper_spot/events.jsonl (the bot's log), reports/owner/reconcile/research_minutes.csv.gz and
late_btc_at_arms.csv (from fetch_and_compute.py on a runner), paper_spot/state.json (the engine's specs: the tick of
each coin, as spec(c).tick returned it), bot/v2/model_meta.json (threshold).

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
    Bot fill: the first rung-4 fill_entry of each ladder. Both: same coin and minute.
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


def compute(ev, R, late, ticks, thr, end=common.END):
    """ev: events (common.load_events). R: research table (ts, coin, level, score, sig, valid, beta, btc_r1_bp,
    btc_r2_bp, open, high, low). late: late-BTC table (ts, coin, btc_lag, level, score) or None.
    Returns a dict of DataFrames / dicts."""
    out = {}
    brief = common.live_minutes_brief(ev, end)
    dec, reset = common.live_minutes(ev, end)
    decset = set(dec)
    out["live"] = dict(brief_minutes=len(brief), brief_hours=len(brief) / 60, decision_minutes=len(dec),
                       decision_hours=len(dec) / 60, startups=[(str(b), str(s), h) for b, s, h in common.startups(ev)],
                       error_minutes=[str(m) for m in common.error_minutes(ev)],
                       gaps=[(str(a), str(b)) for a, b in common.logged_gaps(ev)])
    R = R.copy()
    R["ts"] = pd.to_datetime(R["ts"])
    R = R.set_index(["ts", "coin"]).sort_index()
    coins = sorted(R.index.get_level_values("coin").unique())
    busy = common.busy_intervals(ev)

    def rget(t, c, k):
        try:
            return R.at[(t, c), k]
        except KeyError:
            return np.nan

    def rpx(t, c):
        lv = rget(t, c, "level")
        return floor_to(lv, ticks[c]) if np.isfinite(lv) else np.nan

    # research armed state on decision minutes
    arm = pd.DataFrame(False, index=dec, columns=coins)
    for c in coins:
        sub = R.xs(c, level="coin").reindex(dec)
        ok = sub["valid"].fillna(False).astype(bool) & (sub["score"] > thr)
        b = np.array([common.is_busy(busy, c, t) for t in dec])
        arm[c] = ok.to_numpy() & ~b
    rnew = common.research_new_bids(arm, dec, reset)
    rnew_set = set(rnew)

    arms = [e for e in ev if e["kind"] == "arm" and e["t"] <= end]
    cash = [e for e in ev if e["kind"] == "cash_short" and e["t"] <= end]
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
    A = pd.DataFrame(rows)
    out["arms"] = A
    Ad = A[A.in_decision & A.err_bp.notna()]
    m1 = dist(Ad.err_bp)
    m1.update({f"raw_{k}": v for k, v in dist(Ad.err_raw_bp).items() if k != "n"})
    out["m1"] = m1
    expl = []
    for name, x in (("beta x BTC 1-min return to t-1 (sign flipped)", "pred_late1_bp"),
                    ("beta x BTC 2-min return to t-1 (sign flipped)", "pred_late2_bp")):
        for yname in ("err_raw_bp", "err_bp"):
            expl.append(dict(x=name, y=yname, **ols(Ad[yname], Ad[x])))
    if "late1_err_bp" in Ad:
        for lag in (1, 2):
            expl.append(dict(x=f"replayed level error, BTC {lag} min late (engine code)", y="err_raw_bp",
                             **ols(Ad.err_raw_bp, Ad[f"late{lag}_err_bp"])))
    out["m1_explain"] = pd.DataFrame(expl)
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
    out["m2"] = m2

    # ---------------- measure 3
    Ab = A[A.in_decision]
    rn = pd.DataFrame(rnew, columns=["ts", "coin"])
    if len(rn):
        rn["bot_arm_pm1"] = [any((t + k * MIN, c) in bot_arm_keys for k in (-1, 0, 1)) for t, c in zip(rn.ts, rn.coin)]
        rn["cash_short_pm1"] = [any((t + k * MIN, c) in cash_keys for k in (-1, 0, 1)) for t, c in zip(rn.ts, rn.coin)]
        rn["score"] = [rget(t, c, "score") for t, c in zip(rn.ts, rn.coin)]
    else:
        rn = pd.DataFrame(columns=["ts", "coin", "bot_arm_pm1", "cash_short_pm1", "score"])
    rn_nc = rn[~rn.cash_short_pm1.astype(bool)]
    out["research_new"] = rn
    out["m3"] = dict(bot_new_bids=int(len(Ab)), bot_matched=int(Ab.research_new_pm1.sum()),
                     share_bot_in_research=float(Ab.research_new_pm1.mean()) if len(Ab) else np.nan,
                     bot_research_armed_at_t=float(Ab.research_armed_t.mean()) if len(Ab) else np.nan,
                     bot_after_cash_short=int(Ab.cash_short_prev.sum()),
                     research_new_bids=int(len(rn)), research_cash_blocked=int(rn.cash_short_pm1.astype(bool).sum()),
                     research_new_bids_ex_cash=int(len(rn_nc)), research_matched=int(rn_nc.bot_arm_pm1.sum()),
                     share_research_in_bot=float(rn_nc.bot_arm_pm1.mean()) if len(rn_nc) else np.nan,
                     bot_arms_outside_decision_minutes=int((~A.in_decision).sum()))
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
    r4pnl, ladpnl = {}, {}
    for e in ev:
        if e["kind"] == "fill_exit" and e.get("rung") == 4:
            r4pnl[e["ladder"]] = r4pnl.get(e["ladder"], 0.0) + e["pnl"]
        if e["kind"] == "ladder_close":
            ladpnl[e["ladder"]] = e["pnl"]
    rfill = []                                          # research first-bid fill episodes
    for c in coins:
        busy_until = None
        sub = R.xs(c, level="coin")
        for t in dec:
            if busy_until is not None and t <= busy_until:
                continue
            if not arm.at[t, c]:
                continue
            lo = sub["low"].get(t, np.nan)
            px = rpx(t, c)
            if np.isfinite(lo) and np.isfinite(px) and lo <= px * (1 + 1e-12):
                sig = sub["sig"].get(t, np.nan)
                tp = floor_to(px * math.exp(THETA * K * sig), ticks[c])
                hi = sub["high"].loc[t + MIN: t + HOLD * MIN]
                hit = hi[hi >= tp]
                busy_until = hit.index[0] if len(hit) else t + HOLD * MIN
                rfill.append((t, c, px, lo))
    rf = pd.DataFrame(rfill, columns=["ts", "coin", "res_px", "final_low"])
    rf_keys = {(t, c) for t, c in zip(rf.ts, rf.coin)}
    rows = []
    for lad, e in fills.items():
        t, c = e["t"].floor("min"), e["coin"]
        px = rpx(t, c)
        lo = rget(t, c, "low")
        armed = bool(t in arm.index and arm.at[t, c])
        res_fill = bool(armed and np.isfinite(lo) and np.isfinite(px) and lo <= px * (1 + 1e-12))
        rows.append(dict(group="both" if res_fill else "bot_only", ts=t, coin=c, ladder=lad, bot_px=e["px"],
                         res_px=px, final_low=lo, research_armed=armed, rung4_pnl=r4pnl.get(lad),
                         ladder_pnl=ladpnl.get(lad), in_decision=t in decset))
    for t, c, px, lo in rf.itertuples(index=False):
        if not any(r["ts"] == t and r["coin"] == c for r in rows):
            rows.append(dict(group="research_only", ts=t, coin=c, ladder=None, bot_px=np.nan, res_px=px, final_low=lo,
                             research_armed=True, rung4_pnl=np.nan, ladder_pnl=np.nan, in_decision=True,
                             bot_armed_pm1=any((t + k * MIN, c) in bot_arm_keys for k in range(-60, 1))))
    F = pd.DataFrame(rows).sort_values(["ts", "coin"]) if rows else pd.DataFrame()
    out["fills"] = F
    m4 = []
    for g in ("both", "bot_only", "research_only"):
        x = F[F.group == g] if len(F) else F
        m4.append(dict(group=g, n=int(len(x)), bot_rung4_pnl=float(x.rung4_pnl.sum()) if len(x) else 0.0,
                       bot_ladder_pnl=float(x.ladder_pnl.sum()) if len(x) else 0.0))
    out["m4"] = pd.DataFrame(m4)
    out["research_fill_episodes"] = int(len(rf))
    out["research_fill_matched"] = int(sum(1 for k in rf_keys if k in {(r["ts"], r["coin"]) for r in rows
                                                                        if r["group"] == "both"}))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--events", default=os.path.join(ROOT, "paper_spot", "events.jsonl"))
    ap.add_argument("--state", default=os.path.join(ROOT, "paper_spot", "state.json"))
    ap.add_argument("--dir", default=OUT)
    a = ap.parse_args()
    ev = common.load_events(a.events)
    meta = json.load(open(os.path.join(ROOT, "bot", "v2", "model_meta.json")))
    thr = float(meta["threshold"])
    ticks = {c: float(v["tick"]) for c, v in json.load(open(a.state))["specs"].items()}
    R = pd.read_csv(os.path.join(a.dir, "research_minutes.csv.gz"))
    lp = os.path.join(a.dir, "late_btc_at_arms.csv")
    late = pd.read_csv(lp) if os.path.exists(lp) else None
    o = compute(ev, R, late, ticks, thr)
    o["arms"].to_csv(os.path.join(a.dir, "m1_m2_bot_arms.csv"), index=False, float_format="%.6g")
    pd.DataFrame([o["m1"]]).to_csv(os.path.join(a.dir, "m1_level_error.csv"), index=False, float_format="%.4g")
    o["m1_explain"].to_csv(os.path.join(a.dir, "m1_explained_by_late_btc.csv"), index=False, float_format="%.4g")
    if "m1_closest" in o:
        o["m1_closest"].to_csv(os.path.join(a.dir, "m1_closest_input.csv"), index=False, float_format="%.4g")
    o["m1_by_coin"].to_csv(os.path.join(a.dir, "m1_by_coin.csv"), index=False, float_format="%.4g")
    if "m1_by_btc_move" in o:
        o["m1_by_btc_move"].to_csv(os.path.join(a.dir, "m1_by_btc_move.csv"), index=False, float_format="%.4g")
    pd.DataFrame([o["m2"]]).to_csv(os.path.join(a.dir, "m2_score_error.csv"), index=False, float_format="%.4g")
    pd.DataFrame([o["m3"]]).to_csv(os.path.join(a.dir, "m3_bids.csv"), index=False, float_format="%.4g")
    o["research_new"].to_csv(os.path.join(a.dir, "m3_research_new_bids.csv"), index=False, float_format="%.6g")
    o["cash_short"].to_csv(os.path.join(a.dir, "m3_cash_short.csv"), index=False, float_format="%.6g")
    o["fills"].to_csv(os.path.join(a.dir, "m4_fills.csv"), index=False, float_format="%.8g")
    o["m4"].to_csv(os.path.join(a.dir, "m4_summary.csv"), index=False, float_format="%.2f")
    summ = dict(live=o["live"], m1=o["m1"], m2=o["m2"], m3=o["m3"], research_fill_episodes=o["research_fill_episodes"],
                research_fill_matched=o["research_fill_matched"])
    json.dump(summ, open(os.path.join(a.dir, "summary.json"), "w"), indent=1, default=float)
    pd.set_option("display.width", 200)
    print(json.dumps(summ, indent=1, default=float))
    for k in ("m1_explain", "m1_closest", "m1_by_coin", "m1_by_btc_move", "m4"):
        if k in o:
            print(k)
            print(o[k].to_string(index=False))


if __name__ == "__main__":
    main()
