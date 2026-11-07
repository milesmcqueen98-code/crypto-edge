# H13 (PS): the limit-only -> full-trading switch on new Coinbase spot listings

Builder h13ps, 2026-11-07, branch hunt/h13ps. Path B.
- **Event table:** commit 65ca6c9, made before any price was fetched.
- **Freeze:** commit d0d8277 (frozen.json; code a560365).
- **Verdict: FAILS G1, G2, G3 and G4; passes G5.**
  - The full-trading switch brings a small burst of aggressive buying, but it is tiny in dollars and well inside
    costs.
  - Inventory held into the switch loses, because new listings fall through the limit-only phase.

## Mechanism
- A new Coinbase book opens in phases: transfers, then auction (at least 10 min), then limit-only, then full trading.
  Market and stop orders are rejected until full trading.
- **Hypothesis:** market-order-only buyers arrive together at the switch.
- **Mode I:** holds inventory bought passively in limit-only into the switch.
- **Mode II:** buys right after the switch.

## Data
**Status page** (Atlassian Statuspage), fetched on Actions with a plain "crypto-edge-research/1.0" client, 1.1 s
apart. There were no refusals.
- `/history.json` pages 1–21: 1,383 incidents, Sep 2021 – Nov 2026.
- `/incidents/<code>.json` for all 1,383.

**Parser** (parse_events.py): phase statements by sentence and product id; future-tense notices and International
perp sentences ignored.
- **T_lo:** the first limit-only statement; on the pair's first trading day in all 257 cases.
- **T_ft:** the first full-trading statement after T_lo (display_at = created_at for 99.6%).

