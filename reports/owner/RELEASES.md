# Releases

A release is any change on `main` that can alter what the bot does with orders, or how it is started and stopped.
The paper books pick a release up at their next run. The live bot picks it up when Miles updates the VM. Each entry
says what changed, why, how it was tested, and what Miles needs to do.

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
