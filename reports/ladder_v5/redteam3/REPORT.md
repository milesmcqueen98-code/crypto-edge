# Red team 3: C4_usdc (ladder v5)

Returned as text by the red team (the subagent harness does not let it write report files) and committed by the
coordinator. Branch ladder/redteam3. Re-derivation committed before the builder's code or report was opened (edf6ee8);
gates.run never called; nothing logged to trials.csv.

## Verdict: partly confirmed
The backtest arithmetic and the gate results reproduce exactly, but the pass is mechanical: it holds for any assumed
reward of about 1.1% a year or more paid on all USDC, so it says nothing about whether this account will be paid.
C4 also adds a USDC peg/issuer tail risk and a regulatory expiry risk that the backtest cannot see.

## 1. Re-derivation: confirmed
- Own code (scripts/ladder_v5/rt3_c4.py): trading side from hsim.book (incumbent equals the frozen cache in all 12
  configuration x era cells); positions, reward, mark, Newey-West t (matches statsmodels HAC to 1e-4), return and
  Sharpe written independently.
- Selection and check eras match the logged JSON to 1e-14. 2022-23 return is 2.0e-5 a year higher: the builder counts
  the missing 2021-12-31 close as 1.0 (a -0.4 bp mark on 2022-01-01); the red team counts that day's ratio as 1.0.
- Pooled t, red team vs logged: S* theta 0.5 3.065 (3.063); theta 0.25 3.065 (3.063); base 6.072 (6.070); $1M 3.068
  (3.066).
- S* theta 0.5, return / Sharpe, incumbent -> C4 (scenario A): selection 19.46% / 2.311 -> 21.18% / 2.565; check
  15.07% / 2.311 -> 16.65% / 2.633; 2022-23 10.37% / 1.720 -> 11.92% / 1.717.
- The reward adds 1.75 / 1.57 / 1.54 points a year; the mark -0.03 / +0.00 / +0.01.
- Depeg week, Mar 10-15 2023, at $250K: marks -$549, -$7,312, +$5,937, +$1,007, +$645, +$372; Mar 11-12 carry 89% of
  the variance of the daily differences.
- Scenario B (no reward on USDC on hold for resting bids), from hsim.run's per-minute trace inside its active windows
  and an independent vectorised 4-sigma allocation outside them (matches a scalar version on 3,000 random minutes):
  on hold 43% / 41% / 3% of capital at S*, 69% / 49% / 3% in base; pooled t S* 2.340 (builder 2.338), theta 0.25
  2.340, base 3.957, $1M 2.720; S* returns / Sharpe 20.41% / 2.450, 16.00% / 2.503, 11.87% / 1.706.

## 2. Inputs
- **T-bill table** (edge/book.py) vs Treasury's daily 13-week bill rate and FRED TB3MS: every month 2022 to Aug 2026
  within 10 bp; Sep, Oct, Nov 2026 are 32, 43, 42 bp too low (actual 3.94 / 4.05 / 4.02 against an extrapolated flat
  3.60-3.62); Jan-May 2026 7-9 bp high. Effect on C4: none that matters (pooled t 3.063 with Treasury rates).
- **USDC/USD** vs Kraken public trades and OHLC and Coinbase's own USDT-USDC book: Mar 11 2023 daily mark -2.93%
  (Bitstamp) vs -3.13% (Kraken); worst hourly close 0.86267 / 0.901 / 0.8675 (Bitstamp / Kraken / Coinbase implied);
  intraday low 0.80526 / 0.874 / about 0.84. Bitstamp's other days with |move| > 0.2% are Bitstamp-only noise (Kraken
  moved at most 1 bp). Nov 2024 - Nov 2026: closes agree within 6.3 bp. **With Kraken marks the S* pooled t is
  2.9985**, just under the scorecard's 3.0 line (Evidence 25 -> 18).
- **Coinbase's published USDC rate vs the proxy (T-bill - 0.5%)**: 2022 0.38% (0.15% until about Nov 2022, then 1.5%)
  vs proxy 1.60%; 2023 3.41% vs 4.57%; selection era 3.94% vs 3.50%; check era 3.55% vs 3.15%. Below the proxy in
  2022-23, about 0.4 points above it in 2025-26; Coinbase One required since Dec 15 2025. Post hoc with the published
  rate: pooled t 5.26; halved under S* 2.66; scenario B at the full rate 3.71.

## 3. Live facts as of Nov 7 2026 (sources in the red team's message, summarised)
- Reward requires Coinbase One (since Dec 15 2025; DL News and Decrypt, 2025-12-11). Rate 3.5% in Feb 2026, 3.75% from
  mid-September, 3.60% in late October; uncapped, no minimum balance. Tiers $49.99 / $299.99 / $2,999.99 a year, same
  rate; Coinbase One's trading-fee waiver does not apply to Advanced Trade.
- Holds: Coinbase's Advanced page (fetched Nov 7) says "Earn rewards when you fund your trading balance with USDC, even
  on partial or unfilled orders", but the same page is stale ("Up to 5.1%"). Unverified for 2026 terms.
