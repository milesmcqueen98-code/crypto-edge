# H9 (MC): the 4:00 pm ET intraday-to-overnight margin step-up on Coinbase US perps (wave 2b)

Fixed before any build. Added after research memo R3, under the same pre-registration (reports/hunt_prereg.md) and
gates. Read reports/hunt/BUILDER_GUIDE.md first.

## Mechanism (from R3, Coinbase docs and CFTC filings)
- **The rule:**
  - Coinbase Financial Markets offers opt-in intraday margin on weekdays from 8 am to 4 pm ET.
  - At 4 pm the overnight requirement applies. It is 2.1–2.6× higher for BTC/ETH (10% → 21–30%) and up to 3.7× for
    alt shorts (DOGE 25% → 52–92%).
  - CDE's daily settlement price is the VWAP of the 60 seconds to 4:00 pm ET.
- **Who is forced:** retail positions sized on intraday margin must shrink before 4 pm or be liquidated by CFM. Retail
  perp positioning is mostly long, so this is predictable forced selling (and, for shorts, forced buying) concentrated
  in a known window, on thin books, by a counterparty that cannot wait.
- **Why we're paid:**
  - A liquidity provider at that minute earns the reversion once the forced flow stops.
  - A trader who is flat into 4 pm and buys the dislocation after it also earns.
- **Why big funds pass:** the window is a few minutes a day on books of $1–10M a day.

## Universe and data
- **Instruments:** every Coinbase crypto perp in common.PERP that passes the $150 contract rule at trade time.
- **Data:**
  - Perp 1-minute candles: /home/claude/crypto-edge/data/cfm.
  - Spot 1-minute candles: data/minute.
  - Perp prints (common.TradeFetcher on Actions) for 15:30–16:45 ET every weekday from each perp's launch.
  - Spot prints only where a variant needs them.
- **Calendar:** weekdays only. US holidays are dropped (no intraday window); list them in the code. The ET clock follows
  daylight saving (use tz America/New_York).
- **Scored days:** gates.ERA_DAYS from each perp's launch (in practice Aug 2025 → Nov 5 2026). DEV ends 2026-05-31.

## Step 1: mechanism check (DEV only; decides whether trading variants are built)
Compare each weekday's 15:30–16:30 ET window with the same clock window shifted to 13:30–14:30 ET (control) on these
measures:
1. **Aggressive sell share:** the share of perp volume from aggressive sellers (prints with side == "BUY").
2. **Basis residual:** the perp's basis residual e (H1's definition: log(perp/spot) minus its trailing 24 h median,
   known at t−1), minute by minute.
3. **Return gap:** perp return minus spot return over 15:45–16:05 ET.

**Pass rule:** move on to Step 2 only if, on DEV, the 4 pm window shows more aggressive selling (paired t ≥ 2 across
days, pooled over coins) and a more negative basis residual at 15:55–16:05 than the control (paired t ≥ 2). The
Step-1 comparisons are logged as one trial each (two in total).

## Step 2: trading variants (≤ 22 more trials)
**V-bid:** resting post-only bids on the perp at F × exp(−k σ_e), live only 15:45–16:15 ET.
- F and σ_e as in H1: spot close at t−1 × exp(b̄), trailing-3-day σ of e.
- Fills checked on perp prints: strictly through the level, size ≤ θ × through-volume, θ = 0.5.
- Take-profit at 60% back to F; market exit at 16:45 ET.
- Grid: k ∈ {1.5, 2, 3} × universe ∈ {BTC+ETH, all} = 6 trials.

**V-after:** at 16:01 ET, if the basis residual z = e/σ_e ≤ −z0, buy the perp.
- Entry: taker at the first print at least 2 s after 16:01:00, with 1.5× half-spread.
- Exit: at 16:30 or 17:00 ET.
- Grid: z0 ∈ {1, 2} × exit ∈ {16:30, 17:00} × universe ∈ {BTC+ETH, all} = 8 trials.

**V-flow:** at 16:01 ET, if the perp's 15:30–16:00 return is below −x × its trailing 20-day standard deviation of that
window's return, buy the perp.
- Entry and exit as in V-after (exit 16:45).
- Grid: x ∈ {1, 2} × universe ∈ {BTC+ETH, all} = 4 trials.

**Mirror for shorts:** the best variant's short side (forced short-covering lifts) = 1 trial.

**Sizing:**
- Notional per coin per day = min($15K, θ × the through-volume for resting fills).
- Taker variants: min($15K, 2% of the coin's trailing 20-day median perp volume in that window).
- Gross ≤ 3× sleeve capital.

**Costs:** common.py; 2× for gates.

**Selection:** the highest DEV alpha t with at least 40 trades.

## Checks to report
- Step-1 tables: per coin, per weekday, the Friday WEEKEND window vs Mon–Thu.
- Net bp by variant and coin.
- Whether the effect shrinks over time (intraday-margin take-up and CFM policy can change).
- Top-3 days' share of P&L.
- Correlation with the incumbent and with H1's daily P&L (if available on branch hunt/h1pb), so Wave 3 can see the
  overlap.
