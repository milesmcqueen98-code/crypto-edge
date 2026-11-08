# Ladder v6, exits (Nov 8 2026): when to sell the part the take-profit has not sold

**Result: no change.** Selling early loses, even with a rule fitted on the same data it is scored on. Holding past
minute 60 had an in-sample edge, but nearly all of it came from Q1 2025. It was weak walk-forward, and the frozen rule
failed out of sample: pooled t +0.52, with the check era negative. The bot keeps "take-profit, else market at minute 60".

## Frozen simulator, incumbent reproduced
This round uses ladder v5's named simulator: red team 1's engine-faithful cash rule, plus red team 2's print-measured
exit costs (scripts/ladder_v6x/lsim.py).

It reproduces the incumbent's best estimate (S*, θ 0.5, $250K): 22.8% / 19.1% / 11.1% a year, Sharpe 2.94 / 2.66 /
1.91 (selection / check / 2022–23). The other three configurations reproduce too. The largest daily difference from
red team 1's series is 1.2e-17 (reproduce.txt).

The exit layer (scripts/ladder_v6x/exits.py) lets a tranche sell at any minute from 0 to 120. "Sell at 60" reproduces
the incumbent exactly in all 4 configurations and 3 eras.

## Exit cost by minute (kappa/REPORT.md)
kappa(m) is the cost of a market sale at minute m divided by its cost at minute 60. It was measured on Coinbase prints
for the 300 pre-drawn selection tranches (6.48M prints, 252–264 valid pairs per minute).

| Minute | 2 | 5 | 10 | 20 | 30 | 45 | 60 |
|---|---|---|---|---|---|---|---|
| kappa | 1.02 | 1.15 | 1.17 | 1.10 | 1.01 | 1.03 | 1 |
| Median cost, bp | 2.9 | 3.6 | 3.7 | 3.4 | 3.5 | 2.9 | 2.8 |

Selling early is never cheaper than selling at 60. Half-spreads are 1.5–1.8x wider for about 10 minutes after the fill.

## Why an hour of rising markouts does not make a better exit (diag_markouts.txt)
Data: S* θ 0.5, selection era. Our fills' average close against the entry climbs to +57 bp by minute 45. By minute
60 the take-profit has already sold 53% of the dollars. What is still unsold at 60 is the set of tranches that did
not rebound: they average −71 bp at 60, −108 at 90 and −117 at 120. The markout rise belongs to the tranches the
take-profit already sells.

## Headroom against what can be captured (round 1, selection era, S* θ 0.5)
| Lever | Hindsight oracle (kappa 1): t / Sharpe change | In-sample rule* | Walk-forward |
|---|---|---|---|
| X1 sell early (0–60) | +4.02 / +1.43 | t −0.72 (best of family) | t +0.16 |
| X2 hold to 120 | +4.35 / +1.82 | t +1.79 (6 inputs, h 10) | best t +0.62 |
| X12 both | +4.78 / +1.93 | t +1.32 (best of family) | t +0.46 |

\* In-sample means fitted on the whole selection era and scored on it. "Best of family" is the best of every subset of
the 6 inputs × hurdle h ∈ {0, 5, 10} at the measured kappa. X2 needed no family scan because its 6-input fit already
cleared the bar, and its costs do not use kappa. Walk-forward for X1 and X12 uses their best family spec and was run
after the freeze, for information only.

The drop bar was t 1.4, so X1 and X12 were dropped. In X1's data, the one strongly predictable region is "the price
is above the take-profit and part of the remainder is unfilled": holding then loses 14–256 bp a dollar. That state
cannot happen live: while our take-profit rests with size left, buyers fill it before the price can trade higher. A
rule that sells the rest at those historical prices counts the same buyers twice (corrected after the read; see the
leads section).

## Rounds 2–4 on X2 (rounds.md, variants.csv)
All rows below are walk-forward on the selection era, with the pessimistic cash bound the gates use.

| Round | Hypothesis | Variants | Best t |
|---|---|---|---|
| 2 | Few inputs beat the 6-input fit | 6 inputs, rec, rec + m, each at 3 hurdles | +0.62 (6 inputs, h 10) |
| 3 | Hold while the cascade is still spreading (breadth) | breadth, + mark, + rec | −0.14 |
| 4 | Weight the fit by remainder dollars | WLS, plus the sign-stable inputs | +0.56 |

What sank X2:
- **One quarter.** In-sample, the edge was "a remainder still deep under water at 60 keeps recovering". That earned
  +164 bp a dollar in Q1 2025, then −3, −46, −47 and +35 in the next four quarters.
- **Cash.** Holding every remainder an extra hour in the cash rule costs 3.5 points a year by itself, because the
  extensions come during cascades, when cash is short.

Round 5 was not needed.

## Out-of-sample read (oos/summary.txt): the frozen X2 rule, read once after freeze commit 94209a0
| | S* θ 0.5 | S* θ 0.25 | Base | $1M |
|---|---|---|---|---|
| Pooled t (check + 2022–23) | +0.52 | +0.60 | +0.73 | +0.83 |
| Check era, bp a day | −0.04 | +0.07 | +0.23 | +0.08 |
| 2022–23, bp a day | +0.22 | +0.22 | +0.30 | +0.17 |
| Sharpe, check: incumbent → rule | 2.66 → 2.37 | 2.41 → 2.20 | 2.67 → 2.53 | 1.47 → 1.33 |

Gates: G1 fail, G2 fail, G3 fail, G4 pass. With optimistic cash (information only), the S* pooled t is +0.90.

## Verdicts and scores (scorecard.csv, ladder v5's 100-point rubric)
| Candidate | Basis | Score | Verdict |
|---|---|---|---|
| X12 hold-or-sell over 0–120 | in-sample upper bound (never frozen) | 46 | reject: dropped at round 1 (walk-forward t +0.46) |
| X2 hold past 60 (frozen rule) | out of sample | 33 | reject: fails G1–G3 |
| X1 sell early | in-sample upper bound (never frozen) | 18 | reject: dropped at round 1 |

The X1 and X12 scores are computed on the data they were fitted to, so they are not comparable with X2's
out-of-sample score. No red team, forward test or bot patch, because nothing passed.

## Leads checked after the read: both closed (rounds.md, last section)
- **Take-profit fill share: small stakes.** Only 4–5% of the dollars unsold at 60 come from tranches whose
  take-profit was touched. Even giving the take-profit all the volume traded above it lifts S* θ 0.5 Sharpe by only
  +0.04 to +0.07. The paper broker uses the same 0.5 capture, so only live pilot fills can measure the real share.
- **X1's pattern, corrected explanation.** While our take-profit rests with size left, buyers fill it before the
  price can trade higher. "Price above the take-profit, part unfilled" cannot happen live, and selling the rest at
  those historical prices counts the same buyers twice.
- **Cash-aware extension: no need to build.** With no cash cost at all, the frozen rule reads out-of-sample t +0.90,
  short of the gate's 2.
- **Exit layer recomputed from the candles** for 6 random tranches at minutes 30 and 120: it matches to 1e-7.

## Files
- `../ladder_v6x_prereg.md`: the pre-registration and its deviation log.
- `rounds.md`, `variants.csv` (1,187 logged runs), `round*.txt`.
- `frozen_rule.json`, `oos/`, `scorecard*.{json,csv}`, `records/`.
- `kappa/` (measurement code on branch ladder/v6x-kappa), `exitdata/`, `books/` (cached frames).
- `reproduce.txt`.
- Code: scripts/ladder_v6x/ (lsim, exits, rules, oos, scorecard; frozen/ holds the unchanged red-team code).