- Aliases: Coinbase's public product API (2026-11-08 00:10Z) shows BTC-, ETH- and SOL-USDC aliased to the -USD books,
  online; Exchange books merged Jul 13 2022.
- Conversion: the Advanced Trade convert endpoint supports USDC/USD; the US user agreement says Coinbase has "no
  obligation to repurchase your USDC"; conversion was paused from late Friday Mar 10 2023 to Monday.
- GENIUS Act effective Jan 18 2027, no transition. OCC final rule (Oct 21 2026) applies the yield ban to issuers,
  dropped the proposed presumption against issuer-to-affiliate or third-party reward arrangements, keeps anti-evasion
  powers; a further rulemaking on yield is anticipated. Exchange rewards do not end automatically but can be
  restructured at any time.
- CLARITY Act: House passed Jul 17 2025; Senate Banking advanced it May 14 2026; cloture failed 49-50 Sep 15 2026;
  considered dead until the new Congress. Its Tillis-Alsobrooks compromise would ban passive yield, the reward C4 uses.
- Could not establish (Coinbase help and terms pages refused automated fetches): eligibility for a New York account;
  whether USDC in API-traded or non-default portfolios earns; whether holds earn under current terms; whether -USDC
  orders are accepted and settle in USDC on this account; the exact current rate; whether -USDC trading would stay open
  in a depeg.

## 4. Risk
- **Forced sale vs the daily mark** (USDC was 99.94% of capital on Mar 11 2023): daily close -2.93% (-$7.3K at $250K);
  worst hourly close -13.3% (Coinbase implied, -$33.1K), -13.7% (Bitstamp), -9.9% (Kraken); intraday low -12.6%
  (Kraken), -19.5% (Bitstamp, -$48.7K). Selling at the worst hourly close and buying back at the Mar 13 close turns the
  S* pooled t to -0.53 (2022-23: -5.1 points a year, Sharpe -1.56): **the pass requires holding USDC through a depeg.**
- **Separate books that weekend**: the incumbent traded little (fills Mar 11 07:42-07:45 UTC worth $3.9K; trading P&L
  Mar 10-13 +$311 at S*). In a real depeg Coinbase would likely suspend -USDC trading, leaving an all-USDC bot unable
  to trade.
- **Expected tail cost**: assumed 0.5% a year chance of a permanent impairment with 10% loss: 5 bp a year ($125 at
  $250K; range 0.6-50 bp). A single event costs $7.5K-$62.5K at $250K. A rule that sells USDC in every >= 10% depeg
  would cost 1.2-1.6% a year, about the whole S* reward.
- **Reward net of Coinbase One Basic ($50 a year)**: trial scenario A $3.9-4.4K at $250K ($15.7-17.5K at $1M); scenario
  B $2.3-2.4K ($12.7-13.7K); at the published 3.5%, A $8.7K ($35K), B $4.9-5.1K ($27.5-28.3K). At a $10K book about
  $300 a year (A) or $150 (B).
- **If rewards end Jan 18 2027**: from a Dec 1 go-live, C4 would be worth $46 at $10K, $1.15K at $250K, $4.6K at $1M;
  after that it is peg risk with no carry. The switch must use one quote flag for every product; cancel the -USDC bids,
  convert only at a 1:1 zero-fee quote, re-place on -USD; never sell USDC at a discount (hold and retry if conversion is
  paused); trigger on rewards below half the expected amount, a Coinbase rate notice, a regulatory action, a rejected
  -USDC order or alias/status change, or independent USDC/USD below 0.997 for 15 minutes or a conversion pause.

## 5. What live verification must establish before any use
- Eligibility of this account and its API portfolio, with Coinbase One active.
- Whether holds earn: compare a full weekly payout with scenario A (total balance) vs B (available balance); the
  pre-registered $10 place-and-cancel bid cannot tell A from B.
- -USDC orders accepted for all 17 coins, fills and take-profit sells settling in USDC.
- USD/USDC conversion at 1:1 with no fee; reward payouts set to USDC, not BTC.
- The switch tested on paper, with a written rule never to sell USDC into a depeg; a check of Coinbase's notices
  around Jan 18 2027.

Scorecard (red team's scoring): 76 (builder 77): Implementation and risk 6, not 7 (a new tail risk and new switching
infrastructure); 69 if Evidence drops to 18 on Kraken marks.

## Files and commits
Scripts: scripts/ladder_v5/rt3_c4.py, rt3_fetch.py, rt3_inputs.py, rt3_risk.py. Outputs: reports/ladder_v5/redteam3/
(c4_summary.json, c4_daily_<cfg>.csv, inputs_summary.json, tbill_check.csv, usdc_check_daily.csv,
usdc_mar2023_hourly.csv, risk_4cde.json, fetch/ from Actions run 42428288756). Commits c27cbe5, 06d4353, edf6ee8,
45f7def, 999e593.
