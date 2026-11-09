#!/usr/bin/env python3
"""Signal lab 2 (reports/signal_lab/prospective_prereg.md, deviation 1): the three readings, in the registered order.

  python scripts/signal_lab/test2.py a     selection reading (no lock): the early export with the print features (the
                                           history rows of RF6H), then RF0, RF6, RF6H, RF6M and RF6HM with the five
                                           seed triples, frozen simulator, walk-forward stopped at 2026Q1, selection era
                                           only -> test2/dose_seeds_sel_main.csv, test2/selection.txt
  python scripts/signal_lab/test2.py b     holdout reading (LOCKED): the same over the whole walk-forward, every era
                                           (2022-23: RF0, RF6, RF6M; RF6H is RF6 there) -> test2/seeded.txt
  python scripts/signal_lab/test2.py c     binding test (LOCKED): 15-seed chains (main: RF0, RF6, RF6H with the twin
                                           RF0H; 2022-23: RF0, RF6), each also with every non-candidate minute armed;
                                           the engine-faithful cells, the armed and frozen-simulator sensitivity cells,
                                           and the report -> test2/holdout.txt, test2/sensitivity.csv
  options: --dry (print the commands only), and for validation runs --f6 DIR, --out DIR, --tag NAME (passed to
  model.py; --out also to score.py)

b and c stop unless reports/signal_lab/test2/AUDIT_PASSED exists (created by the orchestrator after the look-ahead
audit). Every step runs alone (one lab-loading process at a time; the scorer never beside a chain); a failed step stops
the driver. Logs: <out>/logs/.
"""
import os
import subprocess
import sys
import time

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import lab2  # noqa: E402

PY = sys.executable
MODEL, SCORE = os.path.join(HERE, "model.py"), os.path.join(HERE, "score.py")
SPECS_MAIN = ["RF0", "RF6", "RF6H", "RF6M", "RF6HM"]
SPECS_EARLY = ["RF0", "RF6", "RF6M"]                        # in 2022-23 RF6H is RF6 and RF6HM is RF6M
SAME_EARLY = {"RF6H": "RF6", "RF6HM": "RF6M"}
CFGS = ["S_0.5", "S_0.25", "cap_1M", "base_0.5"]


def options():
    opt, rest, it = {"dry": False}, [], iter(sys.argv[1:])
    for a in it:
        if a == "--dry":
            opt["dry"] = True
        elif a in ("--f6", "--out", "--tag"):
            opt[a[2:]] = next(it)
        else:
            rest.append(a)
    if len(rest) != 1 or rest[0] not in ("a", "b", "c"):
        raise SystemExit(__doc__)
    return rest[0], opt


def model_args(opt, out):
    """model.py always writes to this test's folder (never the first lab's reports/signal_lab)."""
    return ["--out", out] + sum(([f"--{k}", opt[k]] for k in ("f6", "tag") if k in opt), [])


def run(cmds, opt, out):
    if not opt["dry"]:
        os.makedirs(os.path.join(out, "logs"), exist_ok=True)
    for name, cmd in cmds:
        print("$ " + " ".join(os.path.relpath(c, lab2.ROOT) if os.path.isabs(c) and c.startswith(lab2.ROOT) else c
                              for c in cmd), flush=True)
        if opt["dry"]:
            continue
        t0 = time.time()
        with open(os.path.join(out, "logs", f"{name}.log"), "w") as log:
            p = subprocess.run(cmd, cwd=lab2.ROOT, stdout=log, stderr=subprocess.STDOUT)
        print(f"  {name}: exit {p.returncode} ({time.time() - t0:.0f}s; log {os.path.join(out, 'logs', name + '.log')})",
              flush=True)
        if p.returncode != 0:
            raise SystemExit(f"step {name} failed; see its log")


