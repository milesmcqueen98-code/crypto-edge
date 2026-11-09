# Sizing lab (Nov 9 2026): is there a durable sizing edge for the R2-08 spot ladder?

**Result: no winner.**
- Both paper books (main, W2) keep flat sizing, and no new paper book is opened.
- Each family's best candidate lost Sharpe out of sample. None cleared +0.20 even in the selection era at $1M.
- Every candidate is rejected.

## Setup
- **Simulator:** scripts/wick_v4/rungs.py (the wick1m simulator), with an optional sizing hook. With no multiplier it
  reproduces the flat books exactly (reproduce.txt).
- **Conditions:**
  - spot-only capacity, theta 0.5, the 0.2% ADV cap, and the simulator's costs;
  - the main book (rungs 1/3 each) and the W2 book (1/4, 1/4, 1/2);
  - $250K and $1M.
- **Multiplier:**
  - Proportional to the bucket's shrunk mu / sigma^2, clipped to 0.5-1.5x, then ADV-capped. Guards set it to 0.
  - Capital is matched to flat on the selection era, then frozen.
- **Process:**
  - Pre-registered in prereg.md (commit 77e8763), before any candidate was run.
  - Frozen at 5f08f43. Check (Apr-Nov 5 2026) and 2022-23 were read once.
  - Event-cluster bootstrap with Holm correction.
  - Two holdout cells were re-derived with independent code and match to the third decimal.

## Selection era (Jan 2025 - Mar 2026)
Mean ΔSharpe against flat over the four cells (2 books x 2 capitals):

| Family | Candidate | Mean ΔSharpe | Note |
|---|---|---|---|
| A calendar | A1 day of week | -0.074 | |
| | **A2 Sunday 16-19 ET** | **+0.016** | finalist |
| | A3 CPI / FOMC days | -0.054 | |
| B predicted edge | B1 halves | +0.116 | |
| | **B2 terciles** | **+0.176** | finalist: +0.31 / +0.28 at $250K (main / W2), -0.00 / +0.12 at $1M |
| | B3 quintiles | +0.115 | |
| C guards | **C1 BTC still falling** | **-0.112** | finalist |
| | C2 coins filling at once | -0.594 | |
| | C3 vol regime | -1.132 | |

Every candidate was testable. Every variant is in variants.csv; bucket statistics are in buckets.csv.

## Holdout, read once
ΔSharpe against the baseline, main / W2:

| Finalist | $250K check | $250K 2022-23 | $1M check | $1M 2022-23 | Holm p |
|---|---|---|---|---|---|
| A2 Sunday 16-19 ET | -0.06 / -0.06 | -0.03 / -0.03 | -0.04 / -0.04 | +0.02 / +0.02 | 1.0 |
| B2 predicted-edge terciles | -0.25 / -0.30 | -0.25 / -0.28 | -0.21 / -0.30 | +0.02 / +0.03 | 1.0 |
| C1 BTC still falling | -0.90 / -1.13 | -0.96 / -1.18 | -1.13 / -1.44 | -1.33 / -1.50 | 1.0 |
| A2 on top of B2, against B2 | 0.00 / 0.00 | +0.01 / +0.02 | 0.00 / 0.00 | +0.02 / +0.02 | 1.0 |

- **Pooled check + 2022-23 at $250K:**
  - A2: -0.04 (p 0.99).
  - B2: -0.24 / -0.28 (p 0.96 / 0.98).
  - C1: -0.92 / -1.14.
- **No calendar year lost money for any candidate**, so test 4 was the only pass.

## Scorecard (rubric fixed in prereg.md)

| Candidate | Sharpe /20 | Capacity /15 | Consistency /10 | Evidence /15 | Spread /10 | Risk /15 | Mechanism /10 | Implementation /5 | **Total** | Verdict |
|---|---|---|---|---|---|---|---|---|---|---|
| B2 | 0 | 1.3 | 1.7 | 0 | 0 | 7.5 | 7 | 5 | **22.5** | reject |
| A2 | 0 | 4.2 | 0 | 0 | 0 | 5.75 | 4 | 5 | **19.0** | reject |
| C1 | 0 | 0 | 0 | 0 | 0 | 7.5 | 4 | 4 | **15.5** | reject |

