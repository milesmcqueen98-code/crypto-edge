# Ladder v5 (Nov 7-8 2026): execution-trader round on the spot ladder

**Result: no change to the trading rules is adopted.** Of 11 pre-registered candidates, four passed the gates in the
frozen simulator; the red teams removed the two trading changes that carried the gain. C4 (idle cash as USDC) goes to a
live check; C2a (size by the AI's margin) and C7b go to a re-test on new data. The incumbent is better than the frozen
estimate once exits are priced from prints and the cash rule is replayed as the engine runs it.

## Verdicts
| Candidate | Logged pooled t (S*, theta 0.5) | Red team | Verdict | Score after red teams (as logged) |
|---|---|---|---|---|
| C4 USDC cash | +3.06, all gates | reproduces to 1e-14; payment to this account unverified | forward-test (live check) | 71 (78) |
| C2a margin terciles | +2.21, all gates | out of sample +1.33; +1.91 with print exit costs (G1 fails) | forward-test (re-test) | 57 (75) |
| C1a deeper first | +1.94 | +1.40 on an engine-faithful replay | reject | 51 (53) |
| C7b sweep tilt | +1.51 | - | forward-test by rule | 49 (49) |
| C3b passive exit 15 min | +7.71, all gates | -0.06 to +0.04 with print-measured exit costs and fills | reject | 37 (84) |
| C3a passive exit 5 min | +7.08, all gates | same | reject | 35 (85) |
| C1b, C2b, C6, C7a, C5 | -1.56, -0.41 (Sharpe path), -0.99, -1.37, -1.93 | - | reject | 34, 33, 28, 26, 21 |

Joint re-test (rule logged before any joint trial): every set passed in the frozen simulator (C2a+C3b+C4 t +4.90), but
no component is adopted, so nothing reaches the bot.

## Best estimate of the live incumbent ($250K, today's volumes, unverified costs doubled, theta 0.5)
22.8% / 19.1% / 11.1% a year, Sharpe 2.94 / 2.66 / 1.91 (selection Jan 2025 - Mar 2026 / check Apr - Nov 5 2026 /
2022-23), against the frozen simulator's 19.5% / 15.1% / 10.4% (2.31 / 2.31 / 1.72). At $1M: 15.0% / 8.5% / 5.1%
(2.28 / 1.47 / 0.73). Sources: red team 1 (engine-faithful cash rule) with red team 2's print-measured exit costs.

## Files
- `../ladder_v5_prereg.md`: the pre-registration (frozen at 7ae53cb) and its deviation log, including the verdicts.
- `trials.csv`, `trials/`: the 15 logged trials (11 candidates, 4 joint) merged from the builder branches.
- `scorecard.csv` (as logged) and `scorecard_adjusted.csv` (after the red teams; inputs in `redteam_records/`);
  hand-scored parts with reasons in `scorecard_manual*.json`.
- Builders: `sizing/`, `exits/`, `cashvenue/`, `sweep/` (REPORT.md each; C1 ran from `scripts/ladder_v5/cand_cash.py`).
- Red teams: `redteam/REDTEAM.md` (cash rule, C1a, winners on an engine-faithful replay), `redteam2/REPORT.md` (C2a,
  C3 on 17.2M Coinbase prints), `redteam3/REPORT.md` (C4, USDC). Their code and data stay on branches ladder/redteam,
  ladder/redteam2, ladder/redteam3.
- `joint/`: reproduction checks and the leave-one-out tables (rule (b)); code on branch ladder/joint.
- Diagnosis: `diag_*.csv/txt` (markouts by fill type, oracle prizes, P&L decomposition, holds, prints).
- Bot changes (branch ladder/v5-bot, merged to main): a coin with unknown volume no longer bids an uncapped size; the
  optional USDC quote with `run.py usdc-check`; tests.
