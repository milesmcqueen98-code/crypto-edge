# R2: options, mechanical flows, events and game theory (research agent memo, Nov 8 2026) — summary

Delivered by the R2 research agent (≈45 searches, ≈55 fetches). Four equity papers are cited through later work only
(Gao–Han–Li–Zhou 2018; Cheng–Madhavan 2009; Shum et al. 2016; Bai–Bond–Hatch 2015).

## Headlines
1. **Leveraged-ETF rebalancing at the US close is the best new lead.** US crypto LETFs hold ≈ $3–3.5B and must trade
   ≈ 2 × AUM × the day's return into CME's 3:59–4:00 pm ET settlement: ≈ $30M per 1% BTC move (BITX + BITU ≈ $1.49B;
   ≥ $48M at the Nov 2024 peak), ≈ $17M per 1% ETH move (ETHU), ≈ $2–3M per 1% for SOLT/XXRP. Weekends/holidays (no
   rebalance) and staggered launches (6/2023, 4/2024, 6/2024) give controls. A 3% BTC day ≈ $90M ≈ 0.4× Coinbase's
   average 3–4 pm volume ($220M, Kaiko 6/2024).
   - Baltussen, Da, Lammers & Martens (2021, JFE), https://academicweb.nd.edu/~zda/intramom.pdf: across 62 futures,
     the return to 30 minutes before the close predicts the last 30 minutes (equity index β 4.18, t 7.3), only when
     dealers are short gamma, growing with LETF share; no crypto.
   - Barbon, Beckmeyer, Buraschi & Moerke (2021/2022), https://abarbon.com/papers/liquidity-provision-to-leveraged-etfs-and-equity-options-rebalancing-flows:
     LETF demand ≈ 9–11% of last-30-minute volume (AAPL, AMZN); ≈ 32% of LETF impact reverses by the next open;
     predictable LETF flows attract liquidity providers, so the effect shrinks.
   - Ivanov & Lenkey (FEDS 2014-106): investor flows offset much of the rebalancing on big days.
   - BITU is ~176% swaps on IBIT/FBTC with seven banks + ~24% CME; BITX holds CME futures.
2. **Deribit open interest is no longer blocked.** Coinbase-hosted Deribit endpoints (drb.coinbase.com) return option
   open interest with no key; history.deribit.com returns every option trade from 2021 with the taker's side, implied
   vol and index price, so dealer inventory = −cumulative signed taker volume per option. IBIT options (now the largest
   BTC options market) can only be logged forward.
   - Pearson, Poteshman & White (2006): +1 sd market-maker net gamma ≈ −37 bp next-day absolute return.
   - Deribit expiry 08:00 UTC on a 30-minute TWAP; expiring deltas fall linearly to zero across the window.
3. **Macro releases are information.** Only CPI moves BTC reliably over 30–60 minutes (Benigno & Rosa, NY Fed SR 1052:
   only CPI significant in a −5/+25 min window; Block Scholes 7/2026: −5.5% per 1 pp CPI surprise over 2020–26, R² 25%;
   nothing at 4–24 h). Pull ladder bids from 2 minutes before to 10 minutes after; prior 4 as a risk filter, ≈ 0 alpha.
4. **Prediction markets are out of scope** (Kalshi via Coinbase app only; no API; SIG makes those markets).
5. **CFM forced flows are small** (CFTC COT Oct 20 2026: nano BTC perp ≈ 1.7k BTC OI; ETH ≈ 23.8k ETH).

## Candidates (prior /10)
L1 LETF close pressure on the BTC/ETH factor (4) · L2 alt-LETF close pressure (3) · L3 post-close LETF reversal sleeve
(2) · G1 dealer-gamma regime filter from Deribit taker flow (4) · G2 bids beyond big dealer short-put strikes (2) ·
G3 Deribit Friday expiry unwind 07:30–08:00 UTC, direction from dealer inventory (3) · G4 IBIT expiry pin (2) ·
E1 macro blackout (4 as risk filter) · E2 alt overshoot after a release, re-arm with stress beta (3) · F1 CFM halt
spill-over (2) · F2 first perp listing anywhere, short-sale relief (3) · F3 Binance delisting deadlines (2) ·
F4 quarter-hour bursts (1; ≈ 0.5 bp) · R1 CME 24/7 as a risk to weekend wicks (monitor) · P1 Kalshi (out of scope).

## Discarded by R2
ETF NAV-fixing/creation flows (in-kind since 7/29/2025); treasury-company buying (OTC, disclosed after); recurring buys
(River 2026: 0.08% hour-of-day spread); US-perp listing as short-sale relief (offshore perps exist); CFM funding and
the 4 pm margin step-up (rejected; small OI); CME gap and BRR expiries (24/7; 12 a year); MSTR LETF flows (trade MSTR);
tax-loss selling (once a year); Kalshi longshot bias (not tradable here).
