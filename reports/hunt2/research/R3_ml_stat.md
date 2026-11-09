# R3: ML and statistical mechanisms (research agent memo, Nov 8 2026) — summary

Delivered by the R3 research agent (≈50 searches, ≈45 fetches; 2026 arXiv papers cited are not peer reviewed).

## Headlines
1. No crypto study shows López de Prado microstructure features (VPIN/BVC, Kyle/Amihud, Roll, entropy) predicting
   DIRECTION after sharp drops out of sample and after costs; where tested they predict volatility-type targets at
   AUC ≈ 0.53–0.58 (Easley, O'Hara et al. 2024, https://stoye.economics.cornell.edu/docs/Easley_ssrn-4814346.pdf).
   Trade size carried no reversal information in the one study that tested it (arXiv:2608.21888, 183 Binance pairs,
   15-minute bars: AUC 0.536, gross edge ≤ 1.3 bp; reversal stronger after order-flow-driven bars, AUC 0.540 vs 0.519).
2. Edge per trade ≈ IC × σ(horizon) × selectivity: minute-horizon signals earn 0.5–1.3 bp gross against 12–18.5 bp
   retail round trips (≈85 independent signals of that strength would be needed). Weak signals pay only as filters
   inside the high-volatility cascade state.
3. Best priors (4–5/10): new data that identify forced selling directly — Hyperliquid basis (perp-led vs spot-led
   drop), HL open-interest depletion, HL wallet identity / liquidation flags; the drop's shape from candles (share of
   the drop in one minute, jump ratio, path efficiency); sell-flow exhaustion from Coinbase prints (exact aggressor
   side).
4. Sizing: in cascades cross-coin correlation is ≈ 0.85–0.90 (17 coins ≈ 1.1 independent bets, ≈ 20 such days), so
   estimated sizing rules should lose to equal size — consistent with the seven failed families.
5. Capacity/decay: square-root impact (Donier & Bonart 2015, Y ≈ 0.9 on bitcoin, https://arxiv.org/abs/1412.4503);
   the main decay risk is forced selling absorbed off the public book (Hyperliquid's backstop took ≈ 63% in Oct 2025,
   Garcia Seuma 2026, https://arxiv.org/pdf/2608.03616; 87.8% of forced selling in the first 30 minutes).

## Candidates (prior /10)
C1 perp-led vs spot-led (HL basis) 5 · C2 HL OI depletion 5 · C3 drop shape (candles) 4 · C4 sell-flow exhaustion
(prints) 4 · C5 cross-venue locality 4 · C6 liquidity withdrawal (EDGE spread, Kyle/Amihud vs 7-day) 3 · C7 HL wallet
"who is selling" 4 · C8 liquidation prints (Kraken Futures tag, 7-day REST) 3 · C9 Hawkes self-excitation 3 ·
C10 time since cascade start 3 · C11 overlap-aware training (uniqueness weights, episode-blocked CV) 3 ·
C12 signed jump variation 2 · C13 trade-size mix 2 · C14 post-fill model 2 · C15 R2-08 gate on Coinbase perps 3.

## Discarded by R3
BVC on candles (Coinbase prints give the aggressor exactly); VPIN (mechanically volume); Roll/Corwin–Schultz as direction
signals; entropy; SADF/CUSUM event filters (built for daily bubbles); second-stage models and ECDF sizing; Carver
buffering; standalone weak-signal strategies; early-warning pre-positioning; funding as a predictor (rank-IC −0.005;
interaction only); implied volatility (not live before IBIT options); deep order-book models (no history).

## Data notes
- Hyperliquid history beyond the live API (asset contexts, L2 snapshots, wallet-tagged trades since 2025-03-22) sits
  in Hyperliquid's archive; per the first hunt's probes the public API serves only funding history and ~3.5 days of
  candles, and the archive is requester-pays S3 (no credentials here) — so C1, C2, C7 are blocked for backtesting in
  this round and go to forward collection.
- Coinbase's `side` is the maker side, so the aggressor is exact (no BVC needed).
