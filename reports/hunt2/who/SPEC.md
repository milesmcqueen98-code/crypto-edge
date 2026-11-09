# WHO: who sold into our bid (pre-fill order-flow composition filter)

- **Path:** A (a modification of the live bot, run on the frozen simulator at $250K).
- **Who is forced or eager, and why we are paid:** the ladder is paid by forced, uninformed sellers: liquidation
  engines, stop orders and retail panic, which arrive as bursts of many small and mid-size aggressive orders and
  sweeps into a thinning book (Grossman–Miller; Harris's "liquidity demanders"). It loses to informed sellers:
  news-driven or insider selling and institutional metaorders, which arrive as large, concentrated, persistent
  aggressive orders (Kyle; Glosten–Milgrom; Bouchaud et al., metaorders' long memory). The composition of the
  aggressive selling in the minutes before our fill separates the two, and the bot can see it live in Coinbase's
  public trade feed and cancel the bid (or skip the ladder) before the fill.
- **Prior evidence and what has been seen:** ladder v5 read fill-minute print features on the selection era
  (reports/ladder_v5/diag_prints_sel.txt: sweep counts, taker-sell share and first-sweep depth at the fill) and built
  C7a/C7b (deeper-rung skip/tilt by the first sweep), rejected/forward-test. Nothing has been computed on the
  PRE-fill window, on trade-size composition, or on any hold-out era for these features.
- **Data:** Coinbase spot prints in [fill minute − 30 min, fill minute + 2 min] for every research parent of the
  frozen dataset (2,311: DEV 1,155; HOLD 412 chk + 744 early), fetched on Actions (reports/hunt2/parents/windows.csv,
  scripts/hunt2/prints.py), features computed on the runner (scripts/hunt2/parent_features.py). DEV features are
  committed first; HOLD features only after the freeze.
- **Live inputs and orders:** Coinbase's public market_trades WebSocket channel (prints), the bot's own fill list;
  cancel of the resting post-only 4σ bid (and no deeper rungs) when the rule fires.
- **Features** (aggressive orders = consecutive prints with the same timestamp and maker side; all use prints at
  least 1 s before the fill; W = minutes before the fill):
  1. `sell_bigadv_share_W`: share of aggressive-sell dollars in orders ≥ 5 bp of the coin's 30-day ADV (blocks).
     Skip when HIGH.
  2. `sell_hhi_W`: Herfindahl concentration of aggressive-sell order sizes. Skip when HIGH.
  3. `sell_share_W`: aggressor-sell share of all printed dollars. A drop that is not driven by aggressive selling is
     makers repricing (pulling bids): an informed move. Skip when LOW. (Replaces a small-order share after memo R3:
     trade-size mix carried no reversal information where tested, while order-flow-driven moves reverted more.)
  4. `rate_ratio_1`: prints in the last minute vs the 30-minute average (a frenzy vs a slow drift). Skip when LOW.
     (W is fixed at 1 for this feature; its second variant uses `rate_ratio_5`.)
- **Rule (frozen grid, 16 trials):** 4 features × W ∈ {5, 15} (rate ratio: {1, 5}) × removal share ∈ {15%, 30%}.
  The threshold is the DEV quantile of the feature over DEV parents that removes that share; it is then fixed in
  absolute units for HOLD. Parents with missing features (no prints) are kept.
- **HOLD protection:** the feature's values on HOLD days (and any threshold or distribution from them) are computed or
  read only after the freeze commit.
- **Costs:** frozen simulator at X2 (selection and gates), X1 (gate A2) and S (reported).
- **Fills and latency:** the frozen simulator's (1-second blend); the filter uses prints ≥ 1 s old at the fill.
- **Selection statistic:** highest DEV paired HAC t at X2 (h2gates.dev_screen_a); ties → the smaller removal share.
- **Capital:** $250K. **Outputs:** reports/hunt2/who/ (REPORT.md, frozen.json, gates.json, daily.parquet with
  columns x2, x1, s over the scored days).
