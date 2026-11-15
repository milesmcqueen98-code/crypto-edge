#!/usr/bin/env python3
"""Live order timing study, part 3 (reports/owner/timing_prereg.md on main: "Part 3: the live bot as built and each
stage of the rebuild" and "Part 3, deviation 1"): the twelve part 3 policies next to the six of parts 1 and 2, by the
method of parts 1 and 2, unchanged.

Steps, all into <out_dir> (never over the files of parts 1 and 2):
  1. evaluate.main with the eighteen policies (the six, then POLICIES3 in the plan's order): policies.csv (every
     policy against P0 and against P1, S1 of part 1: first-order P&L), entry_by_seconds.csv, p0_fill_times.csv,
     p0_vs_research.csv, parents.csv.gz, minute_flags.csv.gz;
  2. part2.run_s1 (moves.csv, removed_top_p1.csv, s1.csv, s1_check.csv): S1 of part 2, every parent on its 4-sigma
     rung alone; the moves table;
  3. part2_s2.run (s2.csv, s2_check.csv, s2_rowcheck.csv, s2_parents.csv.gz): S2, the whole ladder, deep prints;
  4. regression_check.csv: every row of the six policies of parts 1 and 2 against the files on record
     (reports/owner/timing), as written (text), per file;
  5. summary.csv: per era and policy, the times, parents, the share of P0's parents caught in the same minute and
     within two minutes (moves.csv share_pm0 and share_pm2: a P0 parent counts when the policy has a parent in the same
     coin whose minute is at most 0, or 2, minutes away, either side; not one to one), the fills on the carried bid
     (stale and kept) and on the new bid, and the P&L differences against P0 and P1 (part 1's first order, S1, S2).
Pairs of the tables: every policy against P0, every policy but P0 and P1 against P1. No rule is applied (part 3 has
no gate); the s1_rule / s2_rule files of parts 1 and 2 are not written.
--dry: the six policies plus dry-run policies whose new-bid times are among the six old starts (part 3's own times
need the fifteen-start rows of rederive_runner.py), for a run end to end on the rows on file.
usage: python scripts/owner/timing/part3.py <scratch_dir> <derived_dir> <pattern> <deep_all.parquet> <out_dir> [--dry]
  pattern: derived3_*.parquet (part 3's rows) or derived_*.parquet (the six-start rows)
"""
import os
import sys
import time

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import evaluate as EV  # noqa: E402
import part2 as P2  # noqa: E402
import part2_s2  # noqa: E402

RECORD = os.path.join(EV.ROOT, "reports", "owner", "timing")
OLD = list(EV.POLICIES)
OLD_PAIRS = list(P2.PAIRS)
# dry run only: new-bid times among the six old starts, cancel times anywhere, with and without a carried bid
DRY = {"dB2": (9300.0, 10000), "dB2r": (9630.0, 10000), "dB0": (14250.0, 15000), "dB4": (1100.0, 1300),
       "dN1": (0.0, 10000, False), "dN3": (0.0, 7500, False), "dN4": (0.0, 1300, False)}


def policy_set(dry):
    pols = dict(EV.POLICIES)
    pols.update(DRY if dry else EV.POLICIES3)
    return pols


def pairs_of(names):
    return [(p, "P0") for p in names if p != "P0"] + [(p, "P1") for p in names if p not in ("P0", "P1")]


# ------------------------------------------------------------------------------------------------ regression
KEYED = {"policies.csv": ["era", "policy", "vs"], "entry_by_seconds.csv": ["era", "policy", "vs", "src", "seconds"],
         "moves.csv": ["era", "policy", "vs"], "s1.csv": ["val", "era", "policy", "vs"],
         "s2.csv": ["val", "era", "policy", "vs"]}
WHOLE = ["p0_fill_times.csv", "p0_vs_research.csv", "removed_top_p1.csv", "s1_check.csv", "s2_check.csv",
         "s2_rowcheck.csv"]
ORDERED = ["parents.csv.gz", "s2_parents.csv.gz"]


def read_txt(path):
    return pd.read_csv(path, dtype=str, keep_default_na=False)


def regression(out, record=RECORD):
    """The six policies' rows against the files on record, compared as written (text)."""
    rows = []
    for f, key in KEYED.items():
        A, B = read_txt(os.path.join(record, f)), read_txt(os.path.join(out, f))
        if "vs" in key and f in ("s1.csv", "s2.csv"):
            B = B[[(p, v) in OLD_PAIRS for p, v in zip(B.policy, B.vs)]]
        else:
            B = B[B.policy.isin(OLD)]
        assert list(A.columns) == list(B.columns), f
        a = {tuple(r[k] for k in key): tuple(r.values()) for r in A.to_dict("records")}
        b = {tuple(r[k] for k in key): tuple(r.values()) for r in B.to_dict("records")}
        diff = sum(1 for k in a if k in b and a[k] != b[k])
        rows.append(dict(file=f, rows_record=len(a), rows_part3=len(b), missing=len(set(a) - set(b)),
                         extra=len(set(b) - set(a)), differing=diff))
    for f in WHOLE:
        A, B = read_txt(os.path.join(record, f)), read_txt(os.path.join(out, f))
        same = A.shape == B.shape and list(A.columns) == list(B.columns) and (A.values == B.values).all()
        rows.append(dict(file=f, rows_record=len(A), rows_part3=len(B), missing=max(len(A) - len(B), 0),
                         extra=max(len(B) - len(A), 0), differing=0 if same else int(max(len(A), len(B)))))
    for f in ORDERED:
        A, B = read_txt(os.path.join(record, f)), read_txt(os.path.join(out, f))
        B = B[B.policy.isin(OLD)].reset_index(drop=True)
        n = min(len(A), len(B))
        diff = int((A.iloc[:n].values != B.iloc[:n].values).any(axis=1).sum()) if list(A.columns) == list(B.columns) \
            else n
        rows.append(dict(file=f, rows_record=len(A), rows_part3=len(B), missing=max(len(A) - len(B), 0),
                         extra=max(len(B) - len(A), 0), differing=diff))
    R = pd.DataFrame(rows)
    R["identical"] = (R.missing == 0) & (R.extra == 0) & (R.differing == 0)
    return R


