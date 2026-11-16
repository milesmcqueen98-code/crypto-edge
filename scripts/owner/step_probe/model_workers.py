"""What would W workers have done on the step probe's recorded requests? An expectation, not a measurement.

Run: python scripts/owner/step_probe/model_workers.py --runs reports/owner/step_probe/run1 reports/owner/step_probe/run2
         --out reports/owner/step_probe/read
Writes model_workers.md and model_workers.csv. Standard library only. Decides nothing."""
import argparse
import csv
import os
import sys

PACE = 1.0 / 7.0
FLOOR = 0.005
LAST_SEND_CAP = 0.05
SORTED_NOTE = "Percentiles: sort the values and take index int(p * (n - 1))."
HEAD = [
    "# Model: what would W workers have done on the recorded requests of the standard pass?",
    "",
    "This is an expectation made from recorded requests, not a measurement of the engine with workers.",
    "",
    "1. Each call's own time (net) is its recorded dur_s minus the wait for the pace of 1/7 s after the previous send (floor 0.005 s).",
    "2. One after another: each call starts at the later of the previous end and the previous start plus 1/7 s; the pass ends at the last end.",
    "3. W workers: calls are handed out in order; a call starts at the later of the earliest free worker and the previous start plus 1/7 s.",
    "4. A pass is the standard-pass rows of one q with a non-empty dur_s, in the order of place (ties by sent_s).",
    "",
    SORTED_NOTE,
    "",
]


def pct(values, p):
    s = sorted(values)
    return s[int(p * (len(s) - 1))]


def mean(values):
    return sum(values) / len(values)


def nets(durs, pages):
    """Each call's own time without its pace wait."""
    out = []
    for i, d in enumerate(durs):
        if i == 0:
            out.append(d)
            continue
        since = out[i - 1] if pages[i - 1] == 1 else min(out[i - 1], LAST_SEND_CAP)
        wait = max(0.0, PACE - since)
        out.append(max(FLOOR, d - wait))
    return out


def one_after_another(net):
    """Length of the pass when each call starts at the later of the previous end and previous start + 1/7 s."""
    start = 0.0
    end = net[0]
    for i in range(1, len(net)):
        start = max(end, start + PACE)
        end = start + net[i]
    return end


def workers(net, w):
    """Length of the pass with w workers, calls handed out in order, starts spaced by the pace."""
    free = [0.0] * w
    prev_start = None
    latest = 0.0
    for n in net:
        k = min(range(w), key=lambda j: free[j])
        start = free[k] if prev_start is None else max(free[k], prev_start + PACE)
        end = start + n
        free[k] = end
        prev_start = start
        latest = max(latest, end)
    return latest


def to_float(s):
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def load_passes(run_dir):
    """Standard-pass rows with a non-empty dur_s, grouped by q: list of (rows) in place / sent_s order."""
    groups = {}
    with open(os.path.join(run_dir, "calls.csv"), newline="") as f:
        for r in csv.DictReader(f):
            if r.get("pass") != "standard":
                continue
            d = to_float((r.get("dur_s") or "").strip())
            if d is None:
                continue
            groups.setdefault(r["q"], []).append(
                (int(r["place"]), to_float(r.get("sent_s")) or 0.0, d, int(r["pages"]), r["coin"]))
    out = []
    for q in sorted(groups):
        rows = sorted(groups[q], key=lambda x: (x[0], x[1]))
        out.append(rows)
    return out


def stats_row(vals):
    return [mean(vals), pct(vals, 0.5), pct(vals, 0.75), pct(vals, 0.9), pct(vals, 0.95), pct(vals, 0.99),
            max(vals), 100.0 * sum(1 for v in vals if v > 6) / len(vals),
            100.0 * sum(1 for v in vals if v > 8) / len(vals)]


