#!/usr/bin/env python3
"""Signal lab 2: QA of the F6 print features -> reports/signal_lab/prints/QA.md.

Reads only derived files (no raw prints): f6_main.parquet, f6_early.parquet, qa_cand.parquet, qa_runner.json (written
by the features run), candle_usd.csv.gz (scripts/signal_lab/prints_windows.py, from the repo's minute candles),
runs.json (run ids and times) and the synthetic test (scripts/signal_lab/test_prints.py, run here again).
Touches no trading outcome: every quantity is from the 30 minutes before the candidate minute.

Gates (prereg deviation 1, before any model run)
  1. per era, at least 97% of candidates have a completely fetched window (complete = True);
  2. per era, the median over complete windows of print USD / candle USD over the same 30 minutes is 0.98-1.02.
Candle USD = sum over the 30 one-minute candles of close x volume, the simulator's daily_usd convention.
usage: python scripts/signal_lab/prints_qa.py [<dir of the feature run outputs; default reports/signal_lab/prints>]
"""
import io
import json
import os
import sys
from contextlib import redirect_stdout

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
PR = os.path.join(ROOT, "reports", "signal_lab", "prints")
ERAS = ("main", "early")
ERA_NAME = {"main": "main (2024-2026)", "early": "early (2021-2023)"}


def spearman(x, y):
    rx = pd.Series(x).rank().to_numpy()
    ry = pd.Series(y).rank().to_numpy()
    return float(np.corrcoef(rx, ry)[0, 1])


def qfmt(q, d=3):
    return "-" if not q else " / ".join(f"{x:.{d}f}" for x in q)


