# H7 (UL): short the perp ahead of large token unlocks: FAILS (G1–G4)

Branch hunt/h7ul. Freeze commit 5d3eeff (pushed before HOLD was read). HOLD read once in 01966aa.

## Mechanism
Recipients (team, investors) and those who expect them to sell hedge or sell before a scheduled cliff, which produces
negative drift into the unlock. The short exists on Coinbase only as a US perp.

## Data actually used
- **Unlock schedules:** DefiLlama's free CDN, 373 protocols, fetched on Actions; 19 committed.
- **Mapping (committed in 42c0121 before any price was loaded):** 16 perp coins matched by gecko_id
  (mapping.csv).
  - XRP, ADA, BCH, XLM, PEPE, ZEC and SHIB have no dataset, so XRP escrow is not covered.
  - The LINK and HYPE unlock sections are realised transfers that DefiLlama records after the fact. Trading them
    ahead would be look-ahead, so the rule excludes them.
- **Event rule:** the daily scheduled increase (treasury excluded) is at least X of DefiLlama's circulating supply 30
  days earlier (DefiLlama for every coin). Runs within 7 days are merged.
- **Events:** at X = 1%, Jun 2021 – Nov 2026, 71 events:
  - SUI 36, AVAX 14, HBAR 14, ENA 3, ONDO 2, BNB 2.
  - By year: 2021: 5; 2022: 9; 2023: 14; 2024: 21; 2025: 15; 2026: 7.
  - The simulation starts Sep 2021, which leaves 67 events.
  - BNB has no data/cfm file and leaves the universe.
  - ENA has no Coinbase price before Jun 2025, and its 2024–25 events were dropped ("no price").
  - 57 trades were taken; **38 touch scored days**: SUI 25, AVAX 6, HBAR 5, ONDO 2.
  - 2024 trains models and is never scored, so 19 trades fall outside the scored window.
- **Prices:** perp from launch (SUI and HBAR from Dec 2025, ONDO from Mar 2026); Coinbase spot before that
  (1-minute, or hourly for AVAX 2021–23). **32 of 38 scored trades (83% of P&L) are HYPOTHETICAL SHORTABILITY:**
  spot-priced with the perp cost model plus a 10%/yr carry charge.

## Trade, sizing and caps (SPEC, fixed)
- Short at 16:00 UTC on U − d1 (taker); cover at 16:00 UTC on U + d2. Each event gets 50% of capital, in contracts
  worth at least $150.
- Gross is capped at 2× capital, and per R3 the summed overnight short margin is capped at 100% of capital.
  Realised peaks: gross 1.0×, margin 0.59×, at most 2 positions, so neither cap bound.
- P&L is marked to market at 00:00 UTC. Costs are those in common.py, doubled at 2×.

## DEV trials (17 logged to reports/hunt/trials.csv; sleeve at 2×, alpha t at the incumbent's $70K)
| Variant | Sleeve Sharpe | Alpha t | Events |
|---|---|---|---|
| **d1=7, d2=0, X=1%, no hedge** | **0.89** | **1.94** | 38 |
| d1=7, d2=0, X=1%, beta | 0.58 | 1.40 | 37 |
| d1=7, d2=0, X=2.5%, none / beta | 0.82 / 0.63 | 1.84 / 1.52 | 26 / 25 |
| d1=7, d2=3, X=1%, none / beta | 0.23 / 0.05 | 0.58 / 0.29 | 38 / 37 |
| d1=7, d2=3, X=2.5%, none / beta | 0.26 / 0.25 | 0.74 / 0.67 | 26 / 25 |
| d1=14, d2=0, X=1%, none / beta | 0.19 / −0.12 | 0.49 / −0.05 | 37 / 36 |
| d1=14, d2=0, X=2.5%, none / beta | −0.29 / −0.32 | −0.32 / −0.41 | 25 / 24 |
| d1=14, d2=3, X=1%, none / beta | −0.14 / −0.48 | −0.10 / −0.74 | 37 / 34 |
| d1=14, d2=3, X=2.5%, none / beta | −0.50 / −0.60 | −0.68 / −0.97 | 25 / 23 |
| d1=7, d2=0, X=1%, team/investor only | 0.68 | 1.50 | 16 |

- **Frozen:** the highest t with at least 20 events.
- **Sign agreement across neighbours:** all five one-step neighbours of the frozen variant are positive (sleeve
  Sharpe 0.19–0.82). But every d1 = 14 or d2 = 3 variant is much weaker, and 7 of the 8 d1 = 14 variants are negative.
- Any effect sits in the final week before the unlock.

## Results at 2× (sleeve on $30K; book a = 0.7, chosen on DEV; benchmark = incumbent with all $100K)
| Window | Alpha t | Book Sharpe | Incumbent Sharpe | Gain | Sleeve Sharpe |
|---|---|---|---|---|---|
| DEV | 1.94 | 2.20 | 2.35 | −0.14 | 0.89 |
| HOLD | n/a (degenerate) | 3.48 | 3.64 | −0.16 | n/a |
| All scored days | 1.90 | 2.28 | 2.47 | −0.19 | 0.82 |

