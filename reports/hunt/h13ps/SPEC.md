# H13 (PS): the switch from limit-only to full trading on Coinbase's new spot listings (loop 3)

Fixed before any build of this idea. Same pre-registration (reports/hunt_prereg.md) and gates. Read
reports/hunt/BUILDER_GUIDE.md first.

## Mechanism
- Coinbase opens a new spot market in phases: transfer-only, then an auction (at least 10 minutes, limit orders only),
  then limit-only, then full trading. Older listings went post-only → limit-only → full trading.
- Market and stop orders are rejected until full trading. That comes 10 minutes to about a day after limit-only, at a
  time Coinbase publishes on its exchange status page (research memo R2, E5: SUI 24 h, SPK 21.7 h, BIGTIME 14.6 h).
- **Who is forced or eager:** buyers who can only use market orders (app and simple-trade users, stop and bracket
  users, some bots) cannot act until the switch, then all arrive at once.
- **Why we're paid:** inventory bought from limit-only sellers is sold to them at the switch, or a fast buyer rides
  the demand they bring.
- **Not H4:** H4 rested bids under fair value through days 0–30 and was paid by snap-backs after dumps. This trades one
  timestamped demand shock.
- **Prior:** 5 of 10 (ideas.md #46). R2 found no prior evidence either way.

## Events and data
- **Phase times:** the incident history of status.exchange.coinbase.com (Atlassian Statuspage).
  - Fetch it on Actions with a plain research User-Agent and at least 1 s between requests. Use the JSON endpoints
    where they exist (`/api/v2/incidents.json`, `/history.json?page=N`, `/incidents/<id>.json`), else the HTML pages.
  - No header spoofing. If the site refuses a plain client, stop and report the idea as blocked.
  - Parse every listing incident. T_lo is the update that enters limit-only mode; T_ft is the update that says the
    pair is now in full-trading mode. Keep the auction and post-only times too.
  - Commit the event table (reports/hunt/h13ps/events.csv) before fetching any price.
- **Universe:** every USD spot pair with both T_lo and T_ft, 2022-01-01 → 2026-11-05.
  - Excluded: stablecoins, fiat-backed and wrapped assets, and relistings.
- **Prints:** common.TradeFetcher from T_lo − 10 min to T_ft + 3 h (Advanced Trade; the Exchange API fallback for
  delisted products). Sizing also uses these prints.
- **Scored days:** gates.ERA_DAYS (2022–23 and 2025-01-01 → 2026-11-05). 2024 events only train the AI variant.
  DEV ends 2026-05-31.

## Trades (fixed; long only, spot)
- **Live detection:** a bot polls the product's status flags (limit_only, post_only) every few seconds, so T_ft is
  known within seconds.
  - Use the status-page time as T_ft.
  - Report the leak diagnostic: the mean move from T_ft − 10 min to T_ft against the move after it. Also report
    whether volume jumps before the posted time.
- **Mode I, inventory into the switch:**
  - From T_lo + 60 min, rest a post-only bid one tick under the last print, refreshed every minute.
  - Fill when a later print trades through it by one tick. Size ≤ θ × through-volume (θ = 0.5; 0.25 also reported),
    up to the target size.
  - Stop bidding at T_ft. Sell everything held at T_ft + H with a taker order.
  - No trade if T_ft − T_lo < 60 min. If full trading never comes, exit at T_lo + 48 h.
- **Mode II, after the switch:**
  - Taker buy at the first print at least Δ after T_ft (Δ ∈ {2 s, 60 s}), paying 1.5× the measured half-spread.
  - Taker sell at T_ft + H.
- **Horizon:** H ∈ {5, 30, 120} minutes.
- **Target size:** min($5K, 5% of the USD volume printed in the 60 minutes before the decision), known at the decision.
- **Costs:** spot 6 bp maker and 12.5 bp taker.
  - Taker legs pay max(1.5 × measured half-spread, 2 bp) on top.
  - Half-spread: from opposite-aggressor print pairs in the 10 minutes before each leg, with H5's fallbacks.
  - 2× fees and half-spreads for the gates.
- **Cash:** open notional ≤ sleeve capital ($30K and $50K).

## Trial grid (≤ 10, all logged with gates.dev_book)
- **Mode I:** H ∈ {5, 30, 120}. 3 trials.
- **Mode II:** Δ ∈ {2 s, 60 s} × H ∈ {5, 30, 120}. 6 trials.
- **AI filter on the best of the nine:** 1 trial.
  - Walk-forward LightGBM by quarter, from the first quarter with at least 30 earlier events.
  - Features known at the decision: limit-only duration so far, USD volume in the limit-only phase, the move since
    the end of the auction, the BTC 4-hour move, and the number of other listings that week.
  - Keep a trade if its predicted net bp is positive.
- **Selection:** the highest DEV alpha t with at least 40 trades.

## Checks to report
- Events by year. The distribution of phase durations (auction, limit-only).
- Mean and median gross move from T_lo + 60 min to T_ft, and from T_ft to T_ft + H.
- Participation: our size against the aggressive buyer flow of the first minute after T_ft.
- Half-spread before and after the switch.
- Overlap with H4's events (same coin and day). Correlation with the incumbent. Top-3 days' share of P&L.
