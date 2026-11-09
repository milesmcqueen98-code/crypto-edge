# Edge hunt 2 (Nov 8 2026): ten desk-style builds against R2-08 — none passes at 2× costs

Protocol, gates and deviation log: `reports/hunt2_prereg.md` (frozen at 88b5894). Final report: the "Edge Hunt 2 vs
R2-08" doc (https://claude.ai/artifact/4Z4j3NUvwGFLKHAxCzzYS5).

| Rank | Build | Path | Score /100 | HOLD (2× costs) | Gates 1–4 |
|---|---|---|---|---|---|
| 1 | MAC: pull bids 2 min before to 10 min after CPI | A | 74 | t 1.08, +0.25 bp/day | ✗✓✓✓ |
| 2 | EXH: skip fills before much forced selling has traded | A | 72 | t 1.51, +0.21 bp/day | ✗✓✓✓ |
| 3 | WHO: skip fills whose pre-fill selling looks informed | A | 53 | t 0.59, +0.11 bp/day | ✗✗✗✓ |
| 4 | SHAPE: skip grinds, keep air pockets | A | 46 | t −1.12 | ✗✗✗✓ |
| 4 | IMP: skip drops larger than the square-root law explains | A | 46 | t −1.50 | ✗✗✗✓ |
| 4 | CROWD: skip when perp funding says shorts are crowded | A | 46 | t −1.83 | ✗✗✗✓ |
| 7 | GAMMA: skip while Deribit dealers are short gamma | A | 44 | t −1.62 | ✗✗✗✓ |
| 8 | BURN: cool a coin down after a failed ladder | A | 41 | t −1.04 | ✗✗✗✓ |
| 9 | LETF: leveraged-ETF rebalancing around the 4 pm close (perps) | B | 34 | book Sharpe −0.40 | ✗✗✗✓ |
| 10 | EXP: Deribit Friday expiry unwind (perps) | B | 31 | book Sharpe −0.04 | ✗✗✗✓ |

## Files
- `ideas.md`: the 73 ideas, each naming who is forced to trade and why we are paid, with prior scores and statuses.
- `<build>/`: `SPEC.md` (frozen grid), `REPORT.md` (the build's write-up), `frozen.json` (the freeze commit's
  variant), `gates.json` (the single HOLD read), `daily.parquet` (Path A: x2, x1, s on $250K; Path B: sleeve returns
  by capital at 2× and 1×), plus each builder's DEV trial tables and diagnostics.
- `trials.csv`: every DEV trial (98), logged by `scripts/hunt2/h2gates.log_trial`.
- `central_gates.json` / `.csv`: every gate recomputed centrally from `daily.parquet` with the final ledger
  (`scripts/hunt2/central_gates.py`).
- `central_checks.json`: skip cells reached the simulator in every era, each HOLD run's DEV slice reproduces its logged
  trial, DEV trials precede the freeze and HOLD outputs follow it, and the sparse-sleeve alpha with idle cash at
  T-bills (`scripts/hunt2/central_checks.py`).
- `scorecard_manual.json` (hand-scored parts; mechanism and implementability fixed before any HOLD read) and
  `scorecard.csv` (`scripts/hunt2/scorecard.py`).
- `incumbent_daily.parquet`: R2-08 on ladder v6's frozen simulator at S, X1 and X2, and at the Path B capitals.
- `parents/`: research-parent windows and the pre-fill print features (DEV and HOLD).
- `research/`: memos R1–R4 (microstructure; options, events and flows; ML and statistics; venue facts).

## Reproduce
Builder code lives in `scripts/hunt2/<build>/` (merged from branches h2/flow, h2/events, h2/shape, h2/options,
h2/letf); each REPORT ends with its commands. Shared modules: `frozen_sim.py`, `pathA.py`, `h2gates.py`, `costs.py`.
Data-heavy steps (prints, Deribit trades, HOLD print features) ran on GitHub Actions through `.github/workflows/hunt2.yml`.
