# REPORT: MAC (pull the ladder around scheduled US macro releases, Path A)

Builder: events. Branch h2/events. SPEC: reports/hunt2/mac/SPEC.md.
- Rule code: scripts/hunt2/mac/mac.py (`dev sel`, `freeze`, `hold`).
- Print check on Actions: scripts/hunt2/mac/fill_check.py.
- Reporting only: scripts/hunt2/burn/post_lowmem.py and scripts/hunt2/burn/explain.py.

## Mechanism
At a scheduled release, prices move on public information, not on forced flow. The releases are CPI, NFP and PPI at 08:30 ET and the FOMC statement at 14:00 ET.

A 4σ dip bid resting through the release is filled by sellers who are informed by the print (Glosten–Milgrom). The dislocation is then a repricing, not an overshoot. Pulling the bids avoids being the liquidity that informed traders hit. R2-08's AI has no calendar feature.

## Data
- **Calendar:** data/hunt2/macro/releases.csv, from the official BLS and Fed calendars. Daylight saving and the autumn-2025 shutdown moves are included. Releases per scored era:

| Era | CPI | NFP | PPI | FOMC |
|---|---|---|---|---|
| early | 24 | 24 | 24 | 16 |
| DEV | 14 | 14 | 14 | 10 |
| chk | 7 | 7 | 7 | 5 |

- **Research parents** (frozen dataset): DEV 1,155, chk 412, early 744.
- **Prints, DEV:** first trade-through times of DEV parents from reports/hunt2/parents/features_dev.csv.
- **Prints, HOLD:** after the freeze, the 8 shared print artifacts were processed on Actions (run 42545469193), giving reports/hunt2/mac/hold_fill_check.csv.

## Definitions (committed before any trial, fa94d36)
- **Window:** minute rows from release − a to release + b, both ends included, UTC rows of `frozen_sim.arrays`. In those rows every coin's 4σ multiplier is SKIP. A parent filling there carries ~0 dollars; ladders armed earlier keep their deeper rungs.
- **Skipped parents:** DEV research parents whose (fill minute, coin) cell is SKIP. A variant is eligible with at least 10.
- **Selection:** the highest DEV paired HAC t at X2; ties go to fewer DEV blackout minutes.

## Trials (6, all logged; sel era, X2, $250K)
| Variant | DEV blackout min | DEV parents skipped | DEV t | Mean bp/day | ΔSharpe |
|---|---|---|---|---|---|
| CPI (2,10) | 182 | 17 | +0.80 | +0.24 | +0.18 |
| CPI (5,30) | 504 | 17 | +0.80 | +0.24 | +0.18 |
| CPI (5,120) | 1,764 | 21 | +0.78 | +0.21 | +0.16 |
| ALL (2,10) | 676 | 36 | +0.43 | +0.13 | +0.11 |
| ALL (5,30) | 1,872 | 36 | +0.43 | +0.13 | +0.11 |
| ALL (5,120) | 6,552 | 59 | −0.09 | −0.03 | +0.02 |

- All six variants are eligible.
- Windows (2,10) and (5,30) skip the same parents and give identical daily series, in both event sets.

## Frozen variant
- CPI only, a = 2, b = 10. It tied with (5,30), and the tie went to the narrower window.
- Freeze commit 6013b3b; code commit fa94d36.
- DEV: t +0.80, +0.24 bp/day, Sharpe 1.62 → 1.80 at X2.
- The 17 DEV parents skipped all come from two release days (Feb 12 and Sep 11, 2025).

## HOLD (read once) and gates, $250K
| | HOLD | chk | early | DEV | full |
|---|---|---|---|---|---|
| X2 mean diff, bp/day | +0.249 | +0.296 | +0.234 | +0.237 | +0.245 |
| X2 HAC t | 1.08 | 0.88 | 0.83 | 0.80 | 1.34 |
| X1 mean, bp/day (t) | +0.217 (1.01) | +0.226 (0.81) | +0.215 (0.80) | +0.188 (0.73) | +0.208 |
| ΔSharpe X2 | +0.22 | +0.23 | +0.22 | +0.18 | +0.20 |

- **A1 FAIL:** HOLD t 1.08 < 2.
- **A2 pass:** X1 HOLD mean +0.217 bp/day.
- **A3 pass:** both HOLD eras positive.
- **A4 pass:** candidate X2 years:

| | 2022 | 2023 | 2025 | 2026 |
|---|---|---|---|---|
| Candidate X2 | 8.59% | 8.76% | 16.65% | 9.85% |
| Difference vs incumbent | +1.84 pp | −0.13 pp | +1.08 pp | +0.65 pp |

- **Deflated Sharpe:** 0.21 (N = 4,546 at the read). The top 5 HOLD days are 119% of the gain.
- **Reported, not gated:**
  - S: HOLD +0.217 bp/day (t 1.01).
  - θ 0.25 at S: HOLD +0.220 bp/day (t 1.02).
  - At X2 the gain is about +0.9% a year on $250K.
- **HOLD parents skipped:**
  - chk: 12 (2.9%), on 2 releases (Sep 11 and Oct 14, 2026).
  - early: 10 (1.3%), on 6 releases.

## Where the difference comes from
Every era's gain is one day:

| Era | Release day with the gain | Other release day(s) |
|---|---|---|
| DEV | Feb 12, 2025: +133 bp | Sep 11, 2025: −25 bp |
| chk | Oct 14, 2026: +74 bp | Sep 11, 2026: −9 bp |
| early | May 11, 2022: +206 bp | five days, −2 to −16 bp each |

- May 11, 2022 was the LUNA/UST collapse week. The two skipped ladders that day (DOGE, SOL) lost 240–920 bp on every rung. The other 8 skipped early ladders hit their take-profits.
- In total, 3 of the 10 release days with a skipped parent helped; 7 cost a little.
- Research gross (before costs, mean of the three rungs) of skipped vs kept ladders is negative for the skipped ones in every era: DEV −13 vs +42 bp, chk −17 vs +40, early −73 vs +46.
- On the incumbent's ten worst DEV days the filter adds +133 bp at X2, all of it on Feb 12, 2025.

## Capacity
The filter only removes bids (m ≤ 1). No per-signal capacity is lost. It pulls about 1.5% of parents and frees their cash.

## Fill realism
- **Release times** are official and published in advance.
- **Live operation:** cancel 4σ bids at T−2 minutes and place none until T+11. That is at most 17 cancels per release, well inside the 30 requests/s limit.
- **Print-confirmed fill times:** all 17 DEV skipped parents traded through 13–56 s after the release. All 22 HOLD skipped parents traded through 6–426 s after it, inside the window. No skip comes from a minute-stamp artefact.
- **SKIP hook's busy side effect:** 0 parents affected in every era.

## Weaknesses
- **Tiny effective sample:** 2 release days in DEV and 8 in HOLD. The SPEC counts parents, but parents fill across coins within the same release minute, so they are not independent.
- **Single-day dependence:** one day carries each era, and the early one overlaps the LUNA crash.
- **NFP/PPI/FOMC added nothing on DEV.** CPI-only matches memo R2, but it was also the DEV winner.
- **Window size barely matters.**
- **Neighbours:** 5 of 6 DEV variants are positive.

## Verdict
FAIL on A1 (HOLD t 1.08). The sign is positive in all three eras and at X2, X1, S and θ 0.25. But each era's gain rests on a single release day, and the deflated Sharpe is 0.21, so this is not a demonstrated edge.

As a costless risk rule it never hurt by more than a few bp per release day. Adopting it would be a judgement call, not a pass, and it would need its own pre-registered test on new releases.
