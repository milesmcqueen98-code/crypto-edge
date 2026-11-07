# H5 (AN): Binance listing/launch announcements traded on Coinbase spot

Written by builder h5an. Committed by the coordinator, because subagents here can't write .md files.

**Verdict: FAILS.** At 2x costs it fails G1 (t 2.87), G2 (HOLD t 0.31, gain +0.08) and G3 (gain +0.22). It passes G4
(DSR 0.956, marginal) and G5. The drift is real but needs near-instant detection: it is gone by Δ = 10 s. A
conservative fill bound turns the DEV P&L negative.

## Mechanism
Binance announces a spot listing, perp launch, margin/earn addition or airdrop for a token that already trades on
Coinbase. Binance-driven buyers and cross-venue arbitrageurs reprice it on every venue within seconds. The question
was what drift is left for a polling bot 2–30 s later on Coinbase spot (taker in, market out).

## Data actually used
- **Events:** Binance CMS catalog 48, paged on a GitHub runner with a plain research User-Agent and 2 s between pages.
  No refusal. 1,394 articles from 2022-01-04 to 2026-10-29, ms `releaseDate`.
- **Classifier:** titles → classes, written and committed before any price was fetched (commit c7d89c5).
  - Class v (dropped): routine items, secondary-margin perps (USDC/BUSD/COIN-M), stables, wrapped tokens, bStocks and
    TradFi items.
  - Three ticker collisions dropped by name/listing date: AI, EDGE, LIT.
- **Prices:** Coinbase spot prints from −60 min to +150 min for all 500 candidate ticker-events.
  - Online products: common.TradeFetcher (Advanced Trade).
  - Delisted products: Advanced Trade returns 404, so the Exchange API was paged by trade id (no survivorship gap).
  - Sizing: daily candles before the event day.
- **Usable events** need prints in the hour before release (SPEC). 273 of 500 failed; 236 of those were tokens
  Coinbase listed only after the announcement.

| Class | 2022 | 2023 | 2024 (train) | 2025 | 2026 | Total |
|---|---|---|---|---|---|---|
| i spot listing | 5 | 4 | 5 | 6 | 6 | 26 |
| ii perp launch | 9 | 30 | 18 | 22 | 14 | 93 |
| iii margin/earn/convert | 25 | 47 | 9 | 12 | 7 | 100 |
| iv HODLer/Launchpool | 0 | 0 | 0 | 5 | 3 | 8 |

- Scored trades: 184 DEV + 11 HOLD.
- Articles by class: i 99, ii 417, iii 282, iv 137, v 459.

## DEV checks (216 DEV events incl. 2024)
- **Leak diagnostic:** the mean move from −10 min to release is +4 bp, against +594 bp by +2 h.
  - Spot listings: +54 bp of +2,775 bp. Perps: +3 of +592.
  - So `releaseDate` does **not** lag publication. The jump starts after it: +141 bp at +2 s, +308 at +5 s, +431 at
    +30 s, +577 at +5 min.
  - The converse risk is untestable on history: the article may become visible to a public poller only 1–3 s after
    `releaseDate` (R2 reports ~1 s CDN cache). Δ = 2 s then front-runs visibility.
- **Share of the −10 min → +5 min move already in the entry price:**

| | Δ = 2 s | Δ = 10 s | Δ = 30 s |
|---|---|---|---|
| All classes | 27% | 61% | 76% |
| Spot listings | 6% | 41% | 51% |
| Perps | 44% | 73% | 92% |

- **Mean gross entry → exit (bp), all classes:**

| | H = 5 min | H = 30 min | H = 120 min |
|---|---|---|---|
| Δ = 2 s | +427 | +505 | +435 |
| Δ = 10 s | +236 | +307 | +240 |
| Δ = 30 s | +163 | +222 | +160 |

  - Medians are far lower (+101 bp at Δ 2 s / H 5 min).
  - Class iii (margin adds) is about +37 bp gross: below costs.
- **Coinbase half-spread in the 10 min before:** median 5.1 bp, p75 10.6 bp.
  - Round trip at 2x: about 80 bp at the median spread; 113 bp on average in the selected variant.

## Trials (20 logged to reports/hunt/trials.csv; the sleeve is $30K at 2x, alpha t on the incumbent at $70K)
| Variant | DEV sleeve SR (2x) | DEV alpha t | Trades | Mean net, 2x (bp) |
|---|---|---|---|---|
| d2 h5 spot / h30 / h120 | 1.18 / 1.19 / 1.24 | 2.26 / 2.28 / 2.35 | 19 | +1598 / +1790 / +2159 |
| d10 h5 spot / h30 / h120 | 0.22 / 0.43 / 0.68 | 0.43 / 0.84 / 1.29 | 19 | +855 / +1026 / +1402 |
| d30 h5 spot / h30 / h120 | −0.16 / 0.09 / 0.50 | −0.29 / 0.21 / 0.95 | 19 | +661 / +825 / +1201 |
| **d2 h5 all** | **1.50** | **2.86** | **184** | **+244** |
| d2 h30 all / h120 | 1.24 / 0.79 | 2.43 / 1.49 | 184 | +306 / +259 |
| d10 h5 all / h30 / h120 | 0.07 / 0.42 / 0.13 | 0.31 / 0.88 / 0.28 | 184 | +78 / +122 / +85 |
| d30 h5 all / h30 / h120 | −0.57 / −0.02 / −0.13 | −0.91 / 0.02 / −0.20 | 184 | +24 / +55 / +19 |
| AI regression filter (d2 h5 all) | 1.27 | 2.39 | 99 | +376 |
| AI classifier filter (d2 h5 all) | 0.99 | 1.94 | 74 | +416 |

