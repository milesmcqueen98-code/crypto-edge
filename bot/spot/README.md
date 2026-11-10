# Spot bot: the wick catcher with the $1M rules (Coinbase spot)

**What it does.** Each minute, for each of the 17 R2-08 coins, the AI decides whether to keep a post-only limit buy
resting 4 residual sigmas below fair value on Coinbase spot (`{coin}-USD`). Fair value is where the coin "should" be
given what BTC did over the last hour. These bids fill only in sharp, forced selling, which tends to snap back within
the hour. On a fill it posts a take-profit sell at 60% of the dislocation. It also places two deeper bids, at 6 and 8
sigma below the same fair value. Every filled rung is sold at market 60 minutes after its fill if the take-profit
hasn't traded. Size per signal is the smaller of 25% of equity and 0.2% of the coin's daily Coinbase volume, split in
thirds across the three rungs. This is the rule chosen in the $1M round (`reports/wick1m_prereg.md`;
`reports/crypto-edge-findings.md`, section "Wick catcher at $1M").

Files: `engine.py` (minute loop, paper broker, live broker), `run.py` (commands), `config.json` (settings),
`replay_test.py` (parity test against an independent implementation), `live_sim_test.py` (live code paths against a
fake exchange), `sandbox_test.py` (live broker against Coinbase's sandbox), `deploy/` (server setup, systemd unit, watchdog), `.github/workflows/paper-spot.yml` (paper run on
GitHub Actions, logs to `paper_spot/`).

## What to expect

Research simulator, 17 coins, θ = 0.5 (we get half the volume that trades through our price), VIP-1 fees (6 bp maker,
12.5 bp taker), Coinbase spot capacity only (wick v4: `reports/wick_v4/spot_only.csv`). Return a year / Sharpe:

| Capital, bot | Selection, Jan 2025 – Mar 2026 | Check, Apr – Nov 2026 | Fresh era, 2022–23 |
|---|---|---|---|
| $250K, paper (steps once a minute) | 27.7% / 2.38 | 18.4% / 2.87 | 12.2% / 2.02 |
| **$250K, live (1-second fill detection)** | **29.9% / 2.28** | **20.1% / 2.82** | **14.0% / 2.28** |
| $500K, paper | 23.5% / 2.46 | 13.6% / 2.45 | 8.6% / 1.59 |
| $1M, live | 20.9% / 2.41 | 9.2% / 1.55 | 6.6% / 1.21 |

- **$250K live is about $35–75K a year** before the haircut below.
- The simulator's fill sizes were checked against Coinbase's trade-by-trade data (wick v4, addendum C1). The volume it
  assumes trades below our bids matches the trades (ratio 1.01), and the fill dollars agree to within 4–5%.
- At θ = 0.25, $250K live: Sharpe 2.15 (selection), 2.54 (check), 2.02 (2022–23).
- **Bigger isn't better past ~$500K.** At $1M the 0.2% volume cap stops positions from growing, so most of the cash
  sits idle.
  - Return falls to 6–21% a year, and Sharpe after the 3.6–4% T-bill rate falls to 1.0–2.4.
  - Run $250–500K here and keep the rest in T-bills.
- Marked drawdown about −18%, intraday, on the Oct 10, 2025 crash. Realized P&L that day was −2.8%.
- About 3 rung fills a day at $250K.
- Net per dollar bought is about 40 bp. One rung's result has a standard deviation of about 180 bp, so judge results over
  dozens of rungs, not days.
- **Volumes are down now.** In the 30 days to Nov 5, 2026, Coinbase volume in most of these alts ran 40–60% below the
  research's Sep–Nov 2026 level. The 0.2% cap shrinks positions to match, so $250K today behaves like about $425K did
  in the check period: roughly 15% a year, not 20%. Stay at $250K until volumes recover. The bot logs each coin's
  volume daily (`adv` events).
