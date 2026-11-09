# REPORT: BURN (skip a coin after its ladder fails to rebound, Path A)

Builder: events. Branch h2/events. SPEC: reports/hunt2/burn/SPEC.md.
- Rule code: scripts/hunt2/burn/burn.py.
- Definitions check: scripts/hunt2/burn/inspect_dev.py.
- HOLD runner actually used: scripts/hunt2/burn/hold_lowmem.py.
- Reporting only: scripts/hunt2/burn/post_lowmem.py and scripts/hunt2/burn/explain.py.

## Mechanism (the SPEC's hypothesis)
The ladder is paid when selling is forced and transient. If a 4σ parent has not rebounded by minute 60, the selling was persistent: an informed seller or a metaorder with long memory. The next dislocation in the same coin within hours is then more likely the same seller, so the rule skips that coin, or every coin when at least 2 coins fail within an hour, for C hours. It needs only the bot's own fills and candles.

## Data
- Research parents and rung records of the frozen dataset, with 1-minute Coinbase candle outcomes: DEV 1,155, chk 412, early 744.
- Failures on DEV: 327 at m = 0 and 164 at m = 0.5.
- Failures for the frozen m = 0.5 in HOLD: chk 47, early 95.
- No lookback parent (Dec 28–31, 2024) failed.

## Definitions (pinned on DEV with inspect_dev.py, committed before any trial, be8b147)
- **Parent:** a research parent (P, k = 4, filled), whether or not the replay funded it. The flag comes from public candles, so it depends neither on the cash replay nor on the filter itself.
- **TP hit by +60:** `tp_hit`, with `tp_off` in 1..60. A high in minutes fill+1 to fill+60 traded through TP = lvl·exp(0.6·4σ) by one tick.
  - Checked: `tp_hit` ⇔ `tp_off` ≥ 0, and `f_off` = 0 for every parent.
  - The only 2 not-hit parents with a later close at or above TP are PEPE closes within one tick of it.
