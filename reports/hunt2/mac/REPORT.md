# MAC: pull the ladder around scheduled US macro releases (Path A)

Builder: events. Branch h2/events. SPEC: reports/hunt2/mac/SPEC.md (frozen with the pre-registration).
Code: scripts/hunt2/mac/mac.py (`dev sel`, `freeze`, `hold`, `post`).

## Definitions (written before any trial)
- **Releases:** data/hunt2/macro/releases.csv (official BLS and Fed calendars; `ts_utc` = the release minute in UTC,
  daylight saving handled in the file). CPI, NFP, PPI at 08:30 ET; FOMC statement at 14:00 ET. DEV holds 14 CPI,
  14 NFP, 14 PPI and 10 FOMC releases (the autumn-2025 shutdown moved or cancelled some).
- **Window:** minute rows `release - a` to `release + b`, both ends included, of `frozen_sim.arrays(era)["idx"]`. In each
  of those rows every coin's 4-sigma multiplier is `frozen_sim.SKIP`; elsewhere it is 1. So no 4-sigma bid rests in any
  coin from `release - a` until the end of minute `release + b` (bids are cancelled at the start of the window and
  re-placed at the minute after it). A parent whose fill minute is in a window carries ~0 dollars; ladders armed
  earlier keep their deeper rungs (a rung's size is the multiplier at its parent's fill minute).
- **Grid (6 trials):** (a, b) in {(2, 10), (5, 30), (5, 120)} x events in {CPI, CPI+NFP+PPI+FOMC}.
- **Skipped parents (eligibility):** DEV research parents (`pathA.parents("sel")`) whose (fill minute, coin) cell is
  SKIP. A variant is eligible with >= 10.
- **Selection:** the highest DEV paired HAC t (X2, $250K) among eligible variants; ties -> the narrower window (fewer
  DEV blackout minutes). If no variant is eligible, MAC is reported untestable and not frozen.
- **Fill-time check:** for every skipped DEV parent, the first trade-through print (reports/hunt2/parents/
  features_dev.csv `t_fill`, from the shared parent prints) is compared with the release time.

(Results follow after the trials, the freeze and the HOLD read.)
