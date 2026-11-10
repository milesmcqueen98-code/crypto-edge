# Releases

A release is any change on `main` that can alter what the bot does with orders, or how it is started and stopped.
The paper books pick a release up at their next run. The live bot picks it up when Miles updates the VM. Each entry
says what changed, why, how it was tested, and what Miles needs to do.

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
  for a bot that was active, restarting, stopped or failed, and for a failed pull.
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
