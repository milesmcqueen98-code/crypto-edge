# Gemini venue test (Nov 8, 2026): not a better venue, and not worth adding

Pre-registration: [reports/gemini_prereg.md](../gemini_prereg.md) (written before any Gemini data was read).
Code: scripts/gemini/ (fetch_tardis, enrich, levels, analyze, summarize). Data: data/gemini/.

**Verdict: fails the bar.** The frozen R2-08 ladder on Gemini prints, AI-filtered, at $250K, makes **−$1.8K a year
net** at Gemini's own fee tier (90% interval −$6.9K to +$3.1K; bar: +$5K with a positive lower bound). It is not more
profitable than Coinbase. On the same days it earns −5 bp gross per dollar against Coinbase's +67, on about 3% of the
dollars.

## Data and checks
- **Sample.** The first UTC day of every month, Jan 2024 – Nov 2026 (35 days), from Tardis.dev's free files.
  - Gemini's public API keeps only seven days of trades, so a sample of days is the only free history with prints on
    both venues.
  - AI-filtered results use the 23 R2-08 out-of-sample days (2025-01-01 onward). Pure gap counts use the 34 days with
    levels (2024-01-01 has none: the 3-day σ window starts with the data).
- **Prints.** Every Gemini print of the coins Gemini lists, enriched on Actions (scripts/gemini/enrich.py) with:
  - Coinbase's last price at that second, its lowest print within ±60 s, and its last price 1 s to 1 h later;
  - Gemini's best bid and ask at the same marks.
- **Coverage.** Gemini lists 13 of the 17 coins: ETH, SOL, XRP, DOGE, LTC, LINK, BCH, AAVE, PEPE and ZEC all period;
  HYPE from Dec 2025, SUI from Mar 2026, NEAR from Oct 2026. XLM, HBAR, ENA and ONDO are not listed.
- **Levels and AI reproduced exactly.** scripts/gemini/levels.py rebuilds R2-08's walk-forward model and matches the
  stored predictions and thresholds on all 1,568 R2-08 trades (max difference 0). The same models then score every
  minute of the sample days.
- **The sample is representative for the incumbent.** On these 23 days the incumbent's Coinbase ladder annualizes to
  $67K a year at $250K, against $71K over all 674 days (frozen simulator, research volumes, θ 0.5).
- **Spot check.** XRP, 2025-12-01 13:54:26.
  - The Gemini bid was 2.01897: the Coinbase level of 2.018855 × r 1.00006, floored to Gemini's 0.00001 tick.
  - It filled on a 2.01833 sell print. Coinbase had already printed 2.0177, below its own level.
  - Hand check of the parent: through-volume $11.9K of taker sells; take-profit hit after 2,387 s.

## Volume: Gemini is 2.6% of Coinbase in these coins
| | Gemini | Coinbase |
|---|---|---|
| USD a day, all overlapping coins (23 days) | $19.9M | $758M |
| Biggest books | ETH $10.1M, XRP $3.3M, SOL $3.2M | ETH $294M, XRP $174M, SOL $140M |

Per coin, Gemini is 0.01–3.8% of Coinbase (reports/gemini/volumes.csv).

## Pure ≥4σ gaps on Gemini (no AI, no level)
A gap is a Gemini print at least kσ below r × Coinbase's last price at that same second. Prints within 60 s form one
episode.

| | 4σ | 6σ | 8σ |
|---|---|---|---|
| Episodes (34 days) | 20 | 9 | 2 |
| Per day | 0.59 | 0.26 | 0.06 |
| Taker sells in all episodes, total | $18.9K | $8.3K | $1.3K |

- **Most are wide books, not holes.** 15 of the 20 are in ZEC, BCH and AAVE, where Gemini's own spread at the time
  was a median 240–540 bp, wider than the "gap".
- **Gemini's price did not rebound.** Its median move 60 s after the first print is 0 bp. The Coinbase-synchronous
  price sat a median 255 bp above it. Only a cross-venue trade (buy Gemini, sell inventory held on Coinbase) could
  capture that, on about $560 a day of sellers.
- **Tight books.** Only 4 episodes had a fresh Coinbase price (≤ 10 s old) and a Gemini spread under 20 bp. Three
  had no taker sells. The fourth, XRP on 2024-12-01, had $9K of sells and kept falling: Gemini led Coinbase down
  (−364 bp on Gemini after 60 s, −257 bp on Coinbase).

