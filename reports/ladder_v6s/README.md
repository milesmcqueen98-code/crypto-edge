# Ladder v6, sizing (Nov 8 2026): how big each signal's ladder should be

**Result: no change.** I tried seven mechanism-led sizing families over four rounds on the selection era. None
reaches the drop bar inside the 0.2% ADV cap, and no rule's gain survives the removal of its 5 best days. Nothing was
frozen, so the check era and 2022–23 stay unread for sizing. The bot keeps equal size: min(25% of capital, 0.2% of
ADV), split into thirds across the rungs.

## Frozen simulator, incumbent reproduced
- The simulator is ladder v6's frozen one (scripts/ladder_v6x/lsim.py): engine-faithful cash rule plus
  print-measured exit costs.
- Sizes enter through the replay's multiplier hook, with C2a's semantics. Every minute's 4σ bid is scaled by
  m(t, coin); at a parent fill, the deeper rungs take m at the fill minute.
- With every multiplier at 1, it reproduces the incumbent exactly (difference 0.0): S* θ 0.5, $250K, 22.79% /
  19.05% / 11.14% a year, Sharpe 2.935 / 2.661 / 1.913 (reproduce.txt).

## Headroom, and why the knowable part does not size well
- **The headroom is real.** In hindsight, sizing each signal ×2 if it made money and ×0.5 if not reads Sharpe-path
  t +3.45 inside the cap (+2.20 Sharpe). Its gain is spread: removing the best 5 days raises the t to +3.76.
- **The AI's prediction μ̂ ranks outcomes, but ranks their spread too** (diag_sel.txt, 1,113 signals).
  - Spearman +0.41 with net per dollar, and +0.29 with the absolute deviation.
  - Mean/variance by μ̂ quintile, ×1e4: 11.6, 2.4, 19.9, 29.5, 13.3. Sizing up the top quintile buys the noisiest
    signals.
- **The coin's volatility is the wrong risk measure.** High-volatility coins earn more per dollar: +12 bp in the
  lowest quintile, +90 bp in the highest. So Kelly with σ̂ = daily volatility tilts toward low-edge coins.
- **The P&L lives on a few days.** 41% of signal dollars and 55% of signal net P&L fall on the 20 days with the
  largest absolute P&L. Any resizing makes most of its difference there.
- **The cap leaves little room to size up.** At today's volumes, only ETH (10.8x), XRP (3.2x) and SOL (2.4x) have
  room under the 0.2% ADV cap (median over approved minutes). Every other coin can only be shrunk (checks.txt).

## Families (selection era, S* θ 0.5, best capped variant; declared path Sharpe)
| Family | Rule | Sharpe-path t (best 5 days out) | Return-path t | dSharpe | Verdict | Score /100* |
|---|---|---|---|---|---|---|
| Z4 cascade breadth | m = (f̄ / f)^0.25 with f = 1/√(coins filling in the last 30 min) | +1.01 (−0.53) | +2.16 | +0.12 | reject, round 1 | 50 |
| Z5 Kelly on the signal's predicted dispersion | mean and spread from μ̂, refit monthly | +1.14 in-sample (−0.26); walk-forward −1.38 | +1.96 | +0.16 | reject, round 2 | 47 |
| Z3 edge | m = (μ̂ / f̄)^0.5 | +0.40 (−1.11) | +1.60 | +0.12 | reject, round 1 | 47 |
| Z7 diversification across armed coins | f = 1/√(armed coins) | +1.01 (−0.61) | +0.60 | +0.06 | reject, round 4 | 39 |
| Z1 Kelly on the coin's volatility | f = μ̂ / σ̂² | −0.66 (−2.23) | −1.28 | −0.12 | reject, round 1 | 27 |
| Z2 inverse variance | f = 1 / σ̂² | −1.27 (−2.36) | −1.88 | −0.60 | reject, round 1 | 25 |
| Z6 book volatility targeting | the whole book scaled by its trailing 60-day volatility | −0.87 (−1.91) | −2.23 | −0.16 | reject, round 3 | 25 |

\* Scored on the selection era (an in-sample upper bound), because nothing reached an out-of-sample read.

- **Common rule shape:** m = clip((f / f̄)^λ, 0.5, 2), with f̄ the trailing 90-day median of f at research parent
  fills. Each family was run at λ 0.25, 0.5 and 1 (Z6 by window), capped and uncapped.
- **Drop bar:** t 1.4 on the declared path inside the cap.
- **Every positive rule depends on a few days.** Its Sharpe-path t turns negative without its best 5 days. For
  several, the top-5 share of the gain is above 1: the other days net to a loss.

## C2a on this simulator (reference, not a candidate; it waits for its forward re-test)
- **Inside the 0.2% ADV cap:** Sharpe-path t +0.68, falling to −1.20 without its best 5 days.
- **Uncapped, as originally run:** +1.25, falling to −0.46.
- Its selection-era Sharpe gain is +0.19 capped and +0.30 uncapped. Breaching the cap accounts for part of it, and a
  few days carry the rest.

## A lead for when volumes recover (not tested out of sample)
At research-era volumes and 1x costs (the base configuration), the cap leaves more room. There, edge sizing reads
Sharpe-path t +1.74 and keeps +0.73 without its best 5 days, and breadth reads +1.82 (+0.88). Sizing may matter again
if alt volumes return to 2025 levels. Re-test it then, on new data.

## Files
- `../ladder_v6s_prereg.md`: the plan, written before any variant, and its deviation log (freeze: nothing frozen).
- `rounds.md`: hypotheses written before each round, then the reads.
- `variants.csv`: all 52 runs, both cap versions, best-5-out figures.
- `round*.txt` and `diag_sel.txt`: round outputs and diagnostics.
- `scorecard.csv`, `scorecard_manual.json` and `records/`: scores and their inputs.
- `checks.txt`: reproduction, cap enforcement, room by coin, determinism.
- Code: scripts/ladder_v6s/ (`ssim.py` sizing hook and inputs, `rounds.py`, `scorecard.py`).
