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

Known differences from the research simulation:
- The deeper bids go out once the 4σ fill is seen, so deeper fills inside the parent's own minute are mostly missed.
  This costs 3–4 points a year at $250K and is already in the table.
- Fill capacity counts Coinbase spot only. That was 97% of the research's capacity.
- Cash held by resting bids counts against the cash cap. Coinbase holds the cash for every resting buy. The research
  ignored this, and the paper run measures how often it binds (`cash_short` events).

## Set it up, in order

### 0. Compliance (first: it can end the project)
Get written clearance from Sculptor compliance before any live order. Ask four things:
- Are spot digital assets covered by the personal trading policy?
- Is there a minimum holding period? A 30- or 60-day hold rules this out, because the bot holds for at most about 2
  hours.
- Can one blanket pre-clearance cover an automated strategy? Per-trade pre-clearance is impossible: the bot trades
  several times a day.
- What reporting do they want? Coinbase exports a full transaction CSV.

### 1. Coinbase portfolio and cash
1. In Coinbase Advanced, create a new portfolio named `wickbot` (Portfolios → New portfolio). Keep the BTC/ETH trend
   holdings in the default portfolio. The bot's portfolio should hold only its own cash.
2. Move the pilot cash ($25,000) into `wickbot` as **USD**. The bot counts only USD as cash. USD and USDC share order
   books on Coinbase, but whether USDC can fund your -USD orders depends on the account, so start with USD.

### 2. Server (an always-on Linux VM)
1. Create an Ubuntu 24.04 VM in a US east region: DigitalOcean NYC, AWS us-east-1, or Vultr New Jersey.
   - Size: 2 vCPU / 4 GB (about $24 a month). The minute loop uses about 0.5 GB and under a second of CPU per minute.
   - Reserve a static IP. Log in with an SSH key only, and allow only SSH in the firewall.
2. Copy `deploy/setup_vm.sh` to the server and run it as root:
   `curl -O https://raw.githubusercontent.com/milesmcqueen98-code/crypto-edge/main/bot/spot/deploy/setup_vm.sh && sudo bash setup_vm.sh`
   - It installs Python, the bot, the systemd service and a 5-minute watchdog, and prints the server's IP.

### 3. API key (Coinbase Developer Platform)
1. Go to portal.cdp.coinbase.com → API Keys → **Secret API Keys** → Create API key. Name it `wickbot`.
2. Under API restrictions:
   - Portfolio: `wickbot`.
   - Permissions: **View and Trade only. Never Transfer.** A key with Transfer can move your coins out.
   - IP allowlist: the server's IP from step 2.
3. Under Advanced settings, set the signature algorithm to **ECDSA**. This is required: the Advanced Trade SDK does not
   accept Ed25519.
4. Copy the key name (`organizations/.../apiKeys/...`) and the private key into `/etc/wickbot.env` on the server.
   Follow the format in `deploy/wickbot.env.example`.
5. Optional: put an ntfy.sh topic in `NTFY_TOPIC` and subscribe to it in the ntfy phone app. That gives you alerts.

### 4. Preflight (checks everything, places nothing)
```bash
sudo -u wick bash -lc 'cd ~/crypto-edge && set -a && . /etc/wickbot.env && set +a && .venv/bin/python bot/spot/run.py preflight'
```
It checks:
- The key can trade and **cannot** transfer.
- The portfolio's USD.
- Your fee tier.
- Which of the 17 coins your New York account can trade. Coinbase lists coins for New York separately. Each coin is
  tested with a preview order that is never placed.

Put the coins it rejects in `coins_disabled` in `bot/spot/config.live.json`. The bot still uses their prices for the
AI's features. Set `capital` to the pilot amount (25000).

### 5. Start
```bash
sudo systemctl enable --now wickbot wickbot-watchdog.timer
sudo -u wick tail -f ~/crypto-edge/live_spot/events.jsonl           # backfill takes ~3-5 min, then "arm" events
sudo -u wick bash -lc 'cd ~/crypto-edge && .venv/bin/python bot/spot/run.py status'
```
On every start the bot:
- reconciles: cancels any of its own orders it lost track of, and compares coin balances with its open rungs;
- books fills that happened while it was down, then runs any exits that fell due.

## Go live in stages (rules fixed now, before any results)

| Stage | Capital | Length | Pass to move on |
|---|---|---|---|
| A. Paper on GitHub Actions (running) | $250K paper | ≥ 3 weeks and ≥ 60 rungs | No unexplained errors. Every rung closes by its rule. 1–6 rung fills a day. Mean net per $ above 0 (expected ≈ +40 bp; 0 is about 2 standard errors below). |
| B. Live pilot | $25K | ≥ 3 weeks and ≥ 50 rungs | Live fills on ≥ 70% of the paper bot's fills (same coin and minute). Fees as reported. Mean live net within 25 bp of paper on matched rungs. No balance warnings. |
| C. Live | $250K | 6–8 weeks | Capture share (filled $ / $ traded beyond our price, from `run.py report`) ≥ 0.25. Mean net above 0 after 150 rungs. |
| D. Live (optional) | $500K | — | Same rules, and only once alt volumes are back near the research level. Don't go above $500K: dollar profit stops growing near $1M. |

- **Standing stop rule at any stage:** stop and review if, after 150 rungs, the mean net per $ bought is below 0.
- **Pilot fees will be higher.** A $25K book trades about $0.3–0.4M a month, which is below VIP 1 (VIP 1 starts at $500K
  of 30-day volume). Expect about 10 bp less net per rung in the pilot.
- **The first week at $250K is a fee ramp.** Starting at $0 of 30-day volume, the bot passes the Intro and Advanced tiers
  in about a week. The cost is a few hundred dollars.
- Check your real tier: the preflight prints it, and so does the `fee_tier` event in the log on each start.

## Kill switches
- `python bot/spot/run.py stop`: no new bids from the next minute. Open rungs still exit by their rules.
  `resume` removes it.
- **Daily loss limit 8%** (realized): no new bids until 00:00 UTC. The research's worst day was −2.8%.
- **Drawdown stop 25%**, marked to market from the peak: no new bids until you run `run.py reset-halt`. The research's
  worst was −17.7%.
- Everything off: `sudo systemctl stop wickbot`, then `python bot/spot/run.py cancel-all`. That cancels every bot
  order; `--flatten` also sells every open rung at market. It refuses to run while the service is up, because the
  running bot would bid again.
- After 5 straight failed minutes, the bot cancels its resting bids. Every 15 minutes it also cancels any of its own
  orders missing from its state, and warns if coin balances differ from its open rungs.
- Last resort: revoke the key in the CDP portal. Then cancel or sell by hand in the Coinbase app, in the `wickbot`
  portfolio.

## Daily and weekly routine
- Phone alerts (watchdog):
  - the bot stopped completing minutes;
  - any halt, error, warning or rejected order;
  - a daily equity line.
- Weekly: `run.py report --state-dir live_spot` next to `run.py report` (paper). Compare fills, net per rung and capture
  share.
- Taxes: every rung is a short-term trade, so there are thousands of lots a year. Coinbase reports sales on Form 1099-DA.
  Use its tax export or crypto tax software, and ask a CPA how the wash-sale rule treats crypto for you.

## Paper run
`.github/workflows/paper-spot.yml` runs `python bot/spot/run.py paper` every 6 hours on GitHub Actions:
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
- Neither test reaches the real Coinbase API. The preflight and the $25K pilot are where real API surprises would
  show up.