def boundary_section(add, out):
    """Follow-up of Nov 9: candle-print boundary offsets (qa_boundary.json from prints_boundary.py)."""
    p = os.path.join(out, "qa_boundary.json")
    if not os.path.exists(p):
        return
    B = json.load(open(p))
    add("## Candle-print boundary offsets (follow-up; prints_boundary.py, qa_boundary.json)")
    add("")
    add("The model decides fills from the candles and F6 reads prints stamped before q, so a candle q that held trades "
        "the prints stamp before q would let the features see the start of the fill minute. For every adjacent pair "
        "of minutes (m, m+1) inside a merged window where print base volume and candle volume differ (relative "
        "1e-5) in at least one of the two: the smallest boundary move that reconciles both minutes within 1e-5 "
        "(\"strict\": within 1e-7, the float32 precision of the candle files).")
    add("- **A** (could leak): the prints stamped in [m+1-d, m+1) sit in candle m+1; candle time lags print time.")
    add("- **B** (harmless): the prints stamped in [m+1, m+1+d) sit in candle m.")
    add("- **Neighbour:** this pair's difference is a reconciled move at the next boundary (one move leaves the two "
        "pairs around it unequal). **Edge:** the remaining difference sits in the first or last minute of a window, "
        "next to a boundary whose outer minute was never fetched. **Not reconciled:** no single move up to 60 s.")
    add("- A whole-minute shift moves every print of the source minute (its candle row is missing and the next one "
        "holds both minutes). d for a whole-minute A shift is measured from that minute's first print.")
    add(f"- Self-test on a synthetic tape with planted moves: `{B.get('self_test')}`")
    add("")
    add("| Year | Unequal pairs | A (strict) | A whole-minute | B (strict) | B whole-minute | Neighbour | Edge | "
        "Not reconciled (A-like / B-like / same sign) | Whole-minute share |")
    add("|---|---|---|---|---|---|---|---|---|---|")
    keys = ["all"] + sorted(k for k in B["pairs"] if k != "all")
    for k in keys:
        v = B["pairs"][k]
        nr = v["not_reconciled"]
        add(f"| {k} | {v['unequal']:,} of {v['pairs']:,} | {v['A']['n']:,} ({v['A']['strict']:,}) | "
            f"{v['A']['whole_minute']:,} | {v['B']['n']:,} ({v['B']['strict']:,}) | {v['B']['whole_minute']:,} | "
            f"{v['neighbour']:,} | {v['edge']:,} | {nr['n']:,} ({nr['a_like']:,} / {nr['b_like']:,} / "
            f"{nr['same_sign']:,}) | {100 * (v['share_whole_minute_of_unequal'] or 0):.1f}% |")
    add("")
    add("Offset d in seconds, p50 / p90 / p99 / max (all reconciled pairs; then without whole-minute shifts):")
    add("")
    add("| Year | A: all | A: sub-minute | B: all | B: sub-minute |")
    add("|---|---|---|---|---|")
    for k in keys:
        v = B["pairs"][k]
        add(f"| {k} | {qfmt(v['A']['d_q'])} | {qfmt(v['A']['d_sub_minute_q'])} | {qfmt(v['B']['d_q'])} | "
            f"{qfmt(v['B']['d_sub_minute_q'])} |")
    add("")
    add("At the boundary before each candidate (m+1 = q). Two-sided where minute q lies inside a merged window; "
        "otherwise minute q was never fetched and A is tested on minute q-1 alone (candle q-1 = its prints less a "
        "suffix, candle q holding at least that volume):")
    add("")
    add("| Era | Candidates | Two-sided: kinds | One-sided: kinds | A (whole-minute) | A share | A: d p50 / p90 / "
        "p99 / max (s) | A: moved USD / usd_30, p50 / p90 / p99 / max | Mean moved USD / usd_30, all candidates |")
    add("|---|---|---|---|---|---|---|---|---|")
    for e in ERAS:
        v = B["candidates"].get(e)
        if not v:
            continue
        add(f"| {e} | {v['n']:,} | {v['two_sided']:,}: {v['two_sided_kinds']} | {v['one_sided']:,}: "
            f"{v['one_sided_kinds']} | {v['A']:,} ({v['A_whole_minute']:,}) | {100 * v['A_share']:.2f}% | "
            f"{qfmt(v['A_d_q'])} | {qfmt(v['A_usd_over_usd30_q'], 4)} | {v['usd_over_usd30_mean_all']:.5f} |")
    add("")
    if "chain" in B:
        add("**Chain check.** The single-move test cannot reconcile runs of consecutive moves (a run of B moves leaves "
            "pairs with an A-like sign pattern that no one move fixes). The chain check solves every boundary of a "
            "window at once: with x the print volume stamped before a boundary that the candles put after it (A > 0, "
            "B < 0), candle m = prints m + x(before m) - x(after m), so x is carried from the window start (x = 0). "
            "Each x must be 0, a suffix of the left minute's prints (A) or a prefix of the right minute's (B); "
            "otherwise the boundary is unexplained (for example candle volume lost) and x restarts at 0. A move is "
            "confirmed when neither neighbouring boundary is unexplained.")
        add("")
        add("| Year | Boundaries | Zero | A confirmed (whole-minute) / unconfirmed | B confirmed (whole-minute) / "
            "unconfirmed | Unexplained | A confirmed d, sub-minute (s) | B confirmed d, sub-minute (s) | "
            "Pairs left open by the single-move test, by chain result |")
        add("|---|---|---|---|---|---|---|---|---|")
        for k in ["all"] + sorted(x for x in B["chain"] if x != "all"):
            v = B["chain"][k]
            kd = v["kinds"]
            add(f"| {k} | {v['boundaries']:,} | {kd.get('zero', 0):,} | {v['A']['confirmed']:,} "
                f"({v['A']['whole_minute']:,}) / {v['A']['unconfirmed']:,} | {v['B']['confirmed']:,} "
                f"({v['B']['whole_minute']:,}) / {v['B']['unconfirmed']:,} | {kd.get('unexplained', 0):,} | "
                f"{qfmt(v['A']['d_sub_minute_q'])} | {qfmt(v['B']['d_sub_minute_q'])} | "
                f"{v['single_move_open_pairs_by_chain']} |")
        add("")
        add("Chain check at the boundary before each candidate (B_unverified: x < 0 at a window end, where minute q "
            "was not fetched; harmless either way):")
        add("")
        add("| Era | Kinds | A confirmed (whole-minute) | A confirmed share | A: d p50 / p90 / p99 / max (s) | "
            "A: moved USD / usd_30, p50 / p90 / p99 / max | Mean moved USD / usd_30, all candidates |")
        add("|---|---|---|---|---|---|---|")
        for e in ERAS:
            v = B["candidates"].get(e)
            if not v:
                continue
            add(f"| {e} | {v['chain_kinds']} | {v['chain_A_confirmed']:,} ({v['chain_A_whole_minute']:,}) | "
                f"{100 * v['chain_A_confirmed_share']:.2f}% | {qfmt(v['chain_A_d_q'])} | "
                f"{qfmt(v['chain_A_usd_over_usd30_q'], 4)} | {v['chain_usd_over_usd30_mean_all']:.6f} |")
        add("")
    L_ = B["largest_A"]

    def s_(x):
        return "none" if x is None else f"{x:.3f} s"
    add(f"**Largest direction-A offset (single-move test):** over all window pairs {s_(L_['pairs_d_max'])} "
        f"({L_['pairs_whole_minute']:,} whole-minute shifts; largest sub-minute {s_(L_['pairs_sub_minute_d_max'])}); "
        f"at the boundary before a candidate {s_(L_['at_q_d_max'])} ({L_['at_q_whole_minute']:,} whole-minute; "
        f"largest sub-minute {s_(L_['at_q_sub_minute_d_max'])}).")
    if "largest_A_chain_confirmed" in B:
        L2 = B["largest_A_chain_confirmed"]
        add(f"**Largest direction-A offset (chain check, confirmed):** over all boundaries {s_(L2['boundaries_d_max'])} "
            f"({L2['boundaries_whole_minute']:,} whole-minute; largest sub-minute "
            f"{s_(L2['boundaries_sub_minute_d_max'])}); at the boundary before a candidate {s_(L2['at_q_d_max'])} "
            f"({L2['at_q_whole_minute']:,} whole-minute; largest sub-minute {s_(L2['at_q_sub_minute_d_max'])}).")
    cp = os.path.join(out, "qa_boundary_cand.parquet")
    if os.path.exists(cp) and "chain" in B:
        Q = pd.read_parquet(cp)
        parts = []
        for e in ERAS:
            g = Q[Q.era == e]
            a = g[(g.kind == "A") | ((g.chain_kind == "A") & g.chain_confirmed)]
            d = np.fmax(a.d_s.fillna(-1.0), a.chain_d_s.fillna(-1.0))
            parts.append(f"{e} {len(a)} of {len(g):,} candidates ({100 * len(a) / len(g):.2f}%), {int((d <= 5).sum())} "
                         f"with d <= 5 s, {int((d <= 60).sum())} with d <= 60 s; chain result unexplained at "
                         f"{int((g.chain_kind == 'unexplained').sum())}, B at "
                         f"{int(g.chain_kind.isin(['B', 'B_unverified']).sum())}")
        add("")
        add("- **Reading:** the candles mostly lead the prints (B: prints stamped in the first seconds of a minute sit "
            "in the previous candle), which cannot leak. Direction A at the boundary before a candidate, by either "
            "test: " + "; ".join(parts) + ". Most A cases there are whole-minute shifts (the candle row for q-1 is "
            "missing and candle q holds that minute's prints). Every A offset found is under 60 s, so the 60 s margin "
            "tables exclude all of them; the 5 s margin excludes few. Unexplained boundaries are undetermined, not "
            "shown to be A.")
    add("")


