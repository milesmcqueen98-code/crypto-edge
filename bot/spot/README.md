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
fake exchange), `deploy/` (server setup, systemd unit, watchdog), `.github/workflows/paper-spot.yml` (paper run on
GitHub Actions, logs to `paper_spot/`).

## What to expect

Research simulator, 17 coins, θ = 0.5 (we get half the volume that trades through our price), VIP-1 fees (6 bp maker,
12.5 bp taker). The bot misses deeper fills inside the parent's own minute, so these are the "bot-like" numbers:

| Capital | Selection, Jan 2025 – Mar 2026 | Check, Apr – Nov 2026 | Dollars a year |
|---|---|---|---|
| $250K | 27.6%, Sharpe 2.37, marked drawdown −17.7% | 19.6%, Sharpe 3.10, −5.5% | $49–69K |
| $500K | 23.4%, Sharpe 2.46, −16.6% | 14.5%, Sharpe 2.67, −5.4% | $72–117K |
| $1M | 19.2%, Sharpe 2.45, −13.2% | 8.5%, Sharpe 1.73, −4.1% | $85–192K |

- At θ = 0.25, the $250K book makes 24.2% (selection) and 18.0% (check).
- The −17.7% drawdown is intraday, marked to market, on the Oct 10, 2025 crash. Realized P&L that day was −2.8%.
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
- At $250K, θ 0.5, live with 1-second detection: 29.8% / Sharpe 2.27 (selection), 21.5% / 3.06 (check), 14.0% / 2.28
  (2022–23). That's about 2 points a year more than the table above.
- The paper run steps once a minute, so it understates live by about that much.

Known differences from the research simulation:
- The deeper bids go out once the 4σ fill is seen, so deeper fills inside the parent's own minute are mostly missed.
  This costs 3–4 points a year at $250K and is already in the table.
- Fill capacity counts Coinbase spot only. That was 97% of the research's capacity.
- Cash held by resting bids counts against the cash cap. Coinbase holds the cash for every resting buy. The research
  ignored this, and the paper run measures how often it binds (`cash_short` events).

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
   - The bot counts only USD as cash. It keeps $500 aside for fees and rounding.
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

## Go live in stages (rules fixed before any results)

| Stage | Capital | Length | Pass to move on |
|---|---|---|---|
| A. Paper on GitHub Actions (running since Nov 6) | $250K paper | ≥ 3 weeks and ≥ 60 rungs | No unexplained errors. Every rung closes by its rule. 1–6 rung fills a day. Mean net per $ above 0. |
| B. Live pilot | $10K | ≥ 3 weeks and ≥ 50 rungs | Live fills on ≥ 70% of the paper bot's fills (same coin and minute). Mean live result before fees within 25 bp of paper. No balance warnings. |
| C. Live | $250K | 6–8 weeks | Capture share ≥ 0.25 (`wickctl report`). Mean net above 0 after 150 rungs. |
| D. Live (optional) | $500K | — | Same rules, and only once alt volumes are back near the research level. |

- Paper and the pilot run side by side. At $10K, the pilot is a test of the machinery, not of the profits.
- **Standing stop rule:** stop and review if, after 150 rungs, the mean net per $ bought is below 0.
- **Pilot fees are higher.** A $10K book trades about $140K a month.
  - The first ~2 weeks sit in Coinbase's Intro and Advanced 1 tiers, where fees eat the edge. That costs roughly $80
    in total.
  - After that it reaches Advanced 2 (0.125% maker / 0.25% taker). Expect about 0.25% net per dollar bought, against
    about 0.40% at VIP 1.
  - Compare the pilot with paper before fees. The preflight and each start's `fee_tier` log line show your real tier.
- At $250K the book reaches VIP 1 ($500K of 30-day volume) in about a week.

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
- Code updates: `wickctl update`.
- Taxes: every rung is a short-term trade, so there are thousands of lots a year. Coinbase reports sales on Form 1099-DA.
  Use its tax export or crypto tax software, and ask a CPA how the wash-sale rule treats crypto for you.

## Paper run
`.github/workflows/paper-spot.yml` runs two paper books every 6 hours on GitHub Actions: the incumbent (`paper_spot/`) and
the wick v4 W2 challenger (rungs ¼, ¼, ½; `paper_spot_w2/`, config `config.w2.json`). Both use:
- $250K paper capital, θ = 0.5 capture, VIP-1 fees;
- live public Coinbase data, no keys;
- it commits `paper_spot/` back to the repo.

Run it locally the same way: `python bot/spot/run.py paper --minutes 60`.

## Tests
- **Parity:** `python bot/spot/replay_test.py 2025-10-10 2025-10-12` runs the engine minute by minute on stored data and
  compares every rung with an independent loop implementation of the same rules (entry minute and price, exit minute,
  type and price).
- **Live code paths:** `python bot/spot/live_sim_test.py "2025-10-10 20:00" "2025-10-11 02:00"` runs the engine in live
  mode against a fake exchange.
  - The fake exchange has real balances and holds, post-only rejections and cash checks.
  - It injects faults: 5% of cancels go unconfirmed and 15% of market sells fill only half.
  - It checks that no orders are orphaned, that coin balances return to zero, and that the bot's equity equals the
    exchange's USD balance.
- Results (Nov 6):
  - Parity: rung for rung identical on Oct 10–12 2025 (156 of 156) and Jun 1–3 2026 (33 of 33).
  - Live paths: books equal the fake exchange's to $0.0002 after 540 crash minutes with injected faults, with no
    orphaned orders and no leftover coins.
- Neither test reaches the real Coinbase API. The preflight and the $10K pilot are where real API surprises would
  show up.