def analyse(run_dir):
    passes = load_passes(run_dir)
    rec, m1, m2, m3, m4 = [], [], [], [], []
    other_net = []
    for rows in passes:
        durs = [r[2] for r in rows]
        pages = [r[3] for r in rows]
        net = nets(durs, pages)
        rec.append(sum(durs))
        m1.append(one_after_another(net))
        m2.append(workers(net, 2))
        m3.append(workers(net, 3))
        m4.append(workers(net, 4))
        other_net.extend(n for n, r in zip(net, rows) if r[4] != "BTC")
    err = [a - b for a, b in zip(m1, rec)]
    gain = [a - b for a, b in zip(rec, m3)]
    k = len(other_net)
    return {
        "passes": len(passes),
        "lines": [("recorded (sum of the calls)", stats_row(rec)), ("model, one after another", stats_row(m1)),
                  ("model, 2 workers", stats_row(m2)), ("model, 3 workers", stats_row(m3)),
                  ("model, 4 workers", stats_row(m4))],
        "err": [pct(err, 0.5), mean(err), max(abs(e) for e in err)],
        "gain": [mean(gain), pct(gain, 0.5), pct(gain, 0.75), pct(gain, 0.9), pct(gain, 0.99)],
        "net_calls": k,
        "net_shares": [100.0 * sum(1 for n in other_net if n > PACE) / k,
                       100.0 * sum(1 for n in other_net if n > 0.5) / k,
                       100.0 * sum(1 for n in other_net if n >= 3) / k],
    }


STAT_COLS = ["mean", "median", "p75", "p90", "p95", "p99", "longest", "pct_over_6s", "pct_over_8s"]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", nargs="+", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    md = list(HEAD)
    csv_rows = [["run", "line"] + STAT_COLS]
    for run in a.runs:
        name = os.path.basename(os.path.normpath(run))
        res = analyse(run)
        md.append(f"## run {name}")
        md.append("")
        md.append(f"Passes: {res['passes']}")
        md.append("")
        md.append("| line | mean s | median s | 75th s | 90th s | 95th s | 99th s | longest s | over 6 s % | over 8 s % |")
        md.append("|---|---|---|---|---|---|---|---|---|---|")
        for label, st in res["lines"]:
            md.append(f"| {label} | " + " | ".join(f"{v:.2f}" for v in st[:7]) + f" | {st[7]:.1f} | {st[8]:.1f} |")
            csv_rows.append([name, label] + [f"{v:.4f}" for v in st])
        e, g, s = res["err"], res["gain"], res["net_shares"]
        md.append("")
        md.append(f"Model error with one worker (model minus recorded), per pass: median {e[0]:.3f} s, mean {e[1]:.3f} s, "
                  f"largest absolute value {e[2]:.3f} s.")
        md.append("")
        md.append(f"Gain of three workers per pass (recorded minus 3-worker model): mean {g[0]:.2f} s, median {g[1]:.2f} s, "
                  f"75th {g[2]:.2f} s, 90th {g[3]:.2f} s, 99th {g[4]:.2f} s.")
        md.append("")
        md.append(f"Calls of the coins other than BTC ({res['net_calls']} calls): net over 1/7 s {s[0]:.2f}%, "
                  f"net over 0.5 s {s[1]:.2f}%, net 3 s or more {s[2]:.2f}%.")
        md.append("")
        csv_rows.append([name, "one-worker error median/mean/maxabs"] + [f"{v:.4f}" for v in e])
        csv_rows.append([name, "gain of three workers mean/median/p75/p90/p99"] + [f"{v:.4f}" for v in g])
        csv_rows.append([name, "other coins net share over 1/7 s, over 0.5 s, 3 s or more (%)"] + [f"{v:.4f}" for v in s])
    os.makedirs(a.out, exist_ok=True)
    with open(os.path.join(a.out, "model_workers.md"), "w") as f:
        f.write("\n".join(md) + "\n")
    with open(os.path.join(a.out, "model_workers.csv"), "w", newline="") as f:
        csv.writer(f).writerows(csv_rows)
    return 0


if __name__ == "__main__":
    sys.exit(main())