- **HOLD:** no qualifying unlock fell in Jun 1 – Nov 5 2026, so the sleeve held cash.
  - Its excess series is −T-bill, which makes the printed HOLD t (−1062) and sleeve Sharpe artifacts.
  - The −0.16 gain is purely idle capital.
  - The pre-freeze schedule scan (no prices) foresaw this and is disclosed in frozen.json.
- **DSR:** about 0 (gates.json: 1.3e−11 at N = 3,050).
  - Recomputed at today's ledger (N = 3,066, v_z = 7.65): 1e−8.
  - v_z is inflated by the dispersion between ideas: the mean within-idea variance is 4.1.
  - At the 1.126 floor it would be 0.77 (for information). The incumbent alone would score 0.91.
- **Years:** book 2022 +20.3%, 2023 +14.6%, 2025 +31.6%, 2026 +17.6%. Sleeve at 2× +38.2%, +3.1%, +16.0%, +14.5%.
- **1× (information):** alpha t 2.18, gain −0.09. At $50K and 2×, sleeve Sharpe 0.82.

**Gates (2×):**
| Gate | Result | Value |
|---|---|---|
| G1 | FAIL | t = 1.90 |
| G2 | FAIL | No HOLD events; gain −0.16 |
| G3 | FAIL | Gain −0.19 |
| G4 | FAIL | DSR ≈ 0 |
| G5 | PASS | No losing year |

Path A does not apply.

## Other checks
- **Event study:** n = 56, mean CAR vs BTC beta (estimated over −120 to −31):
  - −30 to −1: −5.8% (t −2.0)
  - −7 to −1: −3.8% (t −3.9; −4.8% excluding 2024)
  - 0 to +10: +1.0% (t 0.5)

  The published pre-drift reproduces in direction and in the last week. The full −30 to +10 path is in checks.json
  and events_study.csv.
- **Hypothetical vs perp-priced:** both earned about +4.2% per trade on notional.
  - Hypothetical: n = 32, hit rate 72%.
  - Perp: n = 6, hit rate 67%. Six trades validate nothing.
- **Concentration:** the top 3 events are 49% of P&L; the top 3 days are 27%.
- **Diversification:** correlation −0.03. On the incumbent's worst 5% of days the sleeve averages +0.29%.
- **Marked max drawdown:** sleeve −15.9% at 2×; book −4.7% (incumbent alone −4.9%).
- **Fee sensitivity (R3), alpha t at 2×:** $0.12 1.94, $0.20 1.90, $0.30 1.85.
- **Funding:** the mean perp–spot premium over the 6 perp-priced holds was −0.3 to +8.0 bp (5 of 6 positive). Under
  CFM's formula (R3) a short would *receive* about −2 to +56 bp per 7-day hold (median about 29). The model charges
  21 bp at 1× and 42 bp at 2×, so the gate cost is conservative on perps. For the 32 spot-priced trades it is
  unknowable.
- **Capacity:** about $15K per order. Median participation is 2.3% of 16:00–17:00 UTC volume, but on thin perp days
  it exceeds 100% (SUI 21× on Dec 25 2025), so live entries need a TWAP. SUI's perp book holds about $94K within
  20 bp.

## Power (honest)
- Per-event Sharpe on notional: 0.40 (mean +4.2%, sd 10.5%), n = 38, so t ≈ 2.4 from events alone.
- t ≥ 3 needs n ≥ 9/0.40² ≈ 57 events at this effect size, or a per-event Sharpe ≥ 0.49 at n = 38.
- On the calendar: 3.85 scored years need a sleeve Sharpe ≥ 1.53 for t = 3. The sleeve has 0.82.
- **The sample cannot reach t ≥ 3, and it is shrinking.**
  - SUI's ≥1% monthly steps ended in May 2026; it supplied 25 of the 38 scored events.
  - The schedule shows only ONDO's Jan 18 2027 and 2028 cliffs ahead, with nothing else at ≥ 1% before 2029.
  - Unlocks in the perp universe arrive at about 0–2 a year from here.

## Weaknesses
- 84% of the evidence assumes a short that did not exist on Coinbase.
- Schedules are partly approximate (SUI read from a chart, AVAX seed dates guessed, ENA linearised) and are today's
  vintage, so revisions are a look-ahead risk.
- One coin carries the result (SUI, 25 of 38).
- HOLD is untested in substance.

## Deviations
1. Added the R3 overnight-margin cap (summed short margin ≤ capital). It never bound.
2. Universe limited to coins with data/cfm, per common.py.
3. Realised-transfer sections excluded (anti-look-ahead; fixed before prices).
4. Hourly spot bars used for AVAX 2021–23.
5. "Events" counts trades that touch scored days.

## Verdict
**Fails** G1–G4 at 2×. The pre-unlock drift is real-looking (−3.8%, t −3.9) and diversifying, but the sample is
small, mostly hypothetical and drying up. Better used as a filter on the incumbent (R2).