- Plan on about half of these numbers. R2-08 was the best of 130 variants (deflated Sharpe 0.77, against a bar of 0.95).
  In the check period, the best 3 days made about half the P&L.
- Gains are short-term and taxed as ordinary income (federal + New York State + New York City).

**Live vs paper (wick v4, trade-by-trade data):**
- When the 4σ bid fills, the price usually reaches the deeper rung 9 seconds later.
- The live bot reads the account's fill list every second, so it catches about 87% of those same-minute deeper fills.
  A once-a-minute bot catches none.
- That is worth about 2 points a year (the paper and live rows above).
- The paper run steps once a minute, so it understates live by about that much.

Known differences from the research simulation:
- Paper misses deeper fills inside the parent's own minute. Live, with 1-second detection, misses about 13% of them.
  Both are already in the table.
- The table counts Coinbase spot only. The research also counted the volume of Coinbase's US perp-style futures
  (mid-2025 on), which this bot can't fill on. Removing it costs the check period about 1.2–1.4 points a year.
- Cash held by resting bids counts against the cash cap. Coinbase holds the cash for every resting buy. The research
  ignored this, and the paper run measures how often it binds (`cash_short` events). Ladder v5 measured it (below).

**Ladder v5 corrections (Nov 7–8; `reports/ladder_v5_prereg.md` on branch `ladder/v5`, red-team branches
`ladder/redteam`, `ladder/redteam2`):**
- **Exits cost less than the table assumes.** The research charges each 60-minute market exit a 2 bp half-spread plus
  square-root impact (y = 0.7). On 17.2M Coinbase trades around 2,053 such exits, the sale cost 2.9–5.4 bp per dollar
  sold, against the model's 8.1–8.6.
- **The cash rule costs the deeper rungs on crash days.** The table lets every rung use its full share of cash; the bot
  funds the 4σ bids first. Replayed as the engine runs it (matched rung by rung on three crash windows), $250K live
  with measured exit costs earns **25.5% / 20.0% / 13.5%** a year (Sharpe 2.66 / 2.67 / 2.21) against the table's
  29.9% / 20.1% / 14.0%. Oct 10 2025 and Feb 3 2025 carry 69% of the selection period's cost. At $1M it costs
  nothing.
- **At today's volumes with unverified costs doubled:** $250K earns 22.8% / 19.1% / 11.1% (Sharpe 2.94 / 2.66 / 1.91);
  $1M earns 15.0% / 8.5% / 5.1% (2.28 / 1.47 / 0.73).
- No change to the trading rules passed (passive exits, margin sizing, deeper-rung priority, stress sizing, perps and
  print-based filters were tested). Holding cash as USDC passed the backtest and waits for a live check (below).

## Set it up, in order (about 1.5 hours)

### 0. Compliance first (it can end the project)
Get written clearance from Sculptor compliance before any live order. Ask four things:
- Are spot digital assets covered by the personal trading policy?
- Is there a minimum holding period? A 30- or 60-day hold rules this out, because the bot holds for at most about 2
  hours.
- Can one blanket pre-clearance cover an automated strategy? Per-trade pre-clearance is impossible: the bot trades
  several times a day.
- What reporting do they want? Coinbase exports a full transaction CSV.

### 1. Coinbase: a separate portfolio holding only the bot's cash
1. In Coinbase Advanced, open the portfolio menu and create a portfolio named `wickbot`.
2. Move the pilot cash into it as **USD**: $10,000. Transfer it between portfolios, or deposit first by wire or ACH.
   - The bot counts only USD as cash (USDC only after the USDC check below). It keeps $500 aside for fees and rounding.
3. Leave the BTC/ETH trend holdings in the default portfolio.

### 2. Alerts (5 minutes)
1. **healthchecks.io** (free): Add Check, named `wickbot`, period **1 minute**, grace **5 minutes**. Copy its ping URL
   (`https://hc-ping.com/...`).
   - The bot pings it every minute. If the pings stop, it alerts you even though the server is dead.
