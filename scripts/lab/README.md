# Wick v2 lab

Many small variations of the AI-filtered resting-bid dip buyer, scored with realistic Coinbase US perp costs.
Rules, periods and adoption bars are pre-registered in `reports/wick_v2_prereg.md`.

| Step | Command | Output (reports/lab/) |
|---|---|---|
| Round 1 (105 single changes) | `python run.py round1` | results_val_round1.csv, daily_*_round1.parquet |
| Round 1b (5 more, logged before results) | `python run.py round1b` | ..._round1b |
| Validation-only analysis | `python analyze.py` | (printed) |
| Round 2 (combinations, built mechanically) | `python run.py round2` | ..._round2 |
| Fix the shortlist (validation only) | `python shortlist.py` | shortlist.json |
| Bar 3: perp-priced check | `python futures_check.py` and `QUIET=1 python futures_check.py` | futures_check*.csv |
| Open the holdout | `python analyze.py --holdout` | holdout_report.csv, overfit_stats.json |
| Apply the bars | `python decide.py` | v2_decision.json |

## Cost models
- **real** (selection): $0.20 per contract per side on every fill, 1.5x the measured perp half-spread on
  market exits, 1 bp funding per trade, whole contracts.
- **adv** (reported): the advertised US perp schedule. 0% maker and 0.03% taker, 1.5x the half-spread on
  market exits, 1 bp funding.
- **base** (v1 continuity): 2 bp per side, plus one perp tick on market exits.

## Code
- `core.py`: the shared pieces.
  - Data, level sets and features; the extra feature sets are known at t-1.
  - Exit kernels (numba): take-profit, two-stage, fair-value tracking, early stop, passive time exit.
  - Cost models.
  - Walk-forward LightGBM.
  - Sequential per-coin books, the perp-candle execution and the whole-contract portfolio.
- `variants.py`: every variant as a change to the v1 base, plus the round-2 combination rule.
- `run.py`: groups variants by level set and caches labels and trades.
