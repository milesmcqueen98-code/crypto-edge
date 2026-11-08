# Ladder v5 sizing: C2a, C2b, C6

Builder's report, returned as text (the subagent harness does not let builders write report files) and committed by
the coordinator. Branch ladder/sizing from the freeze commit 7ae53cb. Spec: reports/ladder_v5/specs/sizing.md. Code:
scripts/ladder_v5/cand_sizing.py. Trials (gates.run, logged in this order, one Actions job, run 42425353744):
reports/ladder_v5/trials.csv and trials/{C2a_margin_terciles,C2b_drop_bottom,C6_stress}.json. Diagnostics (not
trials, from the same runs): reports/ladder_v5/sizing/. No variant, threshold or configuration was run besides these.

## Result (S*, θ 0.5, declared path)

| Trial | Path | Pooled t (declared path) | Raw / vol-matched t | ΔSharpe sel / chk / early | G1 | G2 | G3 | G4 |
|---|---|---|---|---|---|---|---|---|
| C2a_margin_terciles | return | **+2.21** | +2.21 / +1.04 | +0.34 / −0.03 / +0.12 | pass | pass | pass | pass |
| C2b_drop_bottom | sharpe | **−0.41** | −1.61 / −0.41 | +0.18 / −0.46 / −0.36 | fail | fail | fail | pass |
| C6_stress | return | **−0.99** | −0.99 / −2.49 | −0.88 / −0.22 / −0.12 | fail | fail | fail | fail |

- **C2a passes G1-G4**; per the prereg, next are the independent red team and the joint re-test. Caveats: (1) it is
  mostly more return for more risk: vol-matched t +1.04 at S*, +0.38 at base; Sharpe falls in chk at S* (2.31 to
  2.28) and in chk and 2022-23 at base (2.61 to 2.42, 2.18 to 1.86); (2) the selection era, where the margin diagnosis
  was made, carries the pooled t (era t +1.81 / +0.38 / +1.30); chk and 2022-23 combined the same way give about +1.3
  (post hoc, not a gate); (3) the gain is all in the top tercile (below).
- **C2b and C6: reject.**
- Scorecard, automatic parts (scorecard.auto; manual parts left to the coordinator): C2a evidence 18, robustness 15
  (C2b has the opposite sign), prize 5 (mean ΔSharpe +0.14), capacity 5 ($1M ΔSharpe +0.31) = 43 of 65; C2b 0/3/0/0;
  C6 0/0/0/2.

## The rules as implemented
- All three are `hsim.book(..., size_fn=f)` on the frozen hsim and fsim; nothing else changes. `f(margin, i)`, margin
  = the panel's prediction minus the quarter's threshold at minute index i (float32, as hsim computes it). The frozen
  hook applies f to every armed coin's 4σ hold each minute and, at a parent fill, to the parent and its 6/8σ rungs
  (f at the fill minute). It multiplies the capped size (0.2% of ADV, 25% of capital).
- **C2 cutoffs**: per calendar quarter, `np.quantile(margins, [1/3, 2/3])` (numpy default, linear interpolation) over
  every row of reports/wick1m/trades_<main|early>.parquet with `ts` before the quarter's first minute (all AI-approved
  parent fills, including rows with bot = False), margin = pred − thr from the trade list. Under 60 such fills: ×1
  (main 2025Q1, early 2022Q1). C2a: ×0.5 if margin < lower, ×1.5 if margin ≥ upper, else ×1. C2b: ×0 (no bid) if
  margin < lower, else ×1.
- **C6 stress** at row t: edge/wick.py's `btc_vol_ratio` placed on row t (the value at t−1), on the lab's BTC closes
  (`wick_sim.load_ohlc`: zero-volume minutes dropped, close forward-filled up to 30 minutes) over the lab's span, sliced
  to the panel's minutes (grid equality asserted). ×1.5 if stress ≥ 2.0, else ×1; a minute without a value (800 of
  970,560 main, 380 of 1,051,200 early; no parent fill among them) gets ×1. Check: equal to the stored
  `btc_vol_ratio` in reports/wick_ai_candidates.parquet at all 4,833 overlapping 2025-26 minutes (max difference 0.0).