- **Fade (short via Coinbase perps):** not run. Zero DEV events had a Coinbase perp at release; two HOLD events (HYPE)
  did.
- **AI:** walk-forward LightGBM by quarter; first eligible quarter 2022Q4, with at least 30 training events required.
  Features known at the decision: class, log 30-day volume, the move from −10 min to the last print at least 1 s old,
  the BTC 60-min move, hour.

## Frozen variant (frozen.json, freeze commit 1c05af4, pushed before HOLD was read)
`core_d2_h5_all`: Δ = 2 s, H = 5 min, classes i–iv.
- Size: min($5K, 1% of the 30-day median USD volume).
- Selected by the fixed rule: highest DEV alpha t with at least 20 trades.

## Gates (Path B, a = 0.7 chosen on DEV; gates.json)
| | 2x (gates) | 1x (info) |
|---|---|---|
| G1 full alpha t ≥ 3 | **2.87, FAIL** | 3.55 |
| G2 HOLD t ≥ 1.5 and gain ≥ +0.25 | **t 0.31, gain +0.08, FAIL** | t 0.52, gain +0.18 |
| G3 full gain ≥ +0.5 | **+0.22, FAIL** (book 2.68 vs incumbent 2.47) | +0.36 |
| G4 DSR ≥ 0.95 (N = 3,020) | **0.956, PASS** | 0.979 |
| G5 no losing year (book) | **PASS:** 2022 +10.7%, 2023 +19.3%, 2025 +32.8%, 2026 +16.9% | PASS |

- **HOLD:** 11 trades, mean net +141 bp at 2x (DEV +244); sleeve Sharpe 0.56.
- **Sleeve at 2x on $30K by year:** +6.1%, +18.9%, +20.2%, +12.3%. Full-period sleeve Sharpe 1.42 vs the
  incumbent's 2.47, so Path A does not apply.
- **G4 is marginal.** It was computed when the ledger held only these 20 trials, and will fall as other builders log
  theirs.
- **Correlation with the incumbent:** −0.02. On the incumbent's 20 worst days the sleeve averaged −5 bp.
- **Concentration:** the top 3 events are 30% of P&L; the top 3 days are 32%.

## Capacity actually filled
- Mean trade $3,860; 64% hit the $5K cap.
- Peak open notional $15K, so the cash cap never binds. $50K gives the same dollar P&L as $30K.
- The sleeve is idle on most days: 195 trades over about 1,400 scored days.

## Fill-realism checks (after the freeze; information only; checks.json)
- **Side convention:** 85% of buyer-initiated prints (`side` = "SELL") tick up, confirming the maker-side reading.
- **Participation:** the median trade is 0.92x all buyer-initiated USD printed in the 10 s after our entry print. In
  44% of trades it exceeds half the buyer flow of the next 60 s.
  - A $5K market buy in a jumping book is therefore not a 1.5x half-spread trade.
- **Worst-print bound:** entry at the highest print in the 10–20 s around the entry, exit at the lowest around the
  exit, taker fee only.
  - Mean net goes to −0.6 bp at 1x and −26 bp at 2x on DEV; −120 bp at 2x on HOLD.
  - Sleeve Sharpe −1.34; DEV alpha t −2.17.
  - This bound is pessimistic, since it partly charges the drift itself, but the sign flip shows the result depends on
    fill assumptions.
- **Entry timing:** the median actual entry is at +3.1 s. 25% of entries come after +10 s and 8% after +60 s on thin
  coins, where the next print stands in for the unobserved ask at +2 s.

## Weaknesses
1. **Latency is everything.** The alpha t falls from 2.86 (Δ 2 s) to 0.31 (Δ 10 s) and −0.91 (Δ 30 s).
   - A public poller sees the article about 1–3 s after `releaseDate`, with ~1 s CDN cache, and Binance's announcement
     WebSocket needs a signed key a US person cannot hold.
   - So the realistic result lies between Δ 2 s and Δ 10 s.
   - It cannot be verified without logging first-seen time minus `releaseDate` live.
2. **Impact:** the trade size is comparable to the whole aggressive flow in the seconds after entry (see the checks
   above).
3. **Class mix:** class iii (routine margin/earn adds) loses money after costs (−77 bp mean net at 2x, −$2.3K on DEV).
   - The spot-listing signal (+1,600 bp mean) is real but rare: 19 DEV trades, about 5 a year.
4. **Thin HOLD:** 11 events, so G2 was near-unreachable for this sleeve.

## Deviations and engineering choices (all fixed before any trial was scored)
- **Half-spread:** if the 10 min before have fewer than 3 opposite-aggressor pairs, use 60 min with gaps of 10 s or
  less, then 60 min with any gap, then 50 bp (4 events).
  - The charge per side is max(1.5x half-spread, 2 bp), the common.py floor.
- **30-day volume:** median of daily candles before the event day; two events fell back to 24x the prior hour.
- **Missing exits:** a fallback exits at the last print. It was never triggered in the frozen variant.
- **Cash:** open notional is capped at the sleeve capital.
- **Delisted products:** fetched through the Exchange API (19 of 195 scored trades).
- **Grid run twice:** the 20-trial DEV grid ran once without logging, to confirm it completes, then once with logging.
  Code and numbers were identical; nothing was added or changed in between.
- **Fade:** not run (no eligible DEV events).
- **No redesign** after reading HOLD.

## Reproduce
In scripts/hunt/h5an/:
- fetch_articles.py, fetch_meta.py, fetch_trades.py (run on Actions)
- events.py
- dev.py --log
- final.py
- checks.py