**Universe:** 338 USD pairs had a limit-only opening; 257 remain.
- **Excluded:** 29 listed before 2022, 23 with no full-trading statement, 19 stable or wrapped, 10 migrations
  (h4nl's rules).
- **By year:** 2022: 57, 2023: 20, 2024: 36 (AI training only), 2025: 87, 2026: 57.
- 31 are delisted now. Listings that went straight from auction to full trading (APE, TIA, BONK, PEPE...) are
  outside the SPEC's universe.

**Phase durations:**
- Auction: median 15 min (p90 46 min).
- Limit-only: median 22 h, but p25 3.2 h and p90 41 days.
  - 2022 books often sat limit-only for weeks (median 28 days); 2025 books for about 5 h.
  - 81 events have T_ft − T_lo > 48 h.

**Prints:** common.TradeFetcher on 8 Actions shards, T_lo − 10 min to T_ft + 3 h: 6.1M prints, all 257 events OK
(31 delisted via the Exchange API). Reduced on the runner into separate DEV and HOLD files; sim.load refused HOLD
files until frozen.json was pushed. Scored: 200 DEV and 21 HOLD events.

## Simulation (rules fixed in sim.py before any trial)
- **Mode I:** from T_lo + 60 min, a bid one tick under the last print (≥ 1 s old), refreshed each minute, filled only
  by later prints strictly below it, size ≤ θ × that through-volume. Bidding stops at T_ft (or T_lo + 48 h); taker
  exit at the first print ≥ 2 s after T_ft + H (or T_lo + 48 h).
- **Mode II:** taker buy at the first print ≥ T_ft + Δ; taker sell at the first print ≥ T_ft + H + 2 s.
- **Target:** min($5K, 5% of the USD printed in the 60 min before the decision); cash reserved until the exit.
- **Costs:** 6 bp maker, 12.5 bp taker. Taker legs add max(1.5 × half-spread, 2 bp), with the half-spread taken
  from opposite-aggressor pairs in the 10 min before the leg (h5an's fallbacks). Gates use 2×.
- **Tick:** the observed price step of the prints. It is 10× or 100× today's tick for 46% of events, from coarser
  precision at listing.

## Trials (10 logged to the shared ledger; DEV; sleeve $30K at 2×; alpha t on the incumbent at $70K)
| Variant | Trades | Sleeve SR | Alpha t | DEV book SR | Mean net bp | Mean gross bp |
|---|---|---|---|---|---|---|
| I, H5 | 178 | −0.78 | −1.50 | 0.44 | −264 | −185 |
| I, H30 | 178 | −0.68 | −1.34 | 0.53 | −224 | −144 |
| I, H120 | 178 | −0.39 | −0.80 | 0.67 | −136 | −56 |
| II, Δ2 s, H5 | 195 | −4.30 | −7.66 | 1.69 | −103 | +19 |
| II, Δ2 s, H30 | 199 | −1.59 | −3.34 | 1.76 | −79 | +43 |
| **II, Δ2 s, H120** | **199** | **−0.06** | **−0.04** | **1.83** | **−22** | **+105** |
| II, Δ60 s, H5 | 192 | −4.71 | −8.44 | 1.64 | −115 | +6 |
| II, Δ60 s, H30 | 199 | −1.90 | −3.97 | 1.70 | −93 | +30 |
| II, Δ60 s, H120 | 199 | −0.15 | −0.21 | 1.78 | −35 | +91 |
| AI on II Δ2 s H120 | 58 | −0.55 | −1.00 | 1.93 | −59 | +59 |

- **Incumbent alone (DEV):** Sharpe 2.35. Every trial lowers the book, and every neighbouring setting has the same
  (negative) sign.
- **AI:** walk-forward LightGBM by quarter from 2022Q4 (at least 30 earlier events). Features: limit-only duration,
  limit-only USD volume, the move since the open, BTC 4 h move, and listings in the trailing week.
- **Mode II, H120:** the mean gross of +105 bp comes from a fat right tail. The median net is −140 bp, and OPG
  (+98% in 2 h) alone is 152% of DEV P&L.

## Frozen variant
m2_d2_H120:
- Mode II, Δ = 2 s, H = 120 min, no AI.
- Chosen by the fixed rule: the highest DEV alpha t with at least 40 trades.

## Results (book = 0.7 × incumbent + 0.3 × sleeve at 2×; HOLD read once; a = 0.7 chosen on DEV)
| Window | Alpha t | Book SR | Incumbent SR | Gain | Sleeve SR |
|---|---|---|---|---|---|
| DEV | −0.04 | 1.83 | 2.35 | −0.52 | −0.06 |
| HOLD (21 trades) | −1.24 | 3.02 | 3.64 | −0.62 | −1.49 |
| All scored days | −0.20 | 1.93 | 2.47 | −0.54 | −0.14 |

**Gates at 2×:**
- **G1** fail: t −0.20.
- **G2** fail: HOLD t −1.24, gain −0.62. The mean net was −130 bp across HOLD's 21 trades.
- **G3** fail: gain −0.54.
- **G4** fail, provisional: DSR 0.50 (N = 3,162, v_z at the 1.126 floor under the within-idea rule). The pooled rule
  gives 0.00002, the plain rule 0.0. The coordinator recomputes G4.
- **G5** pass: book +8.8% (2022), +14.4% (2023), +23.9% (2025), +17.9% (2026). It is below the incumbent alone every
  year.

**1×, for information:** full t +0.38, HOLD t −0.96, gain −0.40, DSR 0.63. Same outcome.
- **Path A:** does not apply, since the sleeve's Sharpe is far below the incumbent's.
- **θ = 0.25:** identical, because the frozen variant is taker-only.

**Sleeve years ($30K, 2×):** −0.1% (2022), +2.5% (2023), −9.6% (2025), +15.5% (2026, mostly OPG).
- Mean +2.1% a year.
- Sharpe −0.14.

## Capacity filled
- 220 scored trades, mean $3.1K (45% at the $5K cap), $689K in all.
- Peak open notional is $19.6K, so the $30K cap never binds and $50K changes nothing.

## Fill realism and checks (all scored events)
**Participation:**
- The median trade is **2.5× all aggressive-buyer USD printed in the first minute after T_ft**, and 2.9× that of the
  minute after our entry.
- 85% of trades exceed half of the first-minute buyer flow.
- The "rush" of market-order buyers is small: a median $374 of aggressive buying in the first minute after T_ft
  ($766 of all prints). A $3K taker buy is the rush.

**Leak diagnostic:** the mean move from T_ft − 10 min to T_ft is −18 bp (median −3) on DEV. After T_ft it is +22 bp at
5 min, +39 bp at 30 min and +47 bp at 120 min (medians 0, −1, −46).
- There is no price run-up before the posted time.
- Volume per minute does rise from about $400 to $600–800 in the 6 minutes before the post. Posts probably lag the
  real switch by minutes: the first print comes a median 52 s before the posted T_lo.
- So a live status-flag poller would be earlier than this test.

**Aggressive-buy share:** 0.64 in minute +1 against about 0.53 before. The demand shock is real but small.

**Half-spread:** median 7.8 bp before and 7.9 bp after the switch (means 12.2 and 14.9).

**Mode I's premise:** price from T_lo + 60 min to T_ft averages −927 bp (median −154) on DEV and −1,085 bp (median
−459) on HOLD. Buying in limit-only is buying a falling knife.

**Other checks:** 0 exit fallbacks; entry a median 12 s after T_ft (thin books); top-3 days 337% of the small net
P&L (top-3 events 317%); correlation with the incumbent −0.02, and −$1.3K on its 20 worst days; 12 of 220 trades on
an H4 coin-day, daily correlation with H4 −0.03.

## Weaknesses
- **Posted time:** T_ft is the status post, not the true switch; a status-flag poller would enter minutes earlier and
  may catch more of the burst. Participation shows the burst is too small for a $3–5K trade anyway.
- **Coverage:** only listings with a limit-only phase; HOLD has 21 events.
- **Mode I fills** use the observed tick and ignore possible post-only rejection in limit-only (h4nl's claim,
  unverified; Coinbase's docs say auction mode rejects post-only). Moot: Mode I loses at any fill.
- The frozen variant holds at most 2 h, so no overnight marked-to-market drawdown applies.

## Deviations and engineering choices
- **T_ft search window:** up to 400 days after T_lo (the SPEC sets none); 81 events wait over 48 h. Mode I then exits
  at T_lo + 48 h ("never comes" read as "not by T_lo + 48 h"); Mode II trades the late switch.
- **Fixed before any trial:** the observed tick; Mode I's target and cash fixed at the first bid; an exit fallback
  when no print comes within 60 min.
- **After the freeze:** one non-model code change (the freeze guard reads FETCH_HEAD; this worktree has no
  origin/hunt/h13ps ref). final.py ran once.
- **G4:** provisional. **Shared code:** no problems; TradeFetcher paging and the Exchange fallback worked on all 257
  events.

## Verdict
**Fails.** The switch to full trading is a real but tiny demand event:
- a median of a few hundred dollars of aggressive buying in its first minute;
- +20–50 bp mean drift with a negative median;
- under a 2× round-trip cost near 100 bp.

Holding limit-only inventory into it loses heavily. Not worth a sleeve.
