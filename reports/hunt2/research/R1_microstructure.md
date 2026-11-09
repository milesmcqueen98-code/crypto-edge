# R1: microstructure mechanisms (research agent memo, Nov 8 2026) — summary

Delivered by the R1 research agent (web budget exhausted before every point was verified; Harris and
Cartea–Jaimungal–Penalva read through a review and a related paper).

## Headlines
1. **Temporary vs permanent impact is the key split.** Isolated, uninformed metaorders' impact decays to about zero
   (Mt.Gox: Donier & Bonart 2015, δ ≈ 0.5, Y ≈ 0.9, https://arxiv.org/abs/1412.4503); informed flow keeps ≈ ⅔ of
   the peak (Farmer, Gerig, Lillo & Waelbroeck 2013; Gomes & Waelbroeck 2015). A take-profit at 60% of the dislocation
   is paid on forced flow and loses on informed flow; the filter's job is to tell them apart.
2. **Path A leaders (prior 6):** A1, a square-root-law impact residual from Coinbase prints, f = ΔP_res / (Y σ_D
   √(Q/V_D)) with Q the net taker selling since the dislocation began (a drop larger than its flow explains is
   information); A2, Hyperliquid's forced-flow label (liquidation fills, OI change) — history only via node data or
   paid indexers.
3. **Path B is thin (priors ≤ 4):** a mirror ask ladder on CFM alt perps for short squeezes; fading weekend
   non-crypto perps toward Hyperliquid prices (≈ 17% of a weekend move reverses at the reopen, Blockworks Intel 2026).
4. Queue imbalance, OFI, microprice, VPIN: sub-second or redundant; passive quoters were run over on Oct 10 2025.
5. Decay arithmetic: with impact-decay exponent β ≈ 0.5, 60% of peak impact has reverted by ≈ 2.1× the selling's
   duration (matches a 60% take-profit and a 60-minute exit for 15–20-minute cascades); equity-like β ≈ 0.2 leaves
   ≈ 67% at 3×.

## Candidates (prior /10)
A1 impact residual (6) · A2 Hyperliquid liquidation/OI label (6) · A3 Hyperliquid lead gate (4) · A4 endogenous vs
exogenous: volatility ramp, Hawkes n̂, breadth (4) · A5 liquidity-provider scarcity, Kyle λ and Roll vs 6-month
medians (4) · A6 volume-time exits (3) · A7 round-dollar retail signature (3) · A8 scheduled sellers: public HL TWAPs,
periodic child orders (3) · A9 bid-cancellation bursts in the full feed (3) · B1 mirror ask ladder on CFM alt perps
(4) · B2 weekend non-crypto perps vs Hyperliquid (4) · B3 cross-margin spill-over wicks in CFM non-crypto perps (3) ·
B4 BRRNY benchmark-hour liquidity vs predicted ETF flow (3).

## Key facts (with sources as given)
- Latent-order-book model: mechanical impact relaxes completely; I(t)/I(T) = √(t/T) − √(t/T − 1) after a metaorder of
  length T (Donier, Bonart, Mastromatteo & Bouchaud 2015, https://arxiv.org/abs/1412.0141).
- Equities: ≈ 0.66 of peak impact remains at the close, β ≈ 0.22 (Bucci et al. 2019, https://arxiv.org/abs/1901.05332).
- Hyperliquid TWAPs are public at submission (median $9.1k; Barone & Lillo 2026, https://arxiv.org/abs/2606.15715).
- Oct 10 2025: BTC best-quote depth fell > 90%; Hyperliquid liquidated ≈ $2.1B between 21:16 and 21:27 UTC;
  depth recovered to only 66–79% of pre-event levels (FTI 2025; Chitra et al. 2026; Lim 2026).
- Hawkes branching ratio ≈ 0.8 for BTC on BitMEX (Mark, Sila & Weber 2022); exogenous vs endogenous jumps differ in
  their volatility profile (Marcaccioli, Bouchaud & Benzaquen 2022, https://arxiv.org/abs/2106.07040).
- Queue imbalance AUC 0.75–0.80 for large-tick stocks, 0.58–0.64 small-tick (Gould & Bonart 2016); OFI market making
  built a losing long on Oct 10 (Bieganowski & Ślepaczuk 2026).
- BRRNY: twelve 5-minute volume-weighted medians, 15:00–16:00 ET; ≈ $220M traded on Coinbase in that hour (Kaiko 2024);
  FX 4 pm fix shows negative serial correlation (Evans 2018).

## Data notes
- A2/A3/A8 need Hyperliquid history beyond the public API (node data, Allium, Dune, Hydromancer: keys or requester-pays)
  → blocked for this round; forward-collect.
- B2/B3: CFM index perps listed Jun 15 / Aug 17 2026 → no DEV history → blocked this round.
