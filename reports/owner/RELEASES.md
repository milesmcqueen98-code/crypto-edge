# Releases

A release is any change on `main` that can alter what the bot does with orders, or how it is started and stopped.
The paper books pick a release up at their next run. The live bot picks it up when Miles updates the VM. Each entry
says what changed, why, how it was tested, and what Miles needs to do.

## Release 3 (Nov 14 2026): verified inputs for the main book, W2 and the live bot

### What changed
1. **The main paper book and W2 use the third book's inputs** (`bot/spot/config.json`, `bot/spot/config.w2.json`:
   `"newest_bar": "trades"`, `"trades_coins"`, `"stale_guard": true`).
   - For BTC, ETH, SOL, XRP and ZEC the minute that just closed is built from Coinbase's public trades list, and
     used only when the list is proven complete.
   - The other thirteen coins keep the candle path with release 2's cache rules. LTC was on the third book's list
     and is not on this one (see Why).
   - The guard is on: no new bid in a minute when BTC's newest row is missing or old, and none on a coin whose
     candle answer is old. Exits and take-profits run as always.
2. **The live bot follows the release's inputs** (`bot/spot/run.py`, new `bot/spot/release_inputs.py`).
   - **The fault this closes:** the VM runs from `bot/spot/config.live.json`, a copy of `config.json` made when the
     VM was set up. A change of `config.json` never reached it, so `wickctl update` alone would have left the pilot
     on the late BTC input.
   - At every start, a file named `config.live.json` now takes six input settings from `config.json`. Capital,
     coins, fees and risk limits stay as the live file has them. The file is not rewritten.
   - `wickctl status` prints the inputs in use.
   - `"inputs_local": true` in the live file keeps that file's own input settings. It is the emergency switch back.
   - If `config.json` cannot be read, every command runs on the live file's own settings and says so. The kill
     switches never depend on it.
   - A live start without these inputs prints a warning and writes a `warning` event, which reaches the phone.
   - `preflight` writes back only `coins_disabled` and `bid_ttl_s`. It no longer saves a `--capital` override into
     the file; `wickctl` never passed one.
3. **One new phone alert** (`bot/spot/deploy/watchdog.py`): when the guard skipped new bids in three or more
   minutes within one five-minute check, at most once every 30 minutes. Before, a failing trades feed would have
   idled the bot with no alert.
4. **Replays of history state their own inputs** (`replay_test.py`, `live_sim_test.py`, `newest_bar_test.py`): final
   candles, because history has no trades list. The config change cannot alter them.
5. **Nothing in the engine changed.** `bot/spot/engine.py` and `bot/market.py` are as in release 2.

### Why
- **The third paper book passed its registered three-day read** (FORWARD_TESTS.md; the record is
  reports/owner/reconcile_tb/read/README.md). It ran these inputs from Nov 11 to Nov 14 next to the main book.
  - All 24,252 trades bars were verified. No refusal, no error. Data was ready at a median of 10.1 s.
  - BTC's trades bar was materially off in 6 of 2,938 compared minutes (0.20%). BTC's candle as the bot first sees
    it was materially off in most minutes.
  - New bids more than 5 bp from the research level: 9 of 550, against 360 of 715 in the main book.
  - New bids the research would not have placed: 23 of 550 (4.2%), against 153 of 715 (21.4%).
- **What the old inputs did in the same three days:** the main book had six first-bid fills the research did not
  have, bought 9 to 73 bp above the research's level. The third book had none, and its three fills are at the
  research's price to the tick.
- **Why LTC is off the list:** the rule keeps a coin only if its trades bar beats the coin's own first-seen candle
  on both measures on every day. LTC did not on Nov 13.

### Effect on trading
- **Main book and W2:** from their next run, at about 17:20 UTC on Nov 14.
- **Live bot:** when Miles updates the VM.
- **Bid levels follow BTC's true newest close.** That is the measured gain. About half the main book's new bids
  were more than 5 bp from the research level; with these inputs it was about one in sixty.
- **What stays imperfect, and is under test:**
  - **The thirteen coins on the candle path.** In the third book 19 of 349 new bids on its twelve (5.4%) were bids
    the research would not have placed, and 752 coin-minutes in three days were skipped for an old answer. A
    skipped minute means no new bid on that coin.
  - **A trades-built row is kept for good.** It gave ZEC level errors of 9 to 23 bp on three bids. ZEC passed the
    rule by a small margin on the last day and is the weakest coin on the list.
  - Part 2 of the bar-source plan tests the way meant to remove both: trades for the newest minute of all 18
    coins, the venue's candle afterwards. Its read is on Nov 15. If it passes, one more input release follows
    after its own tests.
- **Test A is counted again from this release** (registered Nov 13, before the read): the main book's three weeks
  and 60 rungs start with its first run on these inputs. The earlier record is kept and shown apart.
- **The third and fourth paper books run on unchanged.**

### Tests
- **Identical before and after the change,** run in the work container and again on GitHub runners:
  - parity replay of Oct 10 to 12 2025: 156 rungs and 88 parents on both sides, every rung identical;
  - live-path simulation: 540 minutes, 111 entries, P&L $11,723.34, bot equity equal to the exchange's to
    $0.0002; with the server death 109 entries and $8,421.28;
  - merge 21, trades bar 37, USDC 11, newest bar 73, hand-over 11, commit step 38, update command 7 checks.
