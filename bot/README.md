# Wick catcher bot (AI-filtered resting-bid dip buyer)

What it does, in one paragraph: for each coin it keeps a **post-only limit buy resting well below
fair value** on the coin's Coinbase US perpetual future. Fair value is where the coin "should" be
given what BTC did over the last hour (beta-adjusted); the bid sits 4 residual standard deviations
below it. These bids fill only during sharp, forced selling (liquidation cascades, stop runs), which
tends to overshoot and snap back within the hour. An AI model (LightGBM) decides each minute whether
the bid is worth keeping live, from 23 market features known at that moment. After a fill it posts a
take-profit sell at 60% of the dislocation (also post-only), and if that has not filled after 60
minutes it exits at market.

## Files

| File | Purpose |
|---|---|
| `edge/wick.py` | Order levels and AI features — the exact code the research used (parity-tested) |
| `bot/engine.py` | Minute loop, paper broker, live broker (Coinbase Advanced SDK), risk limits |
| `bot/market.py` | Public market data (no keys): spot candles, futures candles, order book |
| `bot/train.py` | Retrains the model on all history for the chosen universe |
| `bot/model.txt`, `bot/model_meta.json` | The trained model and its threshold |
| `bot/config.json` | Capital, size per trade, max positions, daily loss limit, paper fee model |
| `bot/replay_test.py` | Runs the live engine over historical data and checks it trades exactly like the research |
| `.github/workflows/paper.yml` | Forward paper test on live data, every 6 hours, no keys, results in `paper/` |

## Venue and account (New York)

* **Coinbase Financial Markets (Coinbase Advanced → Futures)**: CFTC-regulated perp-style futures,
  available in all 50 states including New York. Up to 10x leverage; this bot uses ~1.5x at most.
* Contracts (6 Nov 2026 prices): nano SOL 5 SOL ≈ $450, nano XRP 500 XRP ≈ $600, nano ETH 0.1 ETH ≈ $225,
  LINK 50 ≈ $545, DOGE 5,000 ≈ $360, LTC 5 ≈ $265, plus BCH, SUI, XLM, HBAR, NEAR, AAVE, HYPE, ENA, PEPE, ONDO.
* Fees: Coinbase advertises perp fees "from 0.02%". The exchange-fee filing shows $0.10 per contract per side
  for retail, before Coinbase's own charges, so small contracts (ETH, LTC) can cost more than 2 bp. The research
  assumed 2 bp per side for makers **and** takers plus one futures tick of spread on every market order, and
  re-ran everything at $0.20 per contract per side. Confirm the real number on the first pilot fill
  (the bot logs the fee Coinbase reports).

## Before any real money

1. **Compliance.** These are commodity futures. Most fund employers' personal-trading policies cover
   futures and crypto even when they are not securities — get written pre-clearance first.
2. **Paper test** (running now, `paper/events.jsonl`): at least 4–8 weeks, ideally including one
   high-volatility week. Pass bar: realized net bp per trade within the backtest's range, fills
   happening where the backtest says they would, no operational errors.
3. **Pilot**: live mode with `notional_frac` such that every order is 1 contract, for 2–4 weeks.
   Compare every live fill against the paper fill for the same minute.
4. Then scale to the target size (`notional_frac` 0.25 ⇒ about $2,500 per trade on $10k).

## Running it yourself (live)

On an always-on machine (a $6/month cloud VM in us-east is ideal; a Mac that never sleeps works):

```bash
git clone https://github.com/milesmcqueen98-code/crypto-edge && cd crypto-edge
python3 -m venv .venv && . .venv/bin/activate
pip install pandas numpy lightgbm requests pyarrow coinbase-advanced-py
python bot/run.py --minutes 60                      # paper, to check it runs on your machine
# live: create a CDP API key (trade permission, futures portfolio) at coinbase.com/developer-platform
export COINBASE_API_KEY="organizations/.../apiKeys/..."
export COINBASE_API_SECRET="-----BEGIN EC PRIVATE KEY-----..."
I_UNDERSTAND_LIVE_TRADING=yes python bot/run.py --mode live --minutes 100000000
```

Kill switch: create a file named `STOP` in the repo folder — the bot stops placing entry bids
(positions it holds still get their take-profit / time exit). Delete it to resume.

## Risk limits (bot/config.json)

* `notional_frac` 0.25 — each trade is 25% of equity in notional.
* `max_positions` 6 — never more than 6 open trades (≤ 1.5x gross); when more coins qualify, the bot
  bids only on the highest-scoring ones.
* `daily_loss_limit` 0.05 — after a 5% loss in a UTC day, no new entries until the next day.
* Every position has a hard 60-minute time exit; there is no stop-loss, by design (stops at 1x the
  dislocation turned the backtest negative).

## Known gaps

* Live mode cannot be tested from the research environment (no exchange access). The first live
  session must be supervised at 1 contract. Order sizes are sent as contract counts (`base_size`),
  which is how Coinbase futures orders are specified — verify on the first order.
* Fills in the research are simulated: an order counts as filled only if the market traded
  *through* its price by at least one tick in that minute. Queue position and latency inside the
  minute are not modelled beyond that.
* The model is fixed at its training date; retrain quarterly (`python bot/train.py <coins>` after
  refreshing `data/minute`).
