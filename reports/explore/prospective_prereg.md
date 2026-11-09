# Explore v1, prospective test: a deeper ladder read on new data — pre-registration (Nov 9 2026)

Written after the explore v1 holdout read, before any of the data it will be read on exists. Branch explore/v1.

## Why
- **Geometry held in all three eras.** In the post-hoc panel (posthoc_panel.txt), it was the only family whose variants
  beat the incumbent in all three eras. 79 of 4,691 variants did; most were ladders with more or deeper rungs.
- **The mechanism is visible.** Deeper fills earned the most per dollar in every era: the 8-sigma rung made 74 / 113 /
  141 bp (selection / check / 2022-23), against about 30 bp at 4 sigma (posthoc_attr.txt).
- **The candidates were chosen with all three eras in view.** So only new data can test them.

## Candidates (frozen now; xsim specs, every other setting at the incumbent)
- **G1:** rungs at 4, 5, 7 and 10 sigma, in equal parts: `{"rungs": {"4.0": 1, "5.0": 1, "7.0": 1, "10.0": 1}}`.
  - Record: ΔSharpe +0.14 / +0.26 / +0.14, blended $250K (selection / check / 2022-23).
- **G2:** the frozen "Best geometry" finalist. Rungs at 4, 5, 6, 8, 10 and 12 sigma, weights (k/4)^0.5 (finalists.json).
  - Record: +0.21 / +0.00 / +0.41.
- **References:**
  - the incumbent: 4/6/8 sigma in thirds;
  - W2: 4/6/8 at 1:1:2, already a paper book. Record: +0.05 / +0.16 / +0.24.

## Data and read
- **New era:** Nov 10 2026 to Mar 31 2027.
- **AI signals:** the same walk-forward pipeline, with its quarterly retraining rule (scripts/wick1m/trades.py on the
  extended data).
- **Precompute:** scripts/explore/precompute_x.py, rebuilt for the new period.
- **Simulator:** xsim at this commit. The only allowed change is adding the new era's dates.
- **Read once,** on or after Apr 7 2027.

## Measures and decision
- **Primary:** blended ΔSharpe against the incumbent at $250K, as in explore v1.
- **Secondary:**
  - minute-mode ΔSharpe at $250K;
  - blended ΔSharpe at $1M;
  - daily and marked-to-market max drawdown, and the worst day.
- **The lead holds if G1 or G2 has all of:**
  - primary ΔSharpe > 0;
  - minute-mode ΔSharpe >= 0;
  - drawdowns and worst day no worse than 1.1x the incumbent's.
- **If the lead holds:**
  - the spot engine gets a configurable depth list (the deeper rungs are fixed at 6 and 8 sigma today), with parity and
    fault tests;
  - the better of G1 / G2 opens as a paper book;
  - no live change follows from this test.
- **If not,** the geometry lead closes. W2 continues under its own forward rules.
- **Reported for information:** the event-cluster bootstrap p of the vol-matched difference.

## Power, stated before the read
- **Noise:** the vol-matched daily difference between G2 and the incumbent had a standard deviation of 0.36-0.58
  across the three eras, about 0.43 on average. Over the roughly 141 days of the read, that makes the standard error
  of the Sharpe difference about 0.69.
- **What a sign can show:**
  - If the true gain is +0.2, the read shows a positive sign about 61% of the time (about 68% after a full year).
  - If the true gain is 0, it shows one 50% of the time.
- **So this is a sign check that keeps a lead open or closes it, not proof.** No significance bar is set, because none
  could be met. Confirming +0.2 at t = 2 would take more than a decade of data. Decisions on gains this small rest on
  the mechanism and on consistency across eras.