- **New:**
  - the inputs rule, 66 checks: which settings move, which never do, the emergency switch, an unreadable
    `config.json`, the warning, and `status` end to end on a live file as a VM set up before this release has it;
  - the live-path simulation on these inputs, with a trades feed made from the same candles: every event equal to
    the candle run's, heartbeat counters aside; no fallback;
  - a switch of modes on a running book: no exception, all 15 open ladders kept, every entry and exit equal;
  - the watchdog, 31 checks.
- **On GitHub runners, for this exact list:** The full offline suite on commit 0fb7f12c (run 43602816403): no file with a failure, the same replay and live-path numbers, 2,410 bars built from trades on the new inputs, 15 ladders kept across the switch. A paper run of the new main-book config on live data (run 43602818937, to 14:30 UTC): no error, 40 bars built from trades in eight minutes (five coins a minute), no fallback, data ready at a median of 11.1 s and 14.0 s at the latest. The same two runs passed on Nov 13 with
  six coins and with four.
- **Not tested:** real orders; the VM's own network path to the trades list, which `wickctl paper-test` on the VM
  exercises for the first time; `preflight`'s write-back end to end (its rule is unit-tested).

### What Miles does
- **Nothing is required.** The paper books switch by themselves.
- **To take the release on the VM** (it starts nothing by itself):
  1. `wickctl update`
  2. `wickctl status`. It must show the line `inputs: newest minute from trades for BTC, ETH, SOL, XRP, ZEC;
     candles for the other coins; stale guard on (from bot/spot/config.json)`.
  3. `wickctl paper-test 35`. In the heartbeat line look for `"tb_built"` and for no entry that begins `tb_fb_`.
     This is the first test of the VM's own path to the trades list.
- **The pilot can start on this release** (bot/spot/README.md, "Configure, check, start" and "Go live in
  stages"). Or wait a day or two: if the Nov 15 read passes, one more input release follows, and installing once
  is less work. Either order is safe, because the live bot now takes its inputs from whichever release is
  installed.
- **One decision, when convenient:** the pilot's live log stays on the VM, and the owner of the algorithm needs it
  to read test B. Either a private repository the VM pushes its log to (about ten minutes to set up, then
  automatic), or a file exported and attached about once a week.
- **A known nuisance:** restarting the bot within a minute of a fill can send "coin balance differs" alerts. They
  clear when the bot books the fill moments later. A fix is queued.
- **The emergency switch back to the old inputs:** add `"inputs_local": true, "newest_bar": "candles",
  "stale_guard": false` to `bot/spot/config.live.json`, then `wickctl restart`. The phone gets a warning at that
  start, by design.

## Release 2 (Nov 10 2026): verified inputs behind a switch, a third paper book, paper runs without gaps

### What changed
1. **A new input mode, off by default** (bot/spot/engine.py, bot/market.py; switch `"newest_bar": "trades"`).
   - For the listed coins (BTC, ETH, SOL, XRP, LTC, ZEC) the minute that just closed is built from Coinbase's public
     trades list, and used only when the list is proven complete. A recent minute that could not be built is
     repaired at the next step.
   - For every coin the bot remembers when the answer behind each recent row was made. An older answer never
     replaces a newer row, and a candle row never replaces a trades-built row. Candles are looked at again for six
     minutes instead of three.
2. **A guard, off by default** (`"stale_guard": true`). The bot places no new bid in a minute when BTC's newest row
   is missing or old, and no new bid on a coin whose newest candle answer is old. Exits and take-profits run as
   always.
3. **Counters in every book's heartbeat, whatever the mode:** how often a candle answer was old, how often BTC was
   stale, and when the data, the cancels and the new bids finished each minute. The code that counts cannot stop a
   step.
4. **A third paper book** (`bot/spot/config.tb.json`, folder `paper_spot_tb/`) runs the new mode with the guard on, in
   its own job on its own runner. The two registered books are untouched.
5. **Paper runs hand over.** Each run of the paper workflow starts the next one when it ends, so the books no longer
   wait for GitHub's schedule. The schedule stays as a backstop.

### Why
- **The bot's BTC input was an old copy.** Coinbase serves candles through a public cache that keeps an answer for up
  to five minutes. In a two-hour probe the bot's own BTC request came back as an old copy in every minute, one to two
  minutes behind (reports/owner/candle_probe/README.md).
- **It shows in the paper book.** Against final candles, the level error at the paper book's 787 new bids is
  explained by a one-minute-late BTC (correlation 0.94). In the Nov 8 drop the book bought seven coins 36 to 59 bp
  above the research price (reports/owner/reconcile/README.md).
- **The trades list is a source that works** for six coins: cached for five seconds at most, and a bar built from it
  matches the final candle (reports/owner/candle_clock/README.md). The other twelve coins stay on candles, because
  Coinbase cuts their candles late after quiet minutes.
- **The paper books were live only about 70% of the time,** because GitHub drops scheduled runs.

### Effect on trading
- **None with the defaults.** The main paper book, W2 and a live bot keep today's inputs and today's decisions. In
  the replays every log line except the heartbeat is identical to release 1.
- The third paper book trades on the new inputs. It is paper only.
- The new mode becomes the default only by the rule fixed in FORWARD_TESTS.md ("Verified inputs"): three clean days
  of the third book, six conditions, no P&L test. That will be release 3.

### Tests
With the switches at their defaults (the same commands as for release 1):
- Parity replay, Oct 10-12 2025: identical (156 rungs, 88 parents on both sides).
- Live-path simulation, Oct 10 2025 20:00 to Oct 11 02:00: 540 minutes, 111 entries, P&L $11,723.34, bot equity equal
  to the exchange's to within $0.0002.
- Event logs of the parity replay, a paper replay and the live-path simulation against release 1: every line except
  the heartbeat is identical (order ids masked in the live simulation; they are random).
- Candle merge test 21 of 21, USDC quote test, `wickctl update` test 7 of 7: passed.

The new code:
- Trades bar and candle-answer age (bot/spot/trades_bar_test.py): 37 checks against a made-up trades endpoint.
  Complete and incomplete paging, an answer made before the minute closed, a refusal, a rate limit, several minutes
  in one pass.
- The engine's switches (bot/spot/newest_bar_test.py): old copies that must not replace newer rows, repair of a
  missed minute, the guard for BTC and for a single coin, a quiet minute with no trades, monitoring code that is made
  to fail, and a check that the live market object has every method the engine calls. Part of it replays the Oct 10
  2025 crash.
- Hand-over script (bot/spot/deploy/paper_next_test.sh): 8 checks with a stand-in for `gh`.
- On GitHub runners, real market data, no orders: the third book's configuration ran for 10 minutes (48 bars built
  from trades for the six coins, no fallbacks, data ready at a median of 9.8 s after the minute and 12.0 s at the
  latest); a repair probe rebuilt 24 of 24 minutes it had marked open; a 30-minute check found the trades bar equal
  to the final candle in every minute for BTC, ETH, SOL, XRP, LTC and ZEC.