2. **ntfy** phone app: subscribe to a long random topic, for example `wickbot-7f3k9q2m`.
   - In healthchecks.io → Integrations, add ntfy with that topic, and keep email on.
   - The server's own watchdog posts halts, errors and a daily line to the same topic.

### 3. Server: AWS Lightsail, about $12 a month
1. Go to lightsail.aws.amazon.com and choose Create instance:
   - region **Virginia (us-east-1)**;
   - Linux/Unix → OS only → **Ubuntu 24.04 LTS**;
   - the **$12 plan (2 GB)**, dual-stack;
   - name `wickbot`.
2. In the instance's Networking tab:
   - **Create static IP** and attach it to the instance. This IP goes in the API key's allowlist.
   - In the firewall, delete the HTTP (80) rule and keep SSH (22).
3. Click **Connect using SSH** (a terminal in the browser) and run:
   ```bash
   curl -fsSLO https://raw.githubusercontent.com/milesmcqueen98-code/crypto-edge/main/bot/spot/deploy/setup_vm.sh
   sudo bash setup_vm.sh
   ```
   - It takes about 5 minutes. It installs the bot, the `wickctl` command, the service and the watchdog, then prints the
     server's IP, which should be the static IP.
4. `wickctl paper-test 10` runs 10 minutes on live public data, with no keys and no orders.
   - Expect `backfill`, `adv` and `arm` lines, and no `error` lines.

### 4. API key (Coinbase Developer Platform)
1. Sign in at portal.cdp.coinbase.com with your Coinbase login. Go to API Keys → **Secret API Keys** → Create API key,
   and name it `wickbot`.
2. Under API restrictions:
   - Portfolio: **wickbot**.
   - Permissions: **View and Trade. Never Transfer.** A key with Transfer can move your coins out.
   - IP allowlist: the static IP.
3. Under Advanced settings, set the signature algorithm to **ECDSA**. This is required; the Coinbase SDK can't use
   Ed25519 keys.
4. Create the key. Keep the window open for the next step, and save the key name and private key in your password
   manager.

### 5. Configure, check, start
```bash
sudo wickctl configure    # key name, private key (paste with its BEGIN/END lines), capital, alerts, live = yes
wickctl preflight         # places nothing; must end with PASSED
wickctl start             # runs now and after every reboot; the first 3-5 minutes are a data backfill
wickctl log               # follow the events (Ctrl-C stops watching; the bot keeps running)
```
- `configure` asks for:
  - the key name and the private key (paste it with its BEGIN/END lines);
  - the capital (10000);
  - the heartbeat URL and the ntfy topic;
  - the live switch (yes).
  It shows a summary and saves only when you confirm.
- `preflight` checks:
  - the key can trade and **cannot** transfer;
  - the portfolio's USD;
  - your fee tier;
  - which of the 17 coins your New York account can trade, using preview orders that are never placed;
  - Coinbase's minimum lifetime for expiring bids.

  It writes the blocked coins and the bid lifetime into `bot/spot/config.live.json`. The bot still uses the blocked
  coins' prices for the AI's features.
- On every start the bot does three things:
  - reconciles: cancels its own orders it lost track of, and compares coin balances with its positions;
  - books fills that happened while it was down;
  - runs any exits that fell due.

### Safety built in
- **Entry bids expire on their own.** They are good-til-date orders lasting about 5 minutes, and the bot renews them
  while it runs. If the server dies, every bid is gone within minutes.
  - Take-profits (sell orders) stay.
  - At most, the open positions are left; sell those in the Coinbase app, or wait for the server to come back.
- If the server goes quiet for 5 minutes, the healthchecks.io heartbeat alerts your phone.
- Tested: a 20-minute server death in the middle of the Oct 10, 2025 crash left no bids behind. The restarted bot booked
  everything correctly (`live_sim_test.py --death`).