def seed_table(path, era_map=None):
    """Per spec and era: each triple's Sharpe minus RF0's with the same triple; mean, SD and positive count."""
    D = pd.read_csv(path)
    inc = D[D.spec == "RF0"].set_index(["seeds", "era"]).sharpe
    D = D[D.spec != "RF0"].copy()
    D["d"] = D.sharpe - inc.reindex(pd.MultiIndex.from_frame(D[["seeds", "era"]])).to_numpy()
    rows = []
    for (spec, era), g in D.groupby(["spec", "era"], sort=False):
        rows.append(dict(spec=spec, era=era, triples=len(g), d_mean=g.d.mean(), d_sd=g.d.std(ddof=1),
                         d_min=g.d.min(), d_max=g.d.max(), positive=int((g.d > 0).sum()), sharpe_mean=g.sharpe.mean(),
                         inc_mean=float(inc.xs(era, level="era").mean())))
    R = pd.DataFrame(rows)
    for a, b in (era_map or {}).items():                  # 2022-23: an H spec is its non-H twin
        x = R[R.spec == b].copy()
        x["spec"] = a
        R = pd.concat([R, x], ignore_index=True)
    return R


def write_summary(R, out, name, title):
    R.to_csv(os.path.join(out, f"{name}.csv"), index=False)
    lines = [title, "", "ΔSharpe against RF0 with the same seed triple (frozen simulator, S* theta 0.5, $250K): mean, SD "
             "across the five triples, range, triples positive; mean Sharpe of the arm and of RF0", ""]
    for era in [e for e in ("sel", "chk", "early") if e in set(R.era)]:
        lines += [f"== {era}", R[R.era == era].drop(columns="era").set_index("spec").reindex(
            [s for s in SPECS_MAIN if s != "RF0" and s in set(R[R.era == era].spec)]).round(3).to_string(), ""]
    txt = "\n".join(lines)
    open(os.path.join(out, f"{name}.txt"), "w").write(txt)
    print(txt)


def main():
    step, opt = options()
    out = os.path.abspath(opt.get("out", lab2.T2))
    if step in ("b", "c") and not opt["dry"]:
        lab2.check_lock(f"test2.py {step}")
    ma, so = model_args(opt, out), ["--out", out]
    if step == "a":
        run([("a1_export_early", [PY, MODEL, "early", "export"] + ma),
             ("a2_seeds_sel_main", [PY, MODEL, "main", "doseseeds", "--sel", "--seeds", "triples"] + ma + SPECS_MAIN)],
            opt, out)
        if not opt["dry"]:
            write_summary(seed_table(os.path.join(out, "dose_seeds_sel_main.csv")), out, "selection",
                          "Signal lab 2, selection reading (walk-forward stopped at 2026Q1; selection era only)")
    elif step == "b":
        run([("b1_seeds_main", [PY, MODEL, "main", "doseseeds", "--seeds", "triples"] + ma + SPECS_MAIN),
             ("b2_seeds_early", [PY, MODEL, "early", "doseseeds", "--seeds", "triples"] + ma + SPECS_EARLY)], opt, out)
        if not opt["dry"]:
            R = pd.concat([seed_table(os.path.join(out, "dose_seeds_main.csv")),
                           seed_table(os.path.join(out, "dose_seeds_early.csv"), SAME_EARLY)], ignore_index=True)
            write_summary(R, out, "seeded", "Signal lab 2, seed-averaged holdout reading (whole walk-forward; in "
                          "2022-23 RF6H is RF6 and RF6HM is RF6M)")
    else:
        sc = so + ["--t2"] + (["--suffix", f"_u15_{opt['tag']}"] if "tag" in opt else [])
        cmds = [("c1_chain_main", [PY, MODEL, "main", "chain", "--seeds", "u15", "--armed"] + ma + ["RF0", "RF6", "RF6H"]),
                ("c2_chain_early", [PY, MODEL, "early", "chain", "--seeds", "u15", "--armed"] + ma + ["RF0", "RF6"])]
        for b in ("RF0", "RF6", "RF6H"):
            cmds.append((f"c3_cells_{b}", [PY, SCORE, "cells", b] + CFGS + sc))
        for b in ("RF0", "RF6", "RF6H"):
            cmds.append((f"c4_cells_{b}_armed", [PY, SCORE, "cells", f"{b}_armed", "S_0.5"] + sc))
            cmds.append((f"c5_cells_{b}_frozen", [PY, SCORE, "cells", b, "frozen"] + sc))
        cmds.append(("c6_report", [PY, SCORE, "report"] + sc))
        run(cmds, opt, out)


if __name__ == "__main__":
    main()