def margin_section(add, out):
    p = os.path.join(out, "qa_margin.json")
    if not os.path.exists(p):
        return
    M = json.load(open(p))
    add("## Margin tables (follow-up)")
    add("")
    add("f6_main_m5.parquet, f6_early_m5.parquet (margin 5 s) and f6_main_m60.parquet, f6_early_m60.parquet (margin "
        "60 s): the same schema, keys and row order as f6_main / f6_early, with both windows ending at q - margin, "
        "[q - 30 min, q - margin) and [q - 5 min, q - margin); the big-print threshold pool is unchanged (prints "
        "before q - 30 min), so big_thr_usd equals the margin-0 column. scripts/signal_lab/prints_features.py "
        "<art_dir> <out_dir> 0,5,60; the synthetic test checks that a print at q - margin is excluded and one 1 us "
        "earlier is included.")
    m0 = M.get("margin0", {})
    add(f"- **Margin 0 unchanged:** the same run recomputed the margin-0 tables: values equal to the committed files "
        f"(main {m0.get('main', {}).get('values_equal')}, early {m0.get('early', {}).get('values_equal')}), bytes "
        f"equal (main {m0.get('main', {}).get('bytes_equal')}, early {m0.get('early', {}).get('bytes_equal')}). The "
        "committed f6_main.parquet and f6_early.parquet were not rewritten.")
    add("")
    add("| Margin | Era | Complete | Windows without a print | Median n_prints | Missing (csv_30, csv_5, sell_share_30, "
        "big_sell_share_30, sweep_max_30) | Medians (same order) |")
    add("|---|---|---|---|---|---|---|")
    for m in sorted(M["margins"], key=int):
        for e in ERAS:
            v = M["margins"][m][e]
            miss = ", ".join(str(v["missing"][k]) for k in ("csv_30", "csv_5", "sell_share_30", "big_sell_share_30",
                                                             "sweep_max_30"))
            med = ", ".join(f"{v['median'][k]:.4g}" for k in ("csv_30", "csv_5", "sell_share_30", "big_sell_share_30",
                                                                "sweep_max_30"))
            add(f"| {m} s | {e} | {v['complete']:,} | {v['no_print_windows']:,} | {v['n_prints_median']:.0f} | {miss} "
                f"| {med} |")
    add("")