- **Error recovery** (fixed Nov 7 after an independent code review):
  - A market sell whose outcome can't be read is resolved before any new sell, so coins are never sold twice.
  - A take-profit lost to a server error, or cancelled by Coinbase, is placed again.
  - A cancel that Coinbase confirms late is no longer mistaken for an expiry, so a rung is never bought twice.
  - A deeper bid rejected on renewal goes back to the queue. No bid is renewed after its window closes or while the
    bot is halted.
  - API calls time out after 10 s. An order whose create call timed out is found by its client id.
  - If candles or cash can't be fetched, exits and take-profits still run; only new bids pause.
  - The STOP file also stops the deeper bids that 1-second detection would place.
- **No bid without a volume figure** (fixed Nov 8 after the ladder v5 red team): a coin with fewer than 10 days of
  volume data (a failed fetch at first start, say) used to bid an uncapped 25% of equity ÷ 3, $20.8K at $250K, which
  the research never priced. It now skips the coin until its volume is known (`no_adv` in the heartbeat counts).

## Go live in stages (rules fixed before any results)

| Stage | Capital | Length | Pass to move on |
|---|---|---|---|
| A. Paper on GitHub Actions (running since Nov 6) | $250K paper | ≥ 3 weeks and ≥ 60 rungs | No unexplained errors. Every rung closes by its rule. 1–6 rung fills a day. Mean net per $ above 0. |
| B. Live pilot | $10K | ≥ 3 weeks and ≥ 50 rungs | Live fills on ≥ 70% of the paper bot's fills (same coin and minute). Mean live result before fees within 25 bp of paper. No balance warnings. |
| C. Live | $100K (up to $250K) | 6–8 weeks | Capture share ≥ 0.25 (`wickctl report`). Mean net above 0 after 150 rungs. |
| D. Live (optional) | $500K | — | Same rules, and only once alt volumes are back near the research level. |