Not tested: the two new jobs of the paper workflow (the third book's job and the hand-over) run only from `main`.
Their first real run is the first paper run after this release.

### What Miles does
- **Nothing is needed.** The VM can take this release at any time with `wickctl update`; it changes nothing there
  until release 3.
- **Hold the pilot until release 3.** A pilot started now would trade on the late BTC input.

## Release 1 (Nov 10 2026): candle merge fix and a safe `wickctl update`

### What changed
1. **bot/spot/engine.py, one line in `update_spot`:** the candle table is sorted after each minute's re-fetch is
   merged in.
2. **bot/spot/deploy/wickctl, the `update` command:** it restarts the bot only if the bot was running. A bot that was
   stopped stays stopped.

### Why
1. **The Nov 7 paper error.** At 21:19 UTC both spot paper books logged one error. A re-fetch left out a minute that an
   earlier fetch had returned, the table went out of order, and the next step failed. For that one minute the bot
   placed no new bids (exits and take-profits still ran). It recovered on the next minute.
2. **`wickctl update` always ended by starting the bot.** The service runs live mode. On a VM where the bot is set up
   but deliberately not running (before the pilot, or after `wickctl stop`), an update would have started live
   trading. Found while writing this note; nothing happened.

### Effect on trading
- **None in a normal minute.** The merged candle table is identical to the old one whenever the old code worked.
- In the rare minute that used to fail, the bot now carries on and places its bids.

### Tests (the same commands before and after the change)
- New candle merge test: 21 of 21 checks. The old lines fail on the case; the engine does not.
- Parity replay, Oct 10-12 2025: identical (156 rungs, 88 parents on both sides).
- Live-path simulation, Oct 10 2025 20:00 to Oct 11 02:00: identical line for line (540 minutes, 111 entries, P&L
  $11,723.34, bot equity equal to the exchange's to within $0.0002).
- USDC quote test: passed.
- Coinbase sandbox test (GitHub runner): 18 of 18 on the old code and on the new.
- New `wickctl update` test: 7 of 7. It runs the real command against stand-ins for sudo, systemctl, git and install,
  for a service that was active, activating (starting or restarting), inactive or failed, and for a failed pull.
- Not tested: a real systemd machine. The stand-ins cover the order of calls and the messages.

### What Miles does
The copy of `wickctl` on the VM is still the old one, so the first update needs care.

- **If the bot is running** (the pilot has started): run `wickctl update`. It stops the bot, pulls, and restarts it,
  as before.
- **If the bot is not running:** do not run `wickctl update` this one time, because the old copy would start the bot
  at the end. Run these two commands instead. They pull the code and install the new `wickctl` without touching the
  service:

  ```
  sudo -u wick git -C /home/wick/crypto-edge pull --ff-only
  sudo install -m 755 /home/wick/crypto-edge/bot/spot/deploy/wickctl /usr/local/bin/wickctl
  ```

- From then on `wickctl update` is safe in both cases. It prints which of the two it did.
