# Ladder v6, sizing: pre-registration

Written before any sizing variant was run. Branch ladder/v6-sizing, cut from ladder/v6-exits at 86dfaaf (the frozen
simulator with the incumbent reproduced, before any exit variant).

## Goal
Find a sizing rule for the spot ladder that raises Sharpe with a gain spread across many days, or show that none
does. "No change" is a valid result.

Context:
- Perfect sizing is worth +2.6 Sharpe: ladder v5's hindsight oracle O4, winners ×2 and losers ×0, which is mostly
  selection.
- C2a (×0.5 / 1 / 1.5 by the AI margin's tercile) passed the frozen gates at t 2.21. Out of sample its t was 1.33
  (1.91 with print exit costs), and the gain sat on a few days. It is queued for a forward re-test and is not
  re-tested here.

## Frozen simulator
- The ladder v6 frozen simulator: scripts/ladder_v6x/lsim.py, unchanged. It combines red team 1's engine-faithful
  cash rule (frozen/rt_live.py) with red team 2's print-measured exit costs (frozen/c3.py PrintCost), on ladder v5's
  frozen dataset.
- It is reproduced first through the sizing path with every multiplier at 1. It must equal the incumbent's best
  estimate to float precision: S* θ 0.5, $250K, 22.79% / 19.05% / 11.14% a year, Sharpe 2.935 / 2.661 / 1.913
  (selection / check / 2022–23).
- **Sizing hook** (rt_live's mult_fn semantics, as C2a used them):
  - Each minute, the 4σ bid of an approved coin is sized at base × m(t, coin).
  - At a parent fill, the parent takes that minute's bid, and the 6σ and 8σ rungs take m at the fill minute.
  - Fill capacity (θ × the volume through the bid), the cash rule, take-profit capacity and print-measured exit costs
    at each tranche's own size all apply exactly as for the incumbent.
  - Implementation: the era's arrays are built once and their wants scaled by m. This is identical to mult_fn
    whenever m > 0, and every rule here keeps m ≥ 0.5.

## The 0.2% ADV cap
- The incumbent's base size per signal is min(25% of capital, 0.2% of the coin's ADV at today's volumes in S*),
  split into thirds across the rungs.
- C2a multiplied this capped size, so its ×1.5 exceeded the 0.2% ADV cap.
- Every variant here is run two ways:
  - **(a) ADV-capped:** m_eff = min(m, room), where room = 0.2% of ADV ÷ the base size. Room is ≥ 1, and exactly 1
    where the ADV cap already binds.
  - **(b) Uncapped**, as C2a was.
- The candidate is always the ADV-capped version (a). Version (b) is reported, never a candidate.

## Spread across days
- Every result is reported three ways: all days; with the 5 best difference days removed (paired Newey-West t and
  mean of the remaining days); and with the share of the total gain that the 5 best days carry.
- **Target criterion for adoption:** with the 5 best out-of-sample difference days removed, the pooled
  out-of-sample t (declared path) must stay ≥ 1.0. A candidate that passes G1–G4 without it can be at most
  "forward-test".

## Inputs, fixed now (all known at the minute)
- **μ̂ (predicted net edge):** the AI's prediction at that minute, from the panel the bot ranks by. Only approved
  coin-minutes (prediction above the quarter's threshold) carry bids.
- **σ̂ (predicted volatility):** the coin's daily volatility as of the previous day. This is the 30-day standard
  deviation of daily log returns, as sim.daily_stats computes vol_d for the trade list.
- **Breadth:** the number of distinct coins with a research parent fill in the last 30 minutes, the current minute
  included.
- **Normalisation f̄:** the median of f over the research parent fills of the trailing 90 days (before the current
  day). With fewer than 30 such parents, m = 1.

## Families (levers), fixed now
- **Z1 Kelly:** f = μ̂ / σ̂²
- **Z2 inverse variance:** f = 1 / σ̂²
- **Z3 edge:** f = μ̂ (a continuous, shrunk cousin of C2a)
- **Z4 cascade breadth:** f = 1 / √breadth (a risk budget per cascade instead of per coin)
- **Size:** m = clip((f / f̄)^λ, 0.5, 2), shrunk toward equal size, with λ ∈ {0.25, 0.5, 1}. Then ADV-capped as above.
- **Declared path: Sharpe** (the vol-matched difference), because sizing reallocates risk. The return path is
  reported alongside.

## Round 1: headroom
- **Diagnostics (selection era, incumbent's signals):** do μ̂ and σ̂ rank the realized per-dollar outcomes and their
  dispersion?
- **Oracle in the family's range:** per signal, m = 2 (ADV-capped) if the incumbent's realized net on that signal is
  positive, else 0.5. This is a hindsight bound on any rule in [0.5, 2].
- **In-sample bound per family:** the best λ on the selection era, at S* θ 0.5 on the declared path. A family is
  dropped when that t is below 1.4. The rules have no fitted coefficients beyond λ: f̄ is a trailing median, μ̂ is
  the walk-forward AI.

## Iteration on the selection era only (Jan 2025 – Mar 2026)
- At most 5 rounds of hypothesis, test, read, refine.
- Each round's hypothesis is written in reports/ladder_v6s/rounds.md before the round runs.
- Every variant run is a row in reports/ladder_v6s/variants.csv, with selection-era statistics only, in both cap
  versions and with the best-5-days-removed figures.
- No statistic of any variant on the check era (Apr – Nov 5 2026) or 2022–23 is computed before the freeze commit.

## Freeze, then one read of the out-of-sample eras
- The chosen rule (or none) is frozen in a commit, then read once on the check era and 2022–23.
- **Gates** (ladder v5's, on the out-of-sample eras, declared path):
  - G1: pooled paired Newey-West t ≥ 2 over check + 2022–23 at S* θ 0.5.
  - G2: mean daily difference > 0 in each out-of-sample era.
  - G3: the same at θ 0.25 (pooled t ≥ 2, both eras positive).
  - G4: base pooled mean > 0.
  - Plus the target criterion (spread) above. The selection era is reported and carries no weight.
- **A rule that passes:**
  - An independent red team re-runs it with its own code, including the cap and spread checks.
  - Then a forward test on data after Nov 5 2026: a paper book running the rule beside the incumbent's on the same
    data, with sample size and stop rule fixed before it starts.
  - Adopt only after both.
- **Verdicts:**
  - Adopt: gates, target criterion, red team, and the forward test set up.
  - Forward-test: G1 at t ≥ 1 with both out-of-sample eras positive, or a question history cannot answer.
  - Reject: everything else.
- **Scorecard:** ladder v5's 100-point rubric, with Evidence, Robustness, Prize and Capacity on the out-of-sample
  eras, as in ladder v6 exits (scripts/ladder_v6x/scorecard.py rules). Hand parts are fixed before the read.
- **Patch** to bot/spot only for an adopted change: an engine option, with parity and fault tests, every safety
  check kept.

## Deviation log

