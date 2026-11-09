# MAC: scheduled US macro releases (blackout filter for the ladder) — DRAFT, not frozen

- **Path:** A (the live bot with its bids pulled around scheduled releases, on the frozen simulator at $250K).
- **Who is forced or eager, and why we are paid (or not):** at a scheduled release (CPI, NFP, PPI at 08:30 ET; FOMC
  statement at 14:00 ET) prices move on public information, not on forced flow. Dip bids resting through the release
  are filled by sellers who are informed by the release (Glosten–Milgrom adverse selection; liquidity providers widen
  or pull before scheduled news), and the dislocation from the BTC-adjusted fair value is a re-pricing (alts with a
  higher macro beta than their trailing BTC beta) rather than an overshoot. Pulling the bids avoids being the
  liquidity that informed traders hit. The release calendar is public and known in advance.
- **Prior evidence and what has been seen:** nothing computed on any era for this rule. R2-08's AI has no calendar
  feature.
- **Data:** official release calendars (data/hunt2/macro/releases.csv: CPI 57, NFP 58, PPI 57, FOMC 40 dates,
  2022-01 .. 2026-12); research parents of the frozen dataset; Coinbase prints around affected parents (from the
  shared parent prints) to confirm the fill times.
- **Live inputs and orders:** the BLS/Fed calendars; cancel resting bids before the window, no new bids inside it.
- **Rule (frozen grid, 6 trials):** no 4σ bid rests in any coin during [release − a, release + b] (the multiplier
  of every coin's 4σ bid is SKIP in those minutes, so a parent filling there does not exist; ladders armed earlier keep
  their deeper rungs): (a, b) ∈ {(5, 30), (5, 120), (30, 240)} minutes × event set ∈ {CPI+NFP+FOMC,
  CPI+NFP+FOMC+PPI}.
- **Minimum events:** a variant must skip ≥ 10 DEV parents to be eligible; if no variant does, the idea is reported
  as untestable at this power and not frozen.
- **Costs:** frozen simulator at X2 (selection, gates), X1 (gate A2), S (reported).
- **Selection statistic:** highest DEV paired HAC t at X2; ties → the narrower window.
- **Capital:** $250K. **Outputs:** reports/hunt2/mac/.