- Paper and the pilot run side by side. At $10K, the pilot is a test of the machinery, not of the profits.
- **Standing stop rule:** stop and review if, after 150 rungs, the mean net per $ bought is below 0.
- **Pilot fees are higher** (simulator at $10K, spot only, Coinbase's US tiers in `scripts/wick1m/sim.py`).
  - A $10K book trades about $120–160K a month (buys plus sells).
  - **First ~11 days:** under $50K of 30-day volume, at 0.35% maker / 0.75% taker (0.50% / 0.90% for the first day or
    two). The strategy loses money at these fees. Expect about −$100 to −$120 in total.
  - **After that:** the $50K–250K tier, 0.15% / 0.30%. The backtest nets 0.11–0.29% per dollar bought, against about
    0.40% at VIP 1. That's 8–20% a year on $10K ($830–2,000), with Sharpe about 0.7–1.4.
  - With the edge halved as planned, the pilot runs about breakeven after the ramp.
  - $100K reaches VIP 1 (0.06% / 0.125%) within about two weeks, so the pilot's fees say nothing about the full-size
    book.
  - Compare the pilot with paper before fees. The preflight and each start's `fee_tier` log line show your real tier.
- At $250K the book reaches VIP 1 ($500K of 30-day volume) in about a week.

## USDC cash (optional; ladder v5 C4, live check first)
Coinbase pays nothing on USD but pays a reward on USDC, and the bot's cash sits idle most of the time. Holding it as USDC
added about 1.6–1.75 points a year at $250K in the backtest with the reward halved (Sharpe +0.25 / +0.32 in the
selection and check periods). On the $10K pilot that is about $350 a year at the published 3.5%, $300 after Coinbase
One Basic. The `-USDC` products are aliases of the `-USD` books,
so fills are the same. It is off (`"quote": "USD"`) because the backtest assumes a reward this account may not get:
1. Rewards need Coinbase One (Basic $49.99 a year), and they were not offered in New York when Coinbase launched them
   (2019). Confirm in the app that this account and the bot's API portfolio earn them, and set payouts to USDC.
2. `python bot/spot/run.py usdc-check` (needs keys and the live switch; places and cancels one $10 bid far below the
   market): a post-only `SOL-USDC` bid must preview with only USDC in the portfolio, and its hold must show on USDC.
3. Set `"quote": "USDC"` in `config.live.json`, convert USD to USDC only at 1:1 with no fee, and run through at least
   one weekly payout. Compare the reward paid with the heartbeats' `usdc_avail` and `usdc_hold`: A = average(both) ×
   APY × days / 365 (held USDC earns), B = average(`usdc_avail`) × APY × days / 365 (it doesn't).
4. Stop and switch back if the reward is below half of B, any `-USDC` order is rejected, or Coinbase changes the
   program (the GENIUS Act takes effect Jan 18 2027). If USDC trades below 0.997 for 15 minutes or conversion pauses,
   `wickctl pause` and hold the USDC: never sell it at a discount. Selling at the worst hour of the March 2023 depeg
   would have wiped out the whole backtest gain.
5. Switching back: pause, `wickctl cancel-all`, convert USDC to USD at 1:1, set `"quote": "USD"`, resume.

## Kill switches
- `wickctl pause`: no new bids from the next minute. Open positions still exit by their rules. `wickctl resume` undoes
  it.
- **Daily loss limit 8%** (realized): no new bids until 00:00 UTC. The research's worst day was −2.8%.
- **Drawdown stop 25%**, marked to market from the peak: no new bids until `wickctl reset-halt`. The research's worst
  was −17.7%.
- `wickctl flatten`: stops the bot, cancels every bot order and sells every open position at market.
  - `wickctl cancel-all` does the same but keeps the positions.
  - `wickctl stop` only stops the process. Bids expire on their own; take-profits stay.
- The bot also protects itself:
  - after 5 straight failed minutes, it cancels its resting bids;
  - every 15 minutes, it cancels any of its own orders missing from its state, and warns if coin balances differ from
    its positions.
- Last resort: revoke the key in the CDP portal, then sell by hand in the Coinbase app (`wickbot` portfolio).

## Day to day
- Your phone gets:
  - a daily equity line;
  - any halt, error, warning or rejected order;
  - the heartbeat alert if the server goes silent.
- Weekly, run `wickctl report`, and look at the paper book's report next to it (`git pull` and `python bot/spot/run.py
  report` on your computer). Compare fills, net per rung and capture share.
- Code updates: `wickctl update` pulls the latest code and restarts the bot only if it was running. A bot that was stopped
  stays stopped, so an update never starts live trading by itself.
- Taxes: every rung is a short-term trade, so there are thousands of lots a year. Coinbase reports sales on Form 1099-DA.
  Use its tax export or crypto tax software, and ask a CPA how the wash-sale rule treats crypto for you.

## Newest minute from trades (optional; off by default)
**The gap.** Each minute, 6 s after it closes, the bot reads 1-minute candles and decides its bids. The research used
final candles. Live, the newest candle is often not final yet:
- In one hour of forward data, 31.6% of the newest candles changed later, and 6% were missing.
- Coinbase serves candles through a public cache keyed by the request address (kept up to 300 s). Anyone's earlier
  request for the same address can hand the bot an old copy, with no error.
- Every coin's bid level moves with BTC's newest close, so an old BTC candle moves every bid.

**The switches** (in the config file; the defaults keep today's behaviour):
- `"newest_bar"`: `"candles"` (default) as today, or `"trades"`.
  - With `"trades"`, the minute that just closed is rebuilt from Coinbase's public trades list (`bot/market.py`,
    `minute_trades_bar`), for the coins in `"trades_coins"` only.
  - The bar is used only if it is proven complete: paging reached a trade older than the minute, and the first page
    was made after the minute ended (Date header minus Age header, or the page holds a later trade).
  - Anything else keeps the candle row (the fallback). Older minutes still come from candles. The next minute's
    candle re-fetch replaces the trades-built row.
  - The pass stops after `"trades_budget_s"` seconds (default 8). A refusal or a rate limit (HTTP 429) stops it at
    once for that minute, with no retry. The coins not done keep their candle.
- `"trades_coins"`: the coins rebuilt from trades. Default: BTC and every coin. Coins not listed use candles exactly
  as before and are never asked for trades. An unknown name stops the bot at start-up.
  - **Why a list.** For some coins Coinbase cuts the candle a few seconds after the minute mark: the 17:32 candle
    holds trades stamped in the first seconds of 17:33. For those coins a bar built from trade stamps cannot equal the
    final candle the research used. In a 30-minute check, trades bars equalled the final candle every minute for BTC,
    ETH, SOL, XRP, LTC and ZEC, and in 30 to 90% of minutes for the others. A separate study measures the cut per
    coin; the list follows it. The trades book lists BTC, ETH, SOL and XRP for now.
- `"stale_guard"`: `false` (default). With `true`, if BTC's newest traded minute is not the one that just closed, the
  minute runs like a market-data failure, for new bids only:
  - exits and take-profits run;
  - no new or re-priced bids; resting bids are left to expire;
  - one `stale_input` event with BTC's age in minutes; not an error.
  - In paper, bids do not expire by themselves, so a resting paper bid stays until the next normal minute.
- Nothing else changes: same model, rules, orders and checks.
- Monitoring cannot stop a step. If the timing or the data checks fail, it is counted (`obs_error`) and the step goes
  on. With the guard on, a failed check counts as stale (no new bids that minute).

**Heartbeat counters** (always on; per heartbeat, then reset):

| Counter | What it counts |
|---|---|
| `tb_built` | bars built from trades and used |
| `tb_insert` | of those, minutes where the candle had no row yet |
| `tb_close_diff` | of those, the trades close differed from the candle close by more than one tick |
| `tb_empty` | verified minutes with no trades (no row, as the candles) |
| `tb_fb_unverified`, `tb_fb_error`, `tb_fb_budget` | fallbacks to the candle: not proven complete, an error, out of time |
| `tb_fb_limited` | fallbacks because Coinbase answered 429 (rate limit) |
| `btc_stale` | minutes where BTC's newest traded minute was not the one that just closed |
| `newest_absent` | coin-minutes with no row for the minute that just closed (all coins) |
| `candle_old` | coin-minutes whose newest candle answer was made before that minute ended, so it cannot be final for it (17 coins) |
| `btc_candle_old` | the same for BTC |
| `obs_error` | timing or data checks that failed (the step went on) |

`candle_old` and `btc_candle_old` only count; they read the answer's Date and Age headers and change no request and
no decision. `step_s` gives the median and the maximum seconds after the minute at which the data step, the cancel
pass and the place pass of the 4-sigma bids finished. `tb_err` is the last trades error, when there was one.

**Paper.** `.github/workflows/paper-spot.yml` runs the trades book (`config.tb.json`, `paper_spot_tb/`) in its own
job (`paper_tb`) on its own runner, so the two registered books keep their requests and rate unchanged.

## Paper run
`.github/workflows/paper-spot.yml` runs three paper books for about 5h45m per run on GitHub Actions: the incumbent
(`paper_spot/`) and the wick v4 W2 challenger (rungs ¼, ¼, ½; `paper_spot_w2/`, config `config.w2.json`) in job
`paper`, and the newest-minute-from-trades book (`paper_spot_tb/`, config `config.tb.json`, section above) in job
`paper_tb`. All use:
- $250K paper capital, θ = 0.5 capture, VIP-1 fees;
- live public Coinbase data, no keys;
- it commits `paper_spot/` back to the repo.

- **Hand-over.** GitHub drops many scheduled runs: since Nov 8 the books ran in real time only about half the time, and
  settled the rest later from final candles. So a last job, `next`, starts the next run on main as soon as this one
  ends (`bot/spot/deploy/paper_next.sh`). It does so only if the run came from the schedule or a manual dispatch,
  and only if it lasted at least 30 minutes, so a run that fails at start cannot loop. The 6-hourly schedule stays as
  the backstop; a second run waits in the workflow's queue. Test: `bash bot/spot/deploy/paper_next_test.sh`.

Run it locally the same way: `python bot/spot/run.py paper --minutes 60`.

## Tests
- **Parity:** `python bot/spot/replay_test.py 2025-10-10 2025-10-12` runs the engine minute by minute on stored data and
  compares every rung with an independent loop implementation of the same rules (entry minute and price, exit minute,
  type and price).
- **Live code paths:** `python bot/spot/live_sim_test.py "2025-10-10 20:00" "2025-10-11 02:00"` runs the engine in live
  mode against a fake exchange.
  - The fake exchange has real balances and holds, post-only rejections and cash checks.
  - It injects faults:
    - 5% of cancels go unconfirmed;
    - 15% of market sells fill only half;
    - 10% of market sells execute with an outcome that can't be read for two minutes;
    - 5% of take-profit placements fail with a server error.
  - It checks that no orders are orphaned, that coin balances return to zero, and that the bot's equity equals the
    exchange's USD balance.
- **USDC quote:** `python bot/spot/usdc_test.py` checks, against a recording fake of the SDK, that with
  `"quote": "USDC"` every order call (bids, take-profits, previews, market sells, the client-id lookup) goes to the
  `-USDC` alias and cash is the available USDC, and that nothing changes with `"quote": "USD"`.
- Results (Nov 6):
  - Parity: rung for rung identical on Oct 10–12 2025 (156 of 156) and Jun 1–3 2026 (33 of 33).
  - Live paths: books equal the fake exchange's to $0.0002 after 540 crash minutes with injected faults, with no
    orphaned orders and no leftover coins.
- Results (Nov 8, after the ladder v5 changes: the volume fix and the USDC option):
  - Parity: 156 of 156 rungs identical on Oct 10–12 2025.
  - Live paths, with a 20-minute server death in the crash: books equal the fake exchange's to $0.0002 after 540
    minutes (187 unconfirmed cancels, 11 take-profit server errors, 4 unreadable market sells injected), no orphaned
    orders, no leftover coins.
  - USDC quote test: passed.
- **Candle merge:** `python bot/spot/merge_test.py` checks the per-minute merge of re-fetched candles in `update_spot`. A re-fetch
  that skips a stored minute used to leave the index out of order and the window cut raised KeyError. The test shows the
  old lines raise and the engine does not, that re-fetched values win, and that a normal merge is unchanged. No network.
- **Newest minute from trades:** `python bot/spot/trades_bar_test.py` (the trades bar and its proof of completeness,
  against a fake trades endpoint) and `python bot/spot/newest_bar_test.py` (the two switches in the engine, on
  synthetic tables and on the stored Oct 10 2025 crash). No network. `bot/spot/trades_bar_check.py` is the network
  check for a GitHub runner (hunt2.yml).
- **wickctl update:** `bash bot/spot/deploy/wickctl_test.sh` runs the real `update` branch against stub `sudo`, `systemctl`, `git` and
  `install`. It checks the order of calls for a bot that was active, activating, inactive or failed, and for a failed pull.
  Only a bot that was active or activating is started again. No network, no sudo.
- **Coinbase sandbox:** `python bot/spot/sandbox_test.py` (GitHub workflow `sandbox-test`) sends every live-broker
  call through the official SDK to Coinbase's Advanced Trade sandbox. The sandbox answers with static responses in the
  production format.
  - Calls covered: accounts, good-til-date and GTC post-only orders, get order, batch cancel, list orders, list fills,
    preview and market sell.
  - It also simulates insufficient funds and a failed cancel.
  - Nov 7: 18 of 18 checks pass. Nov 8, with the USDC option: 18 of 18.
- The sandbox's responses are static, so it can't show:
  - real order validation (post-only, the good-til-date minimum);
  - key permissions;
  - rate limits.
  The preflight and the $10K pilot are where those would show up.