## The frozen R2-08 ladder on Gemini (23 out-of-sample days, $250K, θ 0.5)
| | AI-filtered: all | Shared with Coinbase | Gemini-only | Unfiltered: all | Incumbent on Coinbase, same days |
|---|---|---|---|---|---|
| Parent fills | 30 | 26 | 4 | 72 | 40 |
| Per day | 1.30 | 1.13 | 0.17 | 3.13 | 1.74 |
| Taker sells through the bids, $/day | $4,429 | $4,204 | $225 | $43,087 | — |
| Our fills, $/day | $1,291 | $1,285 | $6 | $4,839 | $38,182 |
| Take-profit hit | 35% | 29% | 71% | 33% | — |
| Gross, bp per dollar | −4.8 | −4.7 | −27 | +7.0 | +67.2 |
| Net at Gemini's tier, bp | −38.4 | −38.3 | −60 | −13.0 | +48.3 (Coinbase fees) |
| Net at Coinbase VIP 1 fees, bp | −21.2 | −21.1 | −43 | −9.3 | — |
| Net, $ a year | −$1,807 | −$1,795 | −$12 | −$2,295 | +$67,261 |
| 90% interval, $ a year | −$6,861 to +$3,148 | | | −$19,618 to +$13,712 | |

- **Fee tier.** The AI-filtered sleeve trades about $77K a month on Gemini: 12.5 bp maker, 25 bp taker. Gemini's
  schedule is not Coinbase's; a small book pays 25–60 bp maker below $75K a month.
- **The dollars alone fail the bar.** If Gemini's fills earned the incumbent's +48 bp net per dollar, $1,291 a day
  would make about $2.3K a year.
- **Capacity even uncapped.** Taking every dollar of sellers at θ 0.5, the AI-filtered fills are $2,700 a day, and
  gross P&L is −$2.2K a year.

**Rebound after the fill** (AI-filtered, median, bp vs our fill price)

| | +1 s | +10 s | +1 min | +5 min | +60 min |
|---|---|---|---|---|---|
| Shared: Coinbase-synchronous price | −8.8 | −6.6 | −5.4 | +0.6 | +3.2 |
| Shared: Gemini mid | −3.2 | −4.4 | −3.3 | +0.2 | −0.4 |
| Incumbent on Coinbase (ladder v5 diagnosis, mid) | | | +14 | +28 | +51 |

## Why Gemini loses where Coinbase wins
1. **Gemini follows Coinbase.** The ladder's dislocations happen on Coinbase. Gemini's book is re-priced afterwards,
   by arbitrageurs with Coinbase's price in hand.
   - A Gemini bid set from the same t−1 level fills after Coinbase has already traded below it: a median 8.8 bp under
     our price one second later.
   - The rebound that pays the incumbent (+51 bp in an hour) is gone by the time the Gemini bid fills (+3 bp).
   - This is the stale-anchor pick-off from H6 and H10, seen from the other side.
2. **The local holes are small and mostly not real.** Gemini-only fills were 0.17 a day.
   - BCH's are a persistent ~3.6% Gemini premium snapping back toward Coinbase.
   - The one clean hole (SUI, 2026-09-01) had $2.2K of sellers.
3. **Fees.** Gemini's own tier at this volume (12.5/25 bp) turns −5 bp gross into −38 bp net.

## Deviations and limits
- **Clarifications made after the data, none affecting a verdict:**
  - Coinbase-price age and Gemini spread are reported on the gap episodes (descriptive only).
  - The incumbent comparison uses the frozen simulator with deeper rungs allowed inside the parent's minute, matching
    the Gemini ladder's 1-second placement.
- **Crash days are not in the sample** (Oct 10 2025, Feb 3 2025), so cascade-day capacity on Gemini is unmeasured.
  - Dec 1 2025, the sample's busiest day, carries 58 of the 103 AI-kept Coinbase candidates. Gemini's fills that day
    were all shared and lost $159; the incumbent lost $1,232 on Coinbase the same day.
  - Without Dec 1, Gemini's AI-filtered fills are +7 bp gross per dollar on $11K of fills in 22 days.
  - A crash would raise Gemini's dollars, but by the volume ratio, not past it.
- **Ticks.** Gemini's ticks are today's.
- **Sizing proxy.** Sizing used each coin's same-day Gemini volume as the 30-day median. That only matters for the
  $-per-year figure, and the uncapped figure is negative too.
