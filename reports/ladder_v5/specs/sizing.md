# Builder spec: sizing (C2a, C2b, C6) — branch ladder/sizing

Read BUILDER_GUIDE.md and reports/ladder_v5_prereg.md first. Three pre-registered trials, logged in this order with
`gates.run` under these names: C2a_margin_terciles, C2b_drop_bottom, C6_stress. All use hsim's `size_fn` hook: `hsim.book(..., size_fn=f)` where `f(margin, i)` returns the
size multiplier for minute index i of the panel (`pan[0][i]` is that minute's timestamp) and margin = the AI's
prediction minus that quarter's threshold. The multiplier scales the whole ladder of a signal: the 4-sigma hold every
minute (from that minute's margin) and the 6/8-sigma rungs (from the margin at the parent's fill). It does not change
the 0.2%-of-ADV and 25%-of-capital caps' definition: it multiplies the capped size.

## C2: meta-label sizing from the AI's margin (López de Prado's bet sizing on the primary model's confidence)
- Diagnosis (selection era only): net bp per $ rises with the margin, quintiles -4 / 15 / 19 / 52 / 125 bp, Spearman
  +0.34, inside every rung.
- Cutoffs: the 1/3 and 2/3 quantiles of the margins (pred - thr) of all parent fills in the era's trade list
  (reports/wick1m/trades_<main|early>.parquet) whose `ts` is before the start of the current calendar quarter.
  Fewer than 60 such fills: multiplier 1.0. Recomputed each quarter. (Main era: 2025Q1 has no earlier fills, so 1.0.)
- **C2a** (path "return"): multiplier 0.5 below the lower cutoff, 1.0 between, 1.5 at or above the upper cutoff.
- **C2b** (path "sharpe"): 0 below the lower cutoff (no bid), 1.0 otherwise.

## C6: stress sizing (Nagel's evaporating liquidity; Grossman-Miller's price of immediacy)
- Stress at minute t, known at t-1: BTC's 60-minute standard deviation of 1-minute log returns divided by its
  4,320-minute standard deviation (at least 1,440 minutes), both ending at t-1 — edge/wick.py's btc_vol_ratio, from
  data/minute/BTC.parquet (main) and data/minute_early/BTC.parquet (early), aligned to the panel's minutes.
- **C6** (path "return"): multiplier 1.5 when stress >= 2.0, else 1.0. Prior: weak (selection-era markouts by BTC's
  15-minute move were U-shaped; by cascade breadth not monotone).

## Report
reports/ladder_v5/sizing/REPORT.md: the off-switch check (size_fn returning 1.0 reproduces the incumbent exactly), the
quarterly cutoffs used, the share of fills in each size bucket by era, the gate tables, and what drives the result
(cash: bigger bids hold more cash, which the live rule can make worse in cascades — report hsim's parent_unfunded and
deep_filled counts against the incumbent's).