- Boundaries unit-tested before the run (margin one ulp below and at each cutoff on each quarter's first minute;
  stress at, below and NaN).

C2 cutoffs used (cutoffs.csv; margin in the model's prediction units):

| Quarter | Earlier fills | Lower | Upper | | Quarter | Earlier fills | Lower | Upper |
|---|---|---|---|---|---|---|---|---|
| 2025Q1 | 0 | ×1 | ×1 | | 2022Q1 | 0 | ×1 | ×1 |
| 2025Q2 | 307 | 18.11 | 54.35 | | 2022Q2 | 78 | 12.33 | 36.77 |
| 2025Q3 | 516 | 15.14 | 43.18 | | 2022Q3 | 201 | 14.27 | 43.52 |
| 2025Q4 | 646 | 14.05 | 38.68 | | 2022Q4 | 253 | 12.48 | 38.43 |
| 2026Q1 | 953 | 12.35 | 36.72 | | 2023Q1 | 347 | 13.37 | 43.09 |
| 2026Q2 | 1,155 | 12.56 | 37.36 | | 2023Q2 | 449 | 10.89 | 35.75 |
| 2026Q3 | 1,297 | 11.50 | 34.35 | | 2023Q3 | 526 | 10.45 | 31.39 |
| 2026Q4 | 1,402 | 11.37 | 33.03 | | 2023Q4 | 596 | 9.23 | 28.36 |

Share of parent fills and armed coin-minutes per bucket (bucket_shares.csv):

| Era | Parents | ×1 (<60 earlier) | Bottom | Middle | Top | Stress ≥ 2 | Armed coin-minutes bottom / middle / top / ×1 | Armed coin-minutes in stress | Minutes in stress |
|---|---|---|---|---|---|---|---|---|---|
| sel | 1,155 | 26.6% | 30.0% | 24.3% | 19.1% | 39.3% | 37.8 / 39.0 / 2.5 / 20.7% | 3.2% | 3.4% |
| chk | 412 | 0% | 44.4% | 38.8% | 16.7% | 30.3% | 37.4 / 57.3 / 5.2 / 0% | 3.2% | 3.6% |
| 2022-23 | 744 | 10.5% | 37.4% | 29.2% | 23.0% | 54.3% | 70.6 / 20.1 / 7.5 / 1.7% | 14.8% | 3.6% |

The cutoffs come from fills, but the multiplier also sizes every armed minute's 4σ hold, where margins are lower: the
top cutoff is reached in 2.5-7.5% of armed coin-minutes against 17-23% of fills. Stress covers 3-4% of minutes but
30-54% of fills.

## Off-switch check
`size_fn` returning 1.0 against the cached incumbent: local, chk at S* θ 0.5, max daily difference **0.0** (same
219-day index). On Actions before the trials, all three eras × four configurations: worst 1.9e-17 (float noise of the
runner; every day index identical).

## Gate tables
Return / Sharpe a year; mean difference in bp of capital a day (raw; vol-matched); era t (Newey-West, 5 lags).

**C2a_margin_terciles** (return)

| Config | Pooled t raw / vm | Era | Incumbent | Candidate | Mean diff | Era t |
|---|---|---|---|---|---|---|
| S_0.5 | +2.21 / +1.04 | sel | 19.5% / 2.31 | 22.4% / 2.65 | +0.82; +0.44 | +1.81 |
| | | chk | 15.1% / 2.31 | 15.7% / 2.28 | +0.17; −0.09 | +0.38 |
| | | early | 10.4% / 1.72 | 11.6% / 1.84 | +0.34; +0.15 | +1.30 |
| S_0.25 | +2.06 / +1.16 | sel | 16.2% / 1.96 | 18.6% / 2.23 | +0.66; +0.39 | +1.38 |
| | | chk | 13.1% / 1.98 | 14.2% / 2.05 | +0.30; +0.09 | +0.74 |
| | | early | 9.1% / 1.48 | 10.3% / 1.69 | +0.31; +0.16 | +1.37 |
| base_0.5 | +1.63 / +0.38 | sel | 22.4% / 2.16 | 25.6% / 2.65 | +0.86; +0.46 | +1.98 |
| | | chk | 17.6% / 2.61 | 18.3% / 2.42 | +0.19; −0.10 | +0.34 |
| | | early | 13.7% / 2.18 | 14.2% / 1.86 | +0.13; −0.09 | +0.42 |
| cap_1M | +3.04 / +1.62 | sel | 12.1% / 1.76 | 14.9% / 2.13 | +0.76; +0.40 | +2.59 |
| | | chk | 6.9% / 0.97 | 8.2% / 1.22 | +0.36; +0.16 | +1.16 |
| | | early | 4.7% / 0.55 | 5.5% / 0.87 | +0.21; +0.08 | +1.33 |

**C2b_drop_bottom** (sharpe: G1-G3 on the vol-matched difference)

| Config | Pooled t raw / vm | Era | Incumbent | Candidate | Mean diff | Era t |
|---|---|---|---|---|---|---|
| S_0.5 | −1.61 / −0.41 | sel | 19.5% / 2.31 | 19.7% / 2.49 | +0.07; +0.53 | +0.14 |
| | | chk | 15.1% / 2.31 | 12.2% / 1.86 | −0.78; −0.49 | −1.26 |
| | | early | 10.4% / 1.72 | 8.3% / 1.36 | −0.57; −0.38 | −1.98 |
| S_0.25 | −0.98 / +0.11 | sel | 16.2% / 1.96 | 17.1% / 2.23 | +0.24; +0.65 | +0.46 |
| | | chk | 13.1% / 1.98 | 11.0% / 1.63 | −0.59; −0.32 | −0.96 |
| | | early | 9.1% / 1.48 | 7.5% / 1.21 | −0.44; −0.26 | −1.56 |
| base_0.5 | −1.74 / +0.45 | sel | 22.4% / 2.16 | 21.7% / 2.50 | −0.19; +0.85 | −0.25 |
| | | chk | 17.6% / 2.61 | 14.9% / 2.37 | −0.74; −0.02 | −1.11 |
| | | early | 13.7% / 2.18 | 10.9% / 1.81 | −0.77; −0.24 | −2.16 |
| cap_1M | −1.30 / +0.60 | sel | 12.1% / 1.76 | 10.8% / 1.80 | −0.36; +0.21 | −0.91 |
| | | chk | 6.9% / 0.97 | 5.5% / 0.64 | −0.39; −0.09 | −0.91 |
| | | early | 4.7% / 0.55 | 4.3% / 0.39 | −0.12; +0.11 | −0.55 |

**C6_stress** (return)

| Config | Pooled t raw / vm | Era | Incumbent | Candidate | Mean diff | Era t |
|---|---|---|---|---|---|---|
| S_0.5 | −0.99 / −2.49 | sel | 19.5% / 2.31 | 14.2% / 1.44 | −1.43; −1.89 | −1.70 |
| | | chk | 15.1% / 2.31 | 14.8% / 2.10 | −0.06; −0.54 | −0.21 |
| | | early | 10.4% / 1.72 | 11.6% / 1.60 | +0.33; −0.04 | +1.42 |
| S_0.25 | −1.42 / −2.75 | sel | 16.2% / 1.96 | 10.4% / 0.93 | −1.57; −1.93 | −1.76 |
| | | chk | 13.1% / 1.98 | 12.2% / 1.67 | −0.24; −0.67 | −0.77 |
| | | early | 9.1% / 1.48 | 9.8% / 1.33 | +0.17; −0.17 | +0.75 |
| base_0.5 | −1.15 / −1.79 | sel | 22.4% / 2.16 | 15.3% / 1.33 | −1.96; −2.19 | −1.78 |
| | | chk | 17.6% / 2.61 | 17.9% / 2.61 | +0.08; −0.18 | +0.30 |
| | | early | 13.7% / 2.18 | 15.0% / 2.04 | +0.35; +0.12 | +1.60 |
| cap_1M | +1.98 / −1.00 | sel | 12.1% / 1.76 | 12.8% / 1.68 | +0.20; −0.32 | +0.72 |
| | | chk | 6.9% / 0.97 | 7.5% / 0.98 | +0.16; −0.14 | +0.48 |
| | | early | 4.7% / 0.55 | 5.9% / 0.85 | +0.31; +0.07 | +2.26 |

## What drives the result (S*, θ 0.5)

Net P&L by C2 bucket over each era, all rungs, minute/1-second blend: $K net (bought $M) [net bp per $]
(diag_bucket.csv):

| Era | Bucket | Parents | Incumbent | C2a | C2b |
|---|---|---|---|---|---|
| sel | ×1 (2025Q1) | 307 | +11.3 (5.33) [+21] | +11.3 (5.33) [+21] | +11.3 (5.33) [+21] |
| sel | bottom | 346 | +2.7 (4.79) [+6] | +2.9 (2.55) [+11] | 0 |
| sel | middle | 281 | +12.8 (3.82) [+34] | +12.6 (3.91) [+32] | +13.0 (3.97) [+33] |
| sel | top | 221 | +33.8 (2.61) [+129] | +43.1 (3.59) [+120] | +37.2 (2.72) [+137] |
| chk | bottom | 183 | +5.3 (2.74) [+19] | +3.1 (1.40) [+22] | 0 |
| chk | middle | 160 | +4.1 (1.95) [+21] | +3.5 (1.93) [+18] | +3.8 (2.14) [+18] |
| chk | top | 69 | +13.2 (1.12) [+118] | +17.0 (1.61) [+105] | +14.6 (1.18) [+124] |
| early | ×1 (2022Q1) | 78 | +11.9 (1.96) [+61] | +11.9 (1.96) [+61] | +11.9 (1.96) [+61] |
| early | bottom | 278 | +10.5 (3.20) [+33] | +6.3 (1.65) [+38] | 0 |
| early | middle | 217 | +1.6 (2.58) [+6] | +1.1 (2.56) [+4] | +1.6 (2.58) [+6] |
| early | top | 171 | +27.8 (1.94) [+143] | +38.8 (2.82) [+138] | +27.8 (1.94) [+143] |

- **C2a.** The top tercile earns 118-143 bp per $ in every era, out of sample too, and C2a buys 38-45% more of it:
  +9.3K / +3.8K / +11.0K. Out of sample the bottom tercile is not the worst (chk 19 bp vs middle 21; 2022-23 33 vs
  6), so halving it costs −2.2K in chk and −4.2K in 2022-23. Net +9.3K / +1.0K / +6.3K (+3.0 / +0.6 / +1.3 points a
  year). Gains are lumpy: losing days outnumber winning days (46/61, 22/52, 50/74), chk's era total (+37.5 bp of
  capital) is smaller than its best day (2026-08-22, +65 bp), and on the selection era's largest cascade (2025-10-10,
  84 parents) C2a lost 81 bp to the incumbent.