## Why (post hoc, posthoc.txt; explanation only)
- **B, predicted edge: the in-sample pattern did not persist.**
  - The selection era's lowest tercile lost 3.9 bp per dollar. Out of sample it made +9.0 bp (check) and +13.4 bp
    (2022-23).
  - Its mu / sigma^2 beat the middle tercile in both holdout eras: 29.8 vs 11.9 and 20.8 vs 9.1 (x1e4).
  - The top tercile earns more, but with more spread.
  - Same lesson as ladder v6 and C2a: the AI's prediction ranks spread as well as return.
- **C1: the rungs it cancels are the best fills.**
  - Deeper rungs bought while BTC is still falling made 83 bp per dollar in check vs 30 for the rest, and 96 vs 88 in
    2022-23.
  - Cancelling them gives up the capitulation bounce. That is what the AI's features and wick v4's BTC-synchronised
    test already said.
- **C2, C3: the P&L lives in broad cascades and high-volatility regimes.**
  - C3's firing set made +63 bp per dollar in selection, against +6 for the rest.
  - Guarding against these cost 0.3-1.3 Sharpe even in-sample.
- **Calendar: no mean difference survived shrinkage.**
  - The between-bucket variance (tau^2) was 0 for all three, so the multipliers came from variance alone.
  - A2's selection gain was noise, and it reversed out of sample.
- **Capacity: sizing cannot add capacity while the 0.2% ADV cap binds.**
  - At $1M most signals sit at the cap, so a same-capital rule can mostly only shrink.
  - B2's mu / sigma^2 sizes collapsed to a step: x0.5 for the lowest tercile, x1.5 (capped) for the rest.
  - It still held only 0.90-0.95 of flat capital at $1M.
- **Test 6 ("beyond B") was nearly empty.** With the capital constant at its bound, A2 on top of B2 equals B2 except
  on signals without a B rank. A2 failed on its own anyway.

## Next test: capacity is in the cap, not in sizing
- **What to test:** re-test the cap level at $1M with print-priced exits.
  - The 0.2% ADV cap was chosen in the $1M round from 72 combinations, under the simulator's exit-cost model.
  - Ladder v5 measured market exits on Coinbase prints at 3-6 bp, against the model's 16-17 bp. Its implied impact
    constant was 0.19-0.39, against the model's 0.7.
- **Candidates:** 0.2%, 0.3% and 0.4% of ADV, with exits priced on prints (red team 2's PrintCost).
- **Procedure:** choose on the selection era, then read check and 2022-23 once, at this lab's bar: +0.20 Sharpe in
  every era, no worse drawdown (daily and marked to market), worst day or CVaR, leave-one-day-out, no losing year.
- **Watch:** the adverse selection by size that set the cap. Fills with the most volume through the bid lose.
- **If it wins:** a $1M paper book; theta from the pilot's live fills before money moves.
- **Information-only hint (not evidence):** B2 with multipliers allowed past the cap gained +0.15 to +0.27 at $1M in
  both holdout eras, where the capped version lost. That fits idle capital, not the sizing signal (info.csv).
- **Sizing itself:** three rounds (ladder v5 C2a, ladder v6 sizing, this lab) found no durable sizing edge. C2a's queued
  forward re-test keeps a weak prior: B2, its relative inside the cap, lost out of sample here.

## Files
- **Plan and inputs:**
  - prereg.md: the plan, with its deviation log (freeze, single read).
  - macro_days.csv: CPI and FOMC days, with sources.
  - reproduce.txt: the flat books, reproduced through the hook.
- **Selection era:**
  - variants.csv, buckets.csv and selection.txt: every candidate.
  - finalists.json: the frozen rules.
- **Holdout:**
  - holdout.txt: the summary. holdout_cells.csv, tests.csv, years.csv and info.csv are its tables.
  - scorecard.csv: the scores.
  - holdout_read.txt: the read-once marker.
- **posthoc.txt:** the diagnostics behind "Why".
- **Code:**
  - scripts/sizing_lab/: reproduce.py, lab.py, holdout.py, posthoc.py.
  - The hook: scripts/wick1m/sim.py (`mult`, `mult_cap`) and scripts/wick_v4/rungs.py (`run`).