# ------------------------------------------------------------------------------------------------ summary
def summary(out, pols):
    T = pd.read_csv(os.path.join(out, "policies.csv"))
    M = pd.read_csv(os.path.join(out, "moves.csv"))
    S1 = pd.read_csv(os.path.join(out, "s1.csv"))
    S2 = pd.read_csv(os.path.join(out, "s2.csv"))
    rows = []
    for e in EV.ERAS:
        for p, v in pols.items():
            t0 = T[(T.era == e) & (T.policy == p) & (T.vs == "P0")].iloc[0]
            r = dict(era=e, policy=p, cancel_s=v[0] / 1000, new_bid_s=v[1] / 1000, carried_bid=EV.carries(v),
                     parents=int(t0.parents), p0_parents=int(t0.ref_parents),
                     stale_fills=int(t0.stale_fills), kept_fills=int(t0.kept_fills), new_fills=int(t0.new_fills))
            m = M[(M.era == e) & (M.policy == p)]
            r["same_minute_share"] = 1.0 if p == "P0" else float(m.share_pm0.iat[0])
            r["within_1min_share"] = 1.0 if p == "P0" else float(m.share_pm1.iat[0])
            r["within_2min_share"] = 1.0 if p == "P0" else float(m.share_pm2.iat[0])
            for ref in ("P0", "P1"):
                if p == ref or (ref == "P1" and p == "P0"):
                    continue
                t = T[(T.era == e) & (T.policy == p) & (T.vs == ref)].iloc[0]
                r[f"first_order_pct_vs_{ref}"] = float(t.dpnl_pct)
                for lab, X in (("s1", S1), ("s2", S2)):
                    x = X[(X.era == e) & (X.policy == p) & (X.vs == ref)].iloc[0]
                    r[f"{lab}_pct_vs_{ref}"] = float(x.dpnl_pct)
                    r[f"{lab}_dsharpe_vs_{ref}"] = float(x.dsharpe)
            for lab, X in (("s1", S1), ("s2", S2)):
                x = X[(X.era == e) & (X.vs == "P0") & (X.policy == (p if p != "P0" else "P1"))].iloc[0]
                r[f"{lab}_pnl_usd"] = float(x.pnl_policy if p != "P0" else x.pnl_ref)
            rows.append(r)
    for p, v in pols.items():                               # pooled P&L of S1 and S2 (sums over the three eras)
        r = dict(era="pooled", policy=p, cancel_s=v[0] / 1000, new_bid_s=v[1] / 1000, carried_bid=EV.carries(v))
        for ref in ("P0", "P1"):
            if p == ref or (ref == "P1" and p == "P0"):
                continue
            for lab, X in (("s1", S1), ("s2", S2)):
                r[f"{lab}_pct_vs_{ref}"] = float(X[(X.era == "pooled") & (X.policy == p) & (X.vs == ref)].dpnl_pct.iat[0])
        rows.append(r)
    return pd.DataFrame(rows)


def main(scr, ddir, pattern, deep, out, dry=False):
    t0 = time.time()
    os.makedirs(out, exist_ok=True)
    assert os.path.abspath(out) != os.path.abspath(RECORD)
    pols = policy_set(dry)
    names = list(pols)
    pairs = pairs_of(names)
    tm = {}
    EV.main(scr, ddir, policies=pols, out=out, flags_path=os.path.join(out, "minute_flags.csv.gz"), pattern=pattern)
    tm["evaluate"] = time.time() - t0
    P2.run_s1(scr, out=out, pols=names, pairs=pairs, with_rule=False)
    tm["s1"] = time.time() - t0 - sum(tm.values())
    part2_s2.run(scr, deep, out=out, pols=names, pairs=pairs, with_rule=False)
    tm["s2"] = time.time() - t0 - sum(tm.values())
    R = regression(out)
    R.to_csv(os.path.join(out, "regression_check.csv"), index=False)
    S = summary(out, pols)
    S.to_csv(os.path.join(out, "summary.csv"), index=False, float_format="%.6g")
    pd.set_option("display.width", 250)
    print(R.to_string(index=False))
    print(S.round(4).to_string(index=False))
    print("timings (s):", {k: round(v) for k, v in tm.items()}, f"total {time.time() - t0:.0f}s")
    print("six policies of parts 1 and 2 identical to the record:", bool(R.identical.all()))


if __name__ == "__main__":
    a = sys.argv[1:]
    main(*a[:5], dry="--dry" in a[5:])
