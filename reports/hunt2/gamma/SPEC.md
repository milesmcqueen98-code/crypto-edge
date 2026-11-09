# GAMMA: dealer gamma regime (Deribit) as a filter on the ladder

- **Path:** A (the live bot skipping bids while option dealers are short gamma; frozen simulator).
- **Who is forced or eager, and why we are paid (or not):** option dealers delta-hedge. When they are net LONG gamma
  they buy as price falls and sell as it rises: they are a second dip-buyer beside the ladder, moves mean-revert, and
  a cascade meets their bids. When they are net SHORT gamma (customers bought puts) they must SELL into a fall: their
  hedging is forced, procyclical selling that extends a cascade past the ladder's 60-minute horizon and makes the
  dislocation a continuing move (Baltussen et al. 2021: intraday momentum appears only when dealers are short gamma;
  Pearson, Poteshman & White 2006: more dealer gamma, smaller moves). The alts' cascades ride BTC's; BTC's dealer
  gamma conditions how far the market keeps falling.
- **Prior evidence and what has been seen:** the Medallion round's short-volatility test used DVOL only; Deribit
  pinning was blocked for lack of open-interest history (first hunt). Nothing computed on any era. R2 rated a
  dealer-gamma regime filter 4/10.
- **Data:** every BTC option trade on Deribit from 2021-01 (history.deribit.com: instrument, taker direction, amount,
  implied vol, index price), fetched on Actions; Deribit's expired-instrument list for strikes and expiries; the
  first-of-month open-interest anchor is not needed (inventory = −cumulative taker volume per instrument, and every
  option live in 2022–2026 was listed after 2021-01; options listed before are flagged and excluded).
- **Live inputs and orders:** Deribit public market data (live via Coinbase-hosted Deribit endpoints; Deribit's own
  terms bar US accounts, not data access; the bot only reads); skip the 4σ bids.
- **Signal (hourly, at h−1):** dealer inventory per live option = −Σ(taker-signed contracts) since listing; dealer
  net gamma G = Σ_options inventory × Black–Scholes gamma (at the option's last traded implied vol, the index price,
  time to expiry) × S² × 1%, in BTC per 1% move, also split into gamma from strikes below spot (G_below).
- **Rule (frozen grid, 8 trials):** skip every coin's 4σ bids while the signal is below a threshold: signal ∈ {G,
  G_below} × threshold ∈ {0, the DEV 25th percentile of the hourly signal} × expiry scope ∈ {all live options,
  options expiring within 30 days}.
- **HOLD protection:** the feature's values on HOLD days (and any threshold or distribution from them) are computed or
  read only after the freeze commit.
- **Costs:** frozen simulator at X2 (selection, gates), X1 (gate A2), S (reported).
- **Selection statistic:** highest DEV paired HAC t at X2 with 5–50% of DEV parents skipped; ties → G, threshold 0,
  all options.
- **Scored days:** all eras (inventory from 2021-01). **Capital:** $250K. **Outputs:** reports/hunt2/gamma/.
- **If Deribit history is unreachable from the runners**, the idea is reported as blocked (not built) and the next
  idea in line replaces it.
