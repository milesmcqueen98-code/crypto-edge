# Ladder v6 sizing: rounds (selection era only)

Each round's hypothesis is written here before the round runs; times are the commit times of each entry. Every run is
a row of variants.csv (selection-era statistics, S* θ 0.5 unless noted, both the ADV-capped and uncapped versions,
with the best-5-days-removed figures). Plan: reports/ladder_v6s_prereg.md.

## Round 1: headroom (written before running)
Hypothesis:
- The AI's prediction μ̂ ranks per-dollar outcomes: C2a's top tercile earned far more per dollar. The coin's daily
  volatility σ̂ ranks their dispersion.
- So Kelly, f = μ̂ / σ̂², should rank risk-adjusted outcomes better than μ̂ alone.

Predictions:
- The hindsight oracle (×2 / ×0.5, ADV-capped) gives a selection Sharpe-path t above 5.
- Z1 Kelly and Z3 edge clear the drop bar (t 1.4) at some λ. Z2 inverse variance ignores edge, and Z4 breadth
  shrinks the most profitable cascades, so neither does.
- Under the ADV cap at S*, upsizing is possible only in ETH, SOL, XRP, NEAR and ZEC, so capped results are weaker
  than uncapped.
- The edge family's t falls the most when the best 5 days are removed, because C2a's gain sat on a few days.

