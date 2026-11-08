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