- **C2b** drops 346 / 183 / 278 parents. In the selection era they earned 6 bp per $, so the cash they free roughly
  pays for them (+0.3 points); in chk and 2022-23 they earned 19-33 bp per $ and the freed cash does not replace them
  (−2.8 / −2.1 points).
- **C6.** Every armed coin's 4σ hold grows 1.5× in stress minutes, exactly when the most coins are armed and filling.
  Under the live cash rule that starves the deeper rungs: in the selection era the stressed parents' net falls from
  +23.7K to +7.7K, their 6σ rungs from +3.8K (179 fills) to −3.4K (146) and 8σ from +7.2K (114) to −0.9K (85); calm
  parents are unchanged. One cascade day, 2025-02-03 (39 parents; funded 32 vs 27, deeper fills 30 vs 21), is −368 bp
  of the era's −652 bp; the five largest days −664 bp. In 2022-23, where coins are rarely armed and cash rarely binds,
  stressed fills earn 52 bp per $ like calm ones and ×1.5 adds +6.0K, at a lower Sharpe (1.72 to 1.60). At $1M the
  ADV cap keeps bids small against cash: raw t +1.98, vol-matched −1.00.

Cash counters (hsim, 1-second bound):

| Era | Book | Parents | Unfunded | Of which dropped by rule | Deeper placed | Placed late | Deeper filled | Cash-short rung-minutes | Bought |
|---|---|---|---|---|---|---|---|---|---|
| sel | incumbent | 1,155 | 38 | 0 | 2,105 | 92 | 737 | 3,863 | $16.7M |
| sel | C2a | 1,155 | 35 | 0 | 2,076 | 88 | 732 | 3,666 | $15.5M |
| sel | C2b | 1,155 | 371 | 346 | 1,465 | 62 | 500 | 2,791 | $12.1M |
| sel | C6 | 1,155 | 70 | 0 | 1,975 | 112 | 674 | 5,912 | $17.7M |
| chk | incumbent | 412 | 12 | 0 | 744 | 16 | 236 | 1,304 | $5.9M |
| chk | C2a | 412 | 21 | 0 | 731 | 14 | 237 | 1,198 | $5.0M |
| chk | C2b | 412 | 186 | 183 | 422 | 11 | 132 | 476 | $3.3M |
| chk | C6 | 412 | 33 | 0 | 691 | 17 | 220 | 1,639 | $6.0M |
| early | incumbent | 744 | 0 | 0 | 1,484 | 5 | 506 | 172 | $9.7M |
| early | C2a | 744 | 0 | 0 | 1,476 | 13 | 503 | 239 | $9.0M |
| early | C2b | 744 | 278 | 278 | 928 | 5 | 345 | 168 | $6.5M |
| early | C6 | 744 | 4 | 0 | 1,440 | 30 | 493 | 791 | $11.8M |