Runs:
- Diagnostics (quintiles of μ̂, σ̂, f and breadth against realized net per dollar of the incumbent's signals).
- The oracle, capped and uncapped.
- Each family at λ 0.25 / 0.5 / 1, capped and uncapped (24 runs).

### Round 1 read
Selection, S* θ 0.5. The declared path is Sharpe (vol-matched); "capped" means the 0.2% ADV cap is respected.

| Run | Sharpe-path t (best 5 days out) | Return-path t (best 5 out) | dSharpe | dret |
|---|---|---|---|---|
| Oracle ×2 / ×0.5, capped | +3.45 (+3.76) | +5.10 (+6.44) | +2.20 | +30.9 pp |
| Z1 Kelly μ̂/σ̂², best capped (λ 0.25) | −0.66 (−2.23) | −1.28 | −0.12 | −1.3 pp |
| Z2 inverse variance, best capped (λ 1) | −1.27 (−2.36) | −1.88 | −0.60 | −5.1 pp |
| Z3 edge μ̂, best capped (λ 0.5) | +0.40 (−1.11) | +1.60 (+0.47) | +0.12 | +2.2 pp |
| Z4 breadth, best capped (λ 0.25) | +1.01 (−0.53) | +2.16 (+0.65) | +0.12 | +1.4 pp |
| Z4 breadth λ 0.25, uncapped (information) | +1.83 (+0.75) | +2.95 (+2.16) | +0.20 | +2.0 pp |

- **All four families fall below the drop bar (1.4) and are dropped.** The headroom is real: the capped oracle reads
  t +3.45, and its gain is spread, since removing the best 5 days raises its t.
- **Every family's gain sits on a few days.** Wherever t is positive, it turns negative once the best 5 days are
  removed.
- **Why Kelly with the coin's volatility fails** (diag_sel.txt, 1,113 signals):
  - High-volatility coins earn proportionally more per dollar. Mean net per dollar runs +12 bp in the lowest σ̂
    quintile to +90 bp in the highest.
  - So 1/σ̂² tilts the book toward the low-edge coins. μ̂/σ̂² is the worst-ranked of the four by risk-adjusted
    outcome: its top quintile has the lowest mean/variance.
- **The AI's prediction ranks outcomes strongly** (Spearman +0.41 with net per dollar). But it also ranks their
  spread (Spearman +0.29 with absolute deviation): the standard deviation is 133 bp in the bottom quintile and 271 in
  the top.
- **Risk-adjusted outcome is hump-shaped in μ̂.** Mean/variance by quintile, ×1e4: 11.6, 2.4, 19.9, 29.5, 13.3. So
  edge-proportional sizing piles into the noisiest signals.

## Round 2: Kelly with the variance the signal itself predicts (written before running)
Hypothesis:
- The variance that matters is the signal's, not the coin's. Bigger predicted edges are more violent dislocations,
  with fatter outcomes.
- Kelly with mean and dispersion both predicted from μ̂ gives a hump-shaped size, largest for mid-to-high μ̂.
- That is the shape of the round-1 mean/variance table. It should beat edge-proportional sizing on the Sharpe path,
  and spread its gain more, because it shrinks the most extreme cascades.

Rule (family Z5, low-parameter, fitted on earlier signals only):
- **Mean model:** r̂ = a + b·μ̂, OLS of the incumbent's per-signal net per dollar.
- **Dispersion model:** ŝ = c + d·μ̂, OLS of the absolute residual, floored at 50 bp.
- **Size:** f = max(r̂, 0) / ŝ², and m = clip((f / f̄)^λ, 0.5, 2), ADV-capped. f̄ is the trailing 90-day median of f
  over research parents, computed with the same coefficients.
- **Fitting:** refit each month on all earlier signals; with fewer than 150, m = 1.
- **Drop bar:** the in-sample bound (coefficients fitted on the whole selection era) must reach t 1.4 at some λ.

Variants:
- λ 0.5 and 1, in-sample and walk-forward, capped and uncapped.
- Plus, for information, inverse dispersion only (f = 1/ŝ²).

### Round 2 read
| Run (capped unless noted) | Sharpe-path t (best 5 out) | Return-path t (best 5 out) | dSharpe |
|---|---|---|---|
| Z5 Kelly, in-sample, λ 1 | +1.14 (−0.26) | +1.96 (+0.79) | +0.16 |
| Z5 Kelly, in-sample, λ 0.5 | +0.98 (−1.03) | +2.06 (+1.26) | +0.12 |
| Z5 Kelly, walk-forward, λ 0.5 / 1 | −1.47 / −1.38 | −1.49 / −1.55 | −0.05 / −0.09 |
| Z5 Kelly, in-sample, uncapped, λ 0.5 / 1 | +0.49 / +0.04 | +0.78 / +0.42 | +0.05 / +0.02 |
| Inverse dispersion, in-sample / walk-forward | −0.57 to −1.51 | −0.48 to −2.46 | −0.14 to −0.36 |

- **Z5 is dropped:** its in-sample bound, +1.14, is below 1.4. Walk-forward it is negative.
- **The fitted shape is not a hump.** In-sample, r̂ = −8.8 + 1.10·μ̂ and ŝ = 64.8 + 0.51·μ̂, so f rises with μ̂ and
  flattens above μ̂ ≈ 100. Z5 is edge sizing with a ceiling, not the hump the quintile table suggested.
- **The walk-forward fits made it worse.** The early fits run on 150–400 signals, and their noise costs more than
  the shape gains.
- **Same pattern as round 1:** no rule's gain survives the removal of its best 5 days.

## Round 3: the book's own volatility (written before running)
Hypothesis:
- The rules so far move risk between signals, and most of the book's variance sits on a few cascade days. So their
  differences are made on those days.
- A rule that scales the whole book over weeks changes many days at once. Its gain, if any, would be spread.
- Volatility management (Moreira and Muir) raises Sharpe when the book's volatility is predictable and its return
  does not rise with it. Here the edge is largest in volatile cascades, so I predict it lowers Sharpe.

Rule (family Z6, low-parameter):
- m(day) = clip((σ_tgt / σ_w)^λ, 0.5, 2) for every coin that day, ADV-capped.
- σ_w is the standard deviation of the incumbent's daily returns over the w days before the day.
- σ_tgt is the median of σ_w over all earlier days. With fewer than 60 earlier days, m = 1.

Variants: w 30 / 60, λ 0.5 / 1, capped and uncapped (8 runs).

### Round 3 read
| Run | Sharpe-path t (best 5 out) | Return-path t | dSharpe | dret |
|---|---|---|---|---|
| Z6 w 30, λ 0.5 / 1, capped | −1.77 (−2.77) / −1.81 (−2.71) | −2.40 / −2.61 | −0.41 / −0.68 | −3.4 / −5.8 pp |
| Z6 w 60, λ 0.5 / 1, capped | −0.87 (−1.91) / −0.99 (−1.84) | −2.23 / −2.21 | −0.16 / −0.30 | −2.2 / −3.7 pp |
| Z6, uncapped (all four) | −0.36 to −1.95 | −1.79 to −2.25 | −0.12 to −0.76 | −1.7 to −6.3 pp |

- As predicted, the book's volatility is not a good reason to shrink it. The edge is largest after volatile weeks,
  so shrinking then gives up more return than risk. Z6 is dropped.
- A diagnostic between rounds shows why the gains concentrate. 41% of signal dollars and 55% of signal net P&L fall
  on the 20 days with the largest absolute P&L.
- μ̂ still ranks outcomes off those days (Spearman +0.26) and among isolated signals (+0.32). But its bottom tercile
  is weak both isolated (+5 bp a dollar) and in cascades (+1 bp). Downsizing that tercile alone was already tried by
  red team 2 (bottom-only ×0.5): selection positive, out-of-sample t −1.78. It is not retried here.

## Round 4: diversification across armed coins (written before running)
Hypothesis:
- When more coins are armed than the cash can cover, the cash rule funds the top-ranked bids in full and starves the
  rest.
- Sizing each bid by 1/√(armed coins) spreads the cash over more coins in a cascade. It also leaves bids full when
  few are armed.
- This is the one mechanism not yet covered (cash and diversification). Its effect lives in cascades, so I predict
  a small Sharpe gain at best, which fails the spread check.

Rule (family Z7):
- f = 1/√n_armed, where n_armed is the number of approved, fresh coins with a bid at that minute.
- m = clip((f / f̄)^λ, 0.5, 2), with f̄ the trailing 90-day median of f at research parent fills. ADV-capped.
- Variants: λ 0.5 and 1, capped and uncapped.

Reference, not a candidate: C2a (×0.5 / 1 / 1.5 by the margin's tercile, cutoffs from the earlier quarters' parent
fills) on this simulator, capped and uncapped. This answers the ADV-cap question for C2a itself on the selection era.
Round 5 is not planned: Z1–Z7 cover the mechanism-led forms (edge, variance, both, cascade breadth, book volatility,
cash and diversification).

### Round 4 read
| Run | Sharpe-path t (best 5 out) | Return-path t (best 5 out) | dSharpe | Top-5 share of the gain |
|---|---|---|---|---|
| Z7 armed coins, λ 0.5, capped | +1.01 (−0.61) | +0.60 (−1.12) | +0.06 | 2.3 |
| Z7 armed coins, λ 1, capped | +0.92 (−1.72) | +1.34 (−0.77) | +0.13 | 1.2 |
| Z7, uncapped, λ 0.5 / 1 | +0.37 / +0.27 | +0.51 / +1.23 | +0.03 / +0.05 | 2.5 / 1.4 |
| C2a reference, capped | +0.68 (−1.20) | +2.06 (+0.73) | +0.19 | 0.8 |
| C2a reference, uncapped | +1.25 (−0.46) | +1.71 (+0.23) | +0.30 | 0.9 |

- **Z7 is dropped** (+1.01 against the bar of 1.4), with the gain concentrated as predicted. A top-5 share above 1
  means the rest of the days net to a loss.
- **C2a on the engine-faithful book with print costs** reads Sharpe-path t +1.25 uncapped and +0.68 inside the
  0.2% ADV cap. Without its best 5 days it is negative either way.

## Conclusion of the iteration
Four rounds and seven families:
- Kelly on the coin's volatility; inverse variance; edge; cascade breadth.
- Kelly on the signal's own predicted dispersion; book volatility targeting; diversification across armed coins.

None reaches the drop bar inside the ADV cap. The best are Z5 in-sample at +1.14 and Z4 and Z7 at +1.01. None keeps a
positive Sharpe-path t without its 5 best days.

The hindsight oracle shows real headroom: t +3.45, with its gain spread. But what is knowable at the minute ranks
outcome size and outcome variance together. Most of the book's P&L, and so most of any resizing's effect, sits on the
20 or so cascade days a year. Round 5 is not run. Nothing is frozen, and the out-of-sample eras stay unread for
sizing.