- **Price at +60:** g60 = 1e4·ln(close of minute fill+60 / lvl), which is the bot's own 60-minute exit price.
- **Dislocation:** D = 4σ = g_tp/0.6 bp. Checked against 2·ln(lvl4/lvl6) on 526 parents: the difference is at most 4e-11 bp.
- **Failure:** failed(m) ⇔ TP not hit, g60 < 0 and g60 ≤ −m·D.
- **Timing:** the flag is known at minute row fill+61 (the engine's time-exit step). The skip covers rows [known, known + 60·C).
- **Market scope:** a failure known less than 60 minutes after another coin's failure skips every coin for C hours. A lone failure skips nothing in that scope.
- **HOLD protection:** chk and early flags can only be computed after the freeze; the code asserts this.

## Trials (12, all logged; sel era, X2, $250K)
| Variant | Triggers | DEV parents skipped | t | Mean bp/day | ΔSharpe |
|---|---|---|---|---|---|
| coin m0 C6 | 327 | 166 (14.4%) | −1.83 | −1.20 | −0.69 |
| coin m0.5 C6 | 164 | 89 (7.7%) | −1.27 | −0.40 | −0.26 |
| coin m0 C24 | 327 | 270 (23.4%) | −2.01 | −1.77 | −1.06 |
| coin m0.5 C24 | 164 | 148 (12.8%) | −1.75 | −0.59 | −0.39 |
| coin m0 C72 | 327 | 340 (29.4%) | −2.43 | −2.29 | −1.38 |
| coin m0.5 C72 | 164 | 190 (16.5%) | −2.45 | −1.02 | −0.62 |
| market m0 C6 | 195 | 259 (22.4%) | −2.06 | −1.87 | −1.14 |
| market m0.5 C6 | 101 | 196 (17.0%) | −2.22 | −1.57 | −0.97 |
| market m0 C24 | 195 | 447 (38.7%) | −2.32 | −2.63 | −1.57 |
| market m0.5 C24 | 101 | 257 (22.3%) | −2.42 | −2.01 | −1.22 |
| market m0 C72 | 195 | 515 (44.6%) | −2.57 | −3.11 | −1.97 |
| market m0.5 C72 | 101 | 313 (27.1%) | −2.76 | −2.63 | −1.59 |

All twelve are eligible (at least 5% skipped). Every one is below the incumbent, and the more a variant skips, the worse it does.

## Frozen variant
- The SPEC's rule (highest DEV t among eligible variants, no sign requirement) picks coin scope, m = 0.5, C = 6 h.
- DEV: t −1.27, −0.40 bp/day, Sharpe 1.62 → 1.37.
- The protocol has no stop-if-negative clause, so the variant was frozen (d23f099; code be8b147) and HOLD was read once.

## HOLD (read once) and gates
| | HOLD | chk | early | DEV | full |
|---|---|---|---|---|---|
| X2 mean diff, bp/day | −0.214 | +0.099 | −0.308 | −0.399 | −0.274 |
| X2 HAC t | −1.04 | +0.13 | −2.18 | −1.27 | −1.59 |
| X1 mean, bp/day (t) | −0.275 (−1.27) | +0.056 (0.07) | −0.374 (−2.24) | −0.551 (−1.66) | |
| ΔSharpe X2 | −0.15 | +0.32 | −0.32 | −0.26 | |

- **A1 FAIL:** HOLD t −1.04.
- **A2 FAIL:** X1 HOLD mean −0.275 bp/day.
- **A3 FAIL:** early −0.308 bp/day (chk +0.099).
- **A4 pass,** though the candidate is below the incumbent in every year:

| | 2022 | 2023 | 2025 | 2026 |
|---|---|---|---|---|
| Candidate X2 | 4.86% | 8.53% | 14.44% | 8.74% |
| Difference vs incumbent | −1.90 pp | −0.35 pp | −1.13 pp | −0.47 pp |

- **Deflated Sharpe:** 0.06 (N = 4,598).
- **Reported, not gated:**
  - S: HOLD −0.275 bp/day (t −1.27).
  - θ 0.25 at S: HOLD −0.267 bp/day (t −1.26).
- **HOLD parents skipped:** chk 12 (2.9%), early 36 (4.8%).
- **Incumbent's ten worst DEV days:** the filter costs −5.7 bp at X2 and −18 bp at S, so it does not help there.

## Why it fails: the opposite of the hypothesis
Ladders that follow a failure in the same coin earn more than average, not less. Research gross (before costs, mean of the three rungs) of skipped vs kept ladders:

| Case | Skipped | Kept | Note |
|---|---|---|---|
| DEV, frozen variant | 83 bp | 38 bp | 4σ rung 100 vs 54 bp; TP rate 78% vs 59% |
| DEV, all 12 variants | 55–91 bp | 26–39 bp | same direction in every variant |
| early | 82 bp | 42 bp | |
| chk | 8 bp | 39 bp | only 12 parents; the one era where the filter slightly helped |

A failed ladder marks a deeper, longer liquidation. The next 4σ trade-through in the same coin comes after more forced selling and rebounds harder. This fits the execution round's finding that bad days usually recovered.

## Capacity and fill realism
- The filter only removes bids (m ≤ 1), so no capacity is lost.
- The flag uses exactly the research's own take-profit and 60-minute definitions. The live bot knows both from its own take-profit fills and its exit price.
- The SKIP hook's busy side effect affected 0 parents in every era.

## Deviations and operations
- Two runs of `burn.py hold` were OOM-killed (exit 137) while five other builders' HOLD jobs shared the memory cgroup. Neither wrote a gate, series or P&L, and nothing from them was seen.
- The single completed read used hold_lowmem.py: the same frozen `burn.mult`, `pathA.hold_read` and `h2gates.path_a`, with one era's arrays in memory at a time.
- Its DEV slice reproduces the logged DEV trial exactly.
- No redesign was made.

## Weaknesses
- The market-scope reading (a lone failure skips nothing; "within the same hour" taken as a rolling 60-minute window) is my interpretation. It was committed before any trial.
- Flags use research parents whether or not the bot funded them. A variant using only the bot's own funded parents was not tested; it is outside the grid.

## Verdict
FAIL on A1, A2 and A3. This is a clean rejection: all 12 DEV variants lower the incumbent's return, and the frozen least-bad variant is negative on HOLD (early t −2.18). After a failed ladder, the same coin's next ladder is more profitable than average. Do not build this; the evidence argues against any cool-down after a failed ladder.