C2a leaves the cash rule roughly where it was (deeper fills −5 / +1 / −3; chk parents unfunded 12 to 21, as top-tercile
holds take 1.5× cash), so its result is the size tilt, not cash. C6 is the cash rule. By rung, net bp per $ (blend),
incumbent → C2a: 4σ 32→42 / 31→41 / 26→31; 6σ 29→38 / 24→23 / 66→86; 8σ 71→73 / 108→137 / 135→153 (sel / chk /
2022-23).

## Things that looked wrong or ambiguous
1. **fsim.load in a fresh checkout** reads reports/wick1m/pre_hunt_<tag>.pkl (gitignored) and otherwise rebuilds the
   dataset with sim.precompute. This runner copies the frozen pickles there after checking SHA256SUMS. (Coordinator's
   check: the rebuild equals the frozen dataset on every column the simulators use, so ladder/cash's run is unaffected.)
2. **Module shadowing.** fsim puts scripts/hunt, which has its own gates.py, ahead of scripts/ladder_v5 on sys.path;
   import gates first; this runner asserts the module paths.
3. Spec gaps, resolved as follows: quantile method not given (numpy linear); "all parent fills" taken literally (the
   trade list's bot = False rows included); early 2022Q1 also has no earlier fills (×1, like main 2025Q1); NaN stress
   → ×1.
4. C2b's dropped parents are counted in hsim's parent_unfunded (the hook gives them a zero hold); separated above.
5. The main trade list has 1,568 parents, the frozen dataset 1,567 (the 2026-11-05 23:08 fill lacks 60 minutes of
   candles); that fill would only enter 2027Q1's cutoffs, so nothing changes.
6. The C2 multiplier sizes every armed minute's hold by cutoffs taken from fills, so C2a also lowers total 4σ cash use
   (7-15% fewer dollars bought); the cash counters show this did not drive the result.

## Files
scripts/ladder_v5/cand_sizing.py (modes check, inputs, run, diag); reports/ladder_v5/trials.csv,
reports/ladder_v5/trials/*.json; reports/ladder_v5/sizing/: run_summary.txt, inputs.txt, cutoffs.csv,
bucket_shares.csv, diag.txt, diag_cash.csv, diag_rung.csv, diag_bucket.csv, diag_days.csv.