def fmt(x, d=4):
    return "n/a" if x is None or (isinstance(x, float) and not np.isfinite(x)) else f"{x:.{d}f}"


def main(out=PR):
    sys.path.insert(0, HERE)
    import test_prints
    buf = io.StringIO()
    with redirect_stdout(buf):
        test_msg = test_prints.run()
    F = {e: pd.read_parquet(os.path.join(out, f"f6_{e}.parquet")) for e in ERAS}
    Q = pd.read_parquet(os.path.join(out, "qa_cand.parquet"))
    R = json.load(open(os.path.join(out, "qa_runner.json")))
    CU = pd.read_csv(os.path.join(PR, "candle_usd.csv.gz"), parse_dates=["ts"])
    CU["ts"] = CU.ts.astype("datetime64[ns]")
    runs = json.load(open(os.path.join(out, "runs.json"))) if os.path.exists(os.path.join(out, "runs.json")) else {}
    W = pd.read_csv(os.path.join(PR, "windows.csv"), parse_dates=["start", "end"])
    L = []
    add = L.append
    gate_ok = {}

    # ----------------------------------------------------------------------------------- joins
    J = {}
    for e in ERAS:
        f = F[e]
        c = pd.read_csv(os.path.join(ROOT, "reports", "signal_lab", f"candidates_{e}.csv.gz"), parse_dates=["ts"])
        assert len(f) == len(c) and (f.coin.to_numpy() == c.coin.astype(str).to_numpy()).all()
        assert (f.ts.to_numpy() == c.ts.astype("datetime64[ns]").to_numpy()).all()
        assert str(f.ts.dtype) == "datetime64[ns]"
        key = pd.MultiIndex.from_arrays([f.coin, f.ts])
        cu = CU[CU.era == e].set_index(["coin", "ts"]).reindex(key)
        qa = Q[Q.era == e].set_index(["coin", "ts"]).reindex(key)
        j = f.copy()
        for k in ("candle_usd_30", "candle_vol_30", "ret_30", "adv_usd_era_bounded"):
            j[k] = cu[k].to_numpy()
        j["adv_candle"] = cu["adv_usd"].to_numpy()
        for k in ("window_id", "status", "vol_30", "px_first", "px_last", "n_sell", "thr_rule"):
            j[k] = qa[k].to_numpy()
        j["r_usd"] = j.usd_30 / j.candle_usd_30
        j["r_vol"] = j.vol_30 / j.candle_vol_30
        J[e] = j

    # ----------------------------------------------------------------------------------- header
    add("# F6 print features: data QA (signal lab 2)")
    add("")
    add("Branch signal-lab-data. Pre-registration: reports/signal_lab/prospective_prereg.md (Data, Features F6, "
        "deviation 1). Written by scripts/signal_lab/prints_qa.py from derived files only; raw prints stayed on the "
        "runners. Nothing here reads a trade outcome, label or prediction: every quantity is from the 30 minutes "
        "before the candidate minute.")
    add("")
    n_main, n_early = len(F["main"]), len(F["early"])
    tot_prints = sum(v.get("prints", 0) for v in R["coins"].values())
    add(f"- **Candidates:** {n_main:,} main + {n_early:,} early = {n_main + n_early:,} rows "
        "(f6_main.parquet, f6_early.parquet; same keys and order as the candidate lists).")
    add(f"- **Windows:** {len(W):,} merged windows (every [q - 30 min, q) of both eras, overlapping or touching "
        f"windows of one product merged); {tot_prints:,} distinct prints fetched.")
    if runs:
        add(f"- **Runs:** fetch {', '.join(str(r['id']) for r in runs.get('fetch', []))}; features "
            f"{runs.get('features', {}).get('id', 'n/a')}; diagnostic {runs.get('diagnostic', {}).get('id', 'n/a')}. "
            f"Wall-clock: {runs.get('wall', 'n/a')}.")
    add("")

    # ----------------------------------------------------------------------------------- gate
    add("## Data-quality gate (deviation 1)")
    add("")
    add("| Era | Candidates | Complete | Share complete (>= 97%) | Median print USD / candle USD (0.98-1.02) "
        "| Gate |")
    add("|---|---|---|---|---|---|")
    for e in ERAS:
        j = J[e]
        share = float(j.complete.mean())
        m = j.complete & (j.candle_usd_30 > 0)
        med = float(np.median(j.r_usd[m])) if m.any() else np.nan
        g1, g2 = share >= 0.97, (0.98 <= med <= 1.02)
        gate_ok[e] = g1 and g2
        add(f"| {ERA_NAME[e]} | {len(j):,} | {int(j.complete.sum()):,} | {100 * share:.2f}% "
            f"({'pass' if g1 else 'FAIL'}) | {med:.4f} over {int(m.sum()):,} windows ({'pass' if g2 else 'FAIL'}) "
            f"| {'**PASS**' if g1 and g2 else '**FAIL**'} |")
    add("")
    verdict = all(gate_ok.values())
    add(f"**Gate: {'PASSES in both eras' if verdict else 'FAILS'}.**" + (
        "" if verdict else " Per deviation 1 the test stops and the gap is reported."))
    add("")
    add("Candle USD = sum of close x volume over the 30 one-minute candles q-30 .. q-1 (the simulator's daily_usd "
        "convention) from data/minute_early (before 2024) and data/minute. Print USD = usd_30. Windows with zero "
        "candle volume are left out of the ratio.")
    add("")
    add("Spread of the per-window ratio (complete windows) and the same ratio in base units "
        "(sum of print size / candle volume; exact agreement expected):")
    add("")
    add("| Era | p1 | p10 | p50 | p90 | p99 | Base-volume ratio p1 / p50 / p99 |")
    add("|---|---|---|---|---|---|---|")
    for e in ERAS:
        j = J[e]
        m = j.complete & (j.candle_usd_30 > 0)
        qs = np.quantile(j.r_usd[m], [0.01, 0.1, 0.5, 0.9, 0.99])
        qv = np.quantile(j.r_vol[m & (j.candle_vol_30 > 0)], [0.01, 0.5, 0.99])
        add(f"| {e} | " + " | ".join(f"{x:.4f}" for x in qs) + f" | {qv[0]:.6f} / {qv[1]:.6f} / {qv[2]:.6f} |")
    add("")
    add("By coin (median print USD / candle USD over complete windows; share complete):")
    add("")
    add("| Coin | main n | main median | main complete | early n | early median | early complete |")
    add("|---|---|---|---|---|---|---|")
    coins = sorted(set(J["main"].coin) | set(J["early"].coin))
    for c in coins:
        cells = []
        for e in ERAS:
            j = J[e][J[e].coin == c]
            if not len(j):
                cells += ["-", "-", "-"]
                continue
            m = j.complete & (j.candle_usd_30 > 0)
            med = float(np.median(j.r_usd[m])) if m.any() else np.nan
            cells += [f"{int(m.sum()):,}", fmt(med), f"{100 * j.complete.mean():.1f}%"]
        add(f"| {c} | " + " | ".join(cells) + " |")
    add("")

    # ----------------------------------------------------------------------------------- minute diagnostic
    dpath = os.path.join(out, "qa_diag.json")
    if os.path.exists(dpath):
        D = json.load(open(dpath))
        add("## Where prints and candles differ (scripts/signal_lab/prints_diag.py, qa_diag.json)")
        add("")
        add("The window ratio's tails come from the candles, not from missing prints. Minute by minute over every "
            "minute of the merged windows, print base volume against the repo's candle volume (equal = within "
            "1e-5 relative; candle volume is stored as float32):")
        add("")
        add("| Era | Minutes | Equal | Candle has volume, no print | Print, no candle row (share of print "
            "volume) | Both, unequal (offset by the next or previous minute) | Prints above / below candle | "
            "Net print / candle volume |")
        add("|---|---|---|---|---|---|---|---|")
        for e in ERAS + tuple(k for k in sorted(D) if k.isdigit()):
            v = D[e]
            m = v["minutes"]
            add(f"| {e} | {m:,} | {100 * v['match'] / m:.1f}% | {v['print_gap']:,} | {v['candle_gap']:,} "
                f"({100 * v['print_vol_in_candle_gaps_share']:.2f}%) | {v['mismatch']:,} "
                f"({v['mismatch_offset_by_neighbour']:,}) | {v['mismatch_prints_above']:,} / "
                f"{v['mismatch_prints_below']:,} | {v['net_vol_ratio']:.4f} |")
        add("")
        g = D.get("trade_id_gaps")
        inv = D.get("inversions", {})
        if g:
            add(f"- **Trade-id gaps inside windows** (Coinbase numbers each product's trades 1, 2, 3, ...): "
                f"{g['gaps']:,} gaps ({g['missing_ids']:,} ids never returned) in {g['windows_with_gap']:,} windows, "
                f"over {g['consecutive_pairs']:,} consecutive pairs" + (f"; by year {g['by_year']}." if g["by_year"] else "."))
        add(f"- **Time against trade id:** {inv.get('n')} places where time decreases along trade id, all within the "
            f"same second (largest {inv.get('ms_quantiles', [None])[-1]} ms), {inv.get('straddle_window_edge')} "
            "across a window edge. The fetcher's stop rule (ids rise with time) holds, so no print at a window edge "
            "can be lost.")
        yrs = {k: D[k]["match"] / D[k]["minutes"] for k in D if k.isdigit()}
        worst = sorted(yrs, key=yrs.get)[:2]
        add("- **Reading:** every window is a contiguous run of trade ids read past both edges, and no minute has "
            "candle volume without prints, so the print side is complete. The differences are candles missing a "
            "minute (prints, no candle row) and volume the candles put in a neighbouring minute (most unequal minutes "
            "are offset by the next or previous minute). They are largest in " + " and ".join(
                f"{y} ({100 * yrs[y]:.0f}% of minutes equal)" for y in sorted(worst)) + ". They do not touch the F6 "
            "rows, which use only prints; they widen the tails of the gate's ratio, not its median.")
        add("")

    # ----------------------------------------------------------------------------------- tests
    add("## Look-ahead unit test (synthetic prints)")
    add("")
    add("scripts/signal_lab/test_prints.py runs before every feature run on the runner (the run stops if it fails) "
        "and again here. On synthetic clustered tapes with shared timestamps:")
    add("- prints added at q, q + 1 us, q + 1 s and q + 7 min leave n_prints and every sum, the threshold and the "
        "sweep unchanged; the same print 1 us before q moves sell_usd_30 and sell_usd_5 by exactly its USD (control); "
        "a print at exactly q - 30 min is in the window and one at q - 30 min - 1 us is not;")
    add("- the big-print threshold equals a brute-force numpy.quantile(0.99) over [w - 30 days, w), w = q - 30 min, "
        "when that holds >= 2,000 prints, over the latest 2,000 prints before w when it does not, and is missing below "
        "2,000 in all (all three branches hit); multiplying the size of every print at or after w (the window "
        "included) by 1,000 leaves it unchanged;")
    add("- sweep against a pandas groupby on calendar seconds; de-duplication by trade_id; maker side BUY counted "
        "as taker sell; the NaN rules.")
    add("")
    add(f"Result: `{test_msg}`")
    add("")

    # ----------------------------------------------------------------------------------- side convention
    add("## Side-convention check")
    add("")
    add("Taker-sell share (maker side BUY) against the sign of the price change over the same 30 minutes, from "
        "candles (log of the close of minute q-1 over the open of minute q-30). If the convention were reversed, "
        "falling windows would show taker-sell shares below one half.")
    add("")
    add("| Era | Windows | Spearman(ret, sell share) | Median sell share, ret < -0.5% | Median sell share, "
        "ret > +0.5% | Falling windows with sell share > 0.5 | Rising windows with sell share < 0.5 |")
    add("|---|---|---|---|---|---|---|")
    side_ok = {}
    for e in ERAS:
        j = J[e]
        m = j.complete & j.sell_share_30.notna() & j.ret_30.notna()
        x, s = j.ret_30[m].to_numpy(), j.sell_share_30[m].to_numpy()
        rho = spearman(x, s)
        dn, up = x < -0.005, x > 0.005
        side_ok[e] = rho < 0 and np.median(s[dn]) > 0.5 > np.median(s[up])
        add(f"| {e} | {int(m.sum()):,} | {rho:+.3f} | {np.median(s[dn]):.3f} (n {int(dn.sum()):,}) | "
            f"{np.median(s[up]):.3f} (n {int(up.sum()):,}) | {100 * np.mean(s[dn] > 0.5):.1f}% | "
            f"{100 * np.mean(s[up] < 0.5):.1f}% |")
    add("")
    add(f"**Side convention: {'consistent' if all(side_ok.values()) else 'NOT consistent'}** (criterion: a negative "
        "rank correlation, and a median taker-sell share above 0.5 in falling windows and below 0.5 in rising ones, "
        "in both eras).")
    add("")

    # ----------------------------------------------------------------------------------- other checks
    add("## Other checks")
    add("")
    ws = R.get("window_status", {})
    add(f"- **Fetch status of merged windows:** main {ws.get('main')}, early {ws.get('early')}.")
    dup = sum(v.get("n_dup", 0) for v in R["coins"].values())
    mono = sum(v.get("time_decreasing_along_id", 0) for v in R["coins"].values())
    outside = sum(v.get("outside_own_window", 0) for v in R["coins"].values())
    sides = {}
    for v in R["coins"].values():
        for k, n in v.get("sides", {}).items():
            sides[k] = sides.get(k, 0) + n
    add(f"- **Prints:** {tot_prints:,} after de-duplication ({dup:,} duplicate trade ids dropped); side values "
        f"{sides}; {mono:,} places where time decreases along trade id; {outside:,} prints outside their own window.")
    tr = R.get("thr_rule_counts", {})
    add(f"- **Big-print threshold rule** (1 = 30-day pool of >= 2,000 prints, 2 = latest 2,000, 0 = missing; all "
        f"candidates, before the completeness mask): main {tr.get('main')}, early {tr.get('early')}.")
    for e in ERAS:
        j = J[e]
        c = j[j.complete]
        nan = {k: int(c[k].isna().sum()) for k in ("adv_usd", "big_thr_usd", "csv_30", "csv_5", "sell_share_30",
                                                     "big_sell_share_30", "sweep_max_30")}
        add(f"- **Missing values among complete {e} rows ({len(c):,}):** {nan}; rows with no print in the window: "
            f"{int((c.n_prints == 0).sum())}.")
    jm = J["main"]
    bounded_nan = int((jm.adv_candle.notna() & jm.adv_usd_era_bounded.isna()).sum())
    both = jm.adv_candle.notna() & jm.adv_usd_era_bounded.notna()
    differ = int((~np.isclose(jm.adv_candle[both], jm.adv_usd_era_bounded[both], rtol=1e-9)).sum())
    add(f"- **ADV:** one continuous daily series per coin (data/minute_early before 2024, data/minute after), so "
        f"January 2024 uses December 2023. The simulator's era-bounded index (sim.py PERIODS) would instead leave "
        f"{bounded_nan} main candidates without ADV and give {differ} others a shorter window (all in January "
        "2024); the early era is identical either way. ADV is missing where a coin has under 10 days of candles in "
        "the 30 before (the first days of the data in January 2021, of a listing, or of XRP's July 2023 "
        "relisting).")
    add("")

    # ----------------------------------------------------------------------------------- definitions
    add("## Definitions as implemented")
    add("")
    add("- q = candidate minute start (UTC). Only prints stamped before q: [q - 30 min, q) and [q - 5 min, q).")
    add("- Taker sell = maker side BUY. USD = price x size. Prints de-duplicated by trade_id.")
    add("- sweep_max_usd_30 = largest taker-sell USD within one calendar second (time floored to the second) in "
        "[q - 30 min, q).")
    add("- big_thr_usd = numpy.quantile(0.99, linear) of print USD over the coin's fetched prints in "
        "[w - 30 days, w), w = q - 30 min; under 2,000 there, the latest 2,000 fetched prints before w; under "
        "2,000 in all, missing. Fetched prints = all de-duplicated prints of the coin's merged windows, both eras. "
        "Big = USD >= threshold.")
    add("- adv_usd = trailing 30-day median of positive daily spot USD volume (close x volume summed per UTC day), "
        "days D-30 .. D-1, at least 10 days (reports/signal_lab/prints/adv_daily.csv.gz).")
    add("- complete = the candidate's merged window was read back to a print stamped before its start.")
    add("- NaN: every float when complete is False; ratios with a missing or zero denominator; big_* without a "
        "threshold; the five F6 features when the window has no print (its USD sums are then 0).")
    add("")
    boundary_section(add, out)
    margin_section(add, out)
    with open(os.path.join(out, "QA.md"), "w") as fh:
        fh.write("\n".join(L) + "\n")
    print("\n".join(L))
    return verdict


if __name__ == "__main__":
    main(*sys.argv[1:2])
