# Release 3 candidate: facts for the release note

Branch `owner/release-3`. Prepared as a candidate; whether it ships, and with which coin list, is decided by the third
book's read. This file states facts only.

## What changed, file by file
- **`bot/spot/release_inputs.py` (new).** Pure functions, standard library only (Python 3.8 and later).
  - `INPUT_KEYS`: `newest_bar`, `trades_coins`, `stale_guard`, `trades_rows`, `trades_budget_s`, `confirm_s`.
  - `applies(path)`: true only when the file's base name is `config.live.json`.
  - `apply(cfg, base)`: the six keys from `base`; a key `base` lacks is dropped; a note for each replaced or dropped
    value; `"inputs_local": true` keeps the file as it is, with one note. Nothing else is touched; neither argument
    is changed.
  - `describe(cfg)`: the one-line inputs summary.
  - `preflight_file(raw, coins_disabled, bid_ttl_s)`: what `preflight` writes back.
- **`bot/spot/run.py`.**
  - Loads the file into `raw`; `cfg` is a copy. For `config.live.json` it applies `bot/spot/config.json`'s input
    settings, for every command.
  - If `bot/spot/config.json` cannot be read (missing, bad JSON, any error in `apply`), `cfg` stays as the live file
    has it, one line is printed (`inputs: bot/spot/config.json could not be read (...); this file's own input
    settings are used`) and the command goes on.
  - `live`, `paper`, `status` print the inputs line (with ` (from bot/spot/config.json)` when applied) and each note.
    `status` prints it first, before the check for a state file.
  - `live` only: when the inputs are not trades with the stale guard, it prints `WARNING: live trading is starting
    without the release 3 inputs (trades with the stale guard); inputs: ...` and writes the same text as one event of
    the existing kind `warning` through the engine's own log (engine built first, then `log`, then `run`). It still
    starts.
  - `preflight` writes back the file as read plus `coins_disabled` and `bid_ttl_s`.
  - The checks before live trading (keys, capital, `I_UNDERSTAND_LIVE_TRADING`) are unchanged and still come before
    the engine is built.
- **`bot/spot/config.json`, `bot/spot/config.w2.json`.** `"newest_bar": "trades"`, `"stale_guard": true`,
  `"trades_coins": ["BTC", "ETH", "SOL", "XRP", "LTC", "ZEC"]` at the end, in `config.tb.json`'s order.
  `config.json` is now byte for byte `config.tb.json`; W2 differs from it only in its rung weights. Own commit.
- **`bot/spot/README.md`.** New section "Inputs of the live bot (taken from the release)"; the heading of the trades
  section now says the code's default is off and `config.json` says what the books and the live bot use; two test
  lines.
- **Tests.** `replay_test.py`, `live_sim_test.py`, `newest_bar_test.py` state candle mode in their own code (step C).
  `live_sim_test.py` gets `--inputs` and `--switch`. New: `release_inputs_test.py`, `live_sim_inputs_test.py`,
  `scripts/owner/release3/run_spot_tests.py`.
- **Not changed.** `bot/spot/engine.py`, `bot/market.py`, every safety check in `bot/spot`, `wickctl`,
  `configure.py`, `setup_vm.sh`, `watchdog.py`, the service file, `.github/`.

## A VM configured before release 3, at `wickctl update`
- **Its live file has no input keys.** `setup_vm.sh` (line 20) made `config.live.json` as a copy of `config.json`
  with capital 0; `configure.py` changes only the capital; `preflight` only `coins_disabled` and `bid_ttl_s`. Before
  release 3 `config.json` had no input keys, so no VM file has them.
- **What `wickctl update` does.** It stops the service, pulls, installs the new `wickctl`, and starts the bot again
  only if it was running (release 1). At its next start the bot takes the three keys from `config.json`: newest
  minute from trades for the listed coins, candles for the others, stale guard on. The live file is not rewritten.
- **A bot that was running.** It restarts on the new inputs with its existing state. In the simulation the switch on
  an existing state raised nothing and kept every open ladder (below).
- **A bot that was stopped.** It stays stopped; it takes the new inputs when started.
- **What its owner sees in `wickctl status`.** First line, for example:
  `inputs: newest minute from trades for BTC, ETH, SOL, XRP, LTC, ZEC; candles for the other coins; stale guard on
  (from bot/spot/config.json)`. No note lines (the file had no input keys). Then the status lines as before.
- **`live_spot/stdout.log`** gets the same inputs line at each start.
- **Emergency switch.** `"inputs_local": true` in `config.live.json` keeps the file's own inputs; the file must then
  name the mode (`"newest_bar": "candles"`, `"stale_guard": false` for the old mode). With that, `live` prints the
  WARNING and writes a `warning` event.

## Tests run here (offline, from a copy of the branch with `data/` linked read-only)
Baseline is the untouched branch (`1ecebdd`). "Identical" means the stdout and every event log named in it are equal
line for line (order ids masked; they are random).

Commands from the repository root; results on the untouched branch, after step C, and after step B (the final
state, commit `11a0940`).

- **Parity replay** `python bot/spot/replay_test.py 2025-10-10 2025-10-12`: 156 rungs, 88 parents on both sides,
  "PARITY OK", all three times; the paper part 72 ladders, 135 entries, P&L $11,017. Both event logs (1021 and 1304
  lines) identical.
- **Live-path simulation, release 2's command** `python bot/spot/live_sim_test.py "2025-10-10 20:00"
  "2025-10-11 02:00"`: 540 minutes, 111 entries, 134 exits, P&L $11,723.34, bot equity equal to the exchange's to
  $0.000151, PASSED, all three times; event log (1504 lines) identical.
- **The same with `"--death=2025-10-10 21:10"`**: 109 entries, 135 exits, P&L $8,421.28, difference $0.000159,
  PASSED, all three times; event log (1334 lines) identical. Release 2's published number is the run without the
  death.
- **`merge_test.py`** 21 of 21, **`trades_bar_test.py`** 37 of 37, **`usdc_test.py`** 11 ok, **`newest_bar_test.py`**
  73 of 73: passed, output identical all three times.
- **`bash bot/spot/deploy/paper_next_test.sh`** 11, **`paper_commit_test.sh`** 38, **`wickctl_test.sh`** 7: passed
  all three times. One line of `paper_commit_test` check 18 differed once (a timing count, 3 of 11 attempts versus
  2 of 11 inside a 3 s deadline), passing both times; the script is not changed here.
- **`python scripts/owner/bar_source/test_bar_source.py`** (builds an engine from `config.json`): 53 of 53, output
  identical before and after step B.
- **New, `python bot/spot/release_inputs_test.py`**: 66 of 66 after step B (65 before it; one check runs only when
  `config.json` is on trades). Covers the rules of `apply`, `applies`, `describe`, `preflight_file`; Python 3.8
  grammar and a light import; `run.py status` end to end on a pre-release-3 live file, a live file with its own
  list (`["BTC", "ETH"]`: the release's list is used, one note), `inputs_local`, and `config.tb.json`; the live files
  unchanged byte for byte; a temp package copy with `config.json` missing and with bad JSON (`status`, `stop`,
  `resume`, `live` with a stand-in engine all complete); the live warning (line and event) present on candles and on
  trades without the guard, absent on trades with the guard; the key and live-switch checks still stopping before
  the engine is built; the real engine's `log("warning", ...)`.
- **New, `python bot/spot/live_sim_inputs_test.py "2025-10-10 20:00" "2025-10-11 02:00"`** (inputs of `config.json`
  after step B; the same with `--inputs=bot/spot/config.tb.json` before it): PASSED.
  - Inputs run against the candle run: every log line equal, heartbeats aside (1487 lines; 111 entries, P&L
    $11,723.34); heartbeats equal apart from the counters and step timing; 2892 bars built from trades, no
    fallback, `btc_stale` 0, `skip_old` 0.
  - Switch run (candle mode 20:00 to 21:00, then a new process on the new inputs on the same state): no exception;
    15 ladders open before and the same 15 after; every entry and exit (245 lines) as in the candle run; P&L
    $11,723.34. The new process logs its own start-up: a backfill, a fee tier, and seven `coin balance differs`
    warnings from the start-up reconcile (fills of the minute before, booked moments later).
- **The same with `"--death=2025-10-10 21:10"`**: PASSED; 1317 lines equal; 109 entries, P&L $8,421.28; switch
  run: 15 ladders kept, 244 entry and exit lines equal.

Not run here: `sandbox_test.py` (Coinbase sandbox, its own workflow), `trades_bar_check.py` and `tb_smoke.py`
(network), and `scripts/owner/bar_source/test_part2_rule.py`, which fails the same way on the untouched branch in
the local copy (it needs `reports/owner/reconcile_tb/i2_t18`, not copied).

## Tests to be run on a runner
Both use the generic runner `hunt2.yml` on this branch; `commit` stays empty, nothing is written back.

- **Every offline spot test, one at a time** (`scripts/owner/release3/run_spot_tests.py`): `merge_test`,
  `trades_bar_test`, `usdc_test`, `newest_bar_test`, `release_inputs_test`, `replay_test 2025-10-10 2025-10-12`,
  `live_sim_test` with and without the death, `live_sim_inputs_test` with and without the death, the three deploy
  shell tests and `test_bar_source.py`. It prints, per file, the exit code, the PASS/ok and FAIL counts and the
  result lines, and exits non-zero if any file fails. About 1.5 to 2 hours (the parity replay took 45 minutes here
  on 2 cores).

  ```
  gh workflow run hunt2.yml -R milesmcqueen98-code/crypto-edge --ref owner/release-3 \
    -f script=scripts/owner/release3/run_spot_tests.py -f tag=rel3-spot-tests \
    -f sparse="bot edge scripts/owner scripts/forward reports/cfm_products.csv \
      reports/wick1m/spot_ticks_wide.csv data/minute data/cfm"
  ```

  Expected, from the runs here: the numbers in the section above, "files with a failure: 0".
- **Paper smoke run of the main book's new config on real market data, no keys, no orders**
  (`bot/spot/tb_smoke.py`, as release 2 used it for the third book).

  ```
  gh workflow run hunt2.yml -R milesmcqueen98-code/crypto-edge --ref owner/release-3 \
    -f script=bot/spot/tb_smoke.py -f args="--minutes 10 --state-dir /tmp/main_smoke --config bot/spot/config.json" \
    -f tag=rel3-main-smoke -f sparse="bot edge reports/cfm_products.csv reports/wick1m/spot_ticks_wide.csv"
  ```

  - **How long.** It waits until minute 20 or 50 of the hour (up to 30 minutes), then runs `run.py paper` for 10
    minutes after the 3 to 5 minute backfill, so it covers a heartbeat at :30 or :00. About 15 to 45 minutes plus
    the runner's set-up.
  - **What proves the trades path.** `tb_smoke.py` prints the exit code, the event kinds, the last 25 events and
    every heartbeat. In each heartbeat: `tb_built` equals the number of listed coins (6) times the minutes stepped
    since the previous heartbeat, with no `tb_fb_unverified`, `tb_fb_error`, `tb_fb_budget` or `tb_fb_limited`, and
    `step_s` shows when the data was ready. No `error` event, exit code 0. Release 2's run of the same values in
    `config.tb.json` showed 48 bars from trades in 10 minutes and no fallback.
  - **What it cannot show.** The engine logs counts, not coin names: that the six built bars are BTC, ETH, SOL, XRP,
    LTC and ZEC follows from `trades_coins` (the engine asks only listed coins; tested offline in
    `newest_bar_test.py`). `run.py`'s own stdout, with the inputs line, is discarded by `tb_smoke.py`. `skip_old`
    (unlisted coins whose candle answer was old, guard on) is expected to be above zero on real data, as in the
    third book.

## Where a config is loaded or passed (step C list), and what each does after step B
- **`bot/spot/run.py` (`--config`, default `config.json`).** Paper books run their own file. A file named
  `config.live.json` takes the input keys from `config.json`.
- **`bot/spot/deploy/wickbot.service`, `wickctl` (every command, `paper-test` too), `configure.py`,
  `setup_vm.sh:20`.** All use `config.live.json`, so the live bot and `wickctl paper-test` run the release's inputs.
  `configure.py` and `setup_vm.sh` load and write the file themselves, not through `run.py`, so they never freeze
  release values into it. A VM set up after release 3 gets the three keys in its file (a copy of the new
  `config.json`); they are replaced from `config.json` at every start anyway.
- **`.github/workflows/paper-spot.yml`.** Line 44, the main book (default `config.json`), and line 46, W2
  (`config.w2.json`): newest minute from trades with the guard from the first run after the merge. Line 79, the
  third book: unchanged.
- **`.github/workflows/paper-spot-t18.yml`.** Its own `config.t18.json` on another engine commit: unchanged.
- **`bot/spot/replay_test.py:229`** (paper part), **`bot/spot/live_sim_test.py:239`** (any `--config`): set
  candle mode in their own code. Identical results.
- **`bot/spot/newest_bar_test.py:45`.** Removes the six input keys from its base settings (engine defaults:
  candles, guard off); every case sets the switches it tests. Identical results.
- **`bot/spot/tb_smoke.py:22,32`.** Its own `--config` (default `config.tb.json`). Given `config.json` it now runs
  the trades mode, as intended for the smoke run.
- **`scripts/owner/reconcile/fetch_and_compute.py:162` (`make_engine`).** Builds an engine from `config.json` in
  trades mode now, but only calls `arrays`, `fresh` and the model settings, which do not read the mode (no
  `update_spot`, no `step`). Not changed. Its offline user `scripts/owner/bar_source/test_bar_source.py`: 53 of 53
  before and after step B, identical output.
- **`scripts/owner/paper_status.py:42,519`.** Reads `trades_coins` from `config.tb.json` only: unchanged.
- **`bot/spot/merge_test.py`, `usdc_test.py`, `trades_bar_test.py`, `trades_bar_check.py`, `sandbox_test.py`.**
  Load no config.
- **`bot/run.py`, `bot/replay_test.py`, `.github/workflows/paper.yml`, `paper-smoke.yml`.** The older bot's
  `bot/config.json`: unrelated.
- **`edge/`.** No config is loaded.

## Not tested
- **A real VM.** No test ran `wickctl update`, `wickctl status` or the service on a real machine. `status` was run
  end to end on temp files; `live` only with a stand-in engine (no keys, no network).
- **`preflight` as a whole.** It needs keys and the network. Covered: the write-back function (`preflight_file`):
  the file as read plus the two keys, nothing from the release, a missing bid lifetime, a file with its own inputs.
  Not covered: the call site in `run.py` (read, not run) and the network part.
- **The live warning event on a real engine in live mode.** Covered: `run.py live` against a stand-in engine (order
  init, log, run; text; present or absent by the inputs); the real engine's `log("warning", msg=...)` in paper mode
  writes one `warning` event. Not run: a real live engine (needs keys).
- **The new inputs on real market data in the main book's config.** To be run on a runner (smoke command above). The
  third book has run the same values for three days.
- **Trades for the live VM's network.** The trades requests come from the VM's own address; rate limits there were
  not measured. Release 2's measurements are from GitHub runners.
- **`scripts/owner/release3/run_spot_tests.py` itself** was not run here (its parts were, one by one).
- **Python 3.8 to 3.10.** Checked only with Python 3.13 and `ast.parse(..., feature_version=(3, 8))` for
  `release_inputs.py` and `run.py`.

## Found while preparing this, for a bot with real money
- **The watchdog** (`bot/spot/deploy/watchdog.py`) alerts on events of kind `halt` (urgent), `error`, `warning`
  (high) and `reject` (default), on no completed minute for 5 minutes, on a missing state file, and once a day with
  equity. So the new start-up `warning` event reaches the phone. A `stale_input` event (BTC stale with the guard on)
  does not reach an alert; it is counted in the heartbeat (`btc_stale`) and visible in `wickctl log`.
- **A restart during fills logs balance warnings.** In the switch simulation the new process's start-up reconcile
  logged seven `coin balance differs from the bot's open rungs` warnings (fills on the exchange in the minute before
  the restart, booked by the bot moments later); entries, exits and P&L were unchanged. The baseline live-path
  runs log the same kind (7 with the death restart, 2 without). On a VM each such warning becomes a phone alert.
  Engine behaviour, not changed here.
- **`config.json` is now read by every command given the live file.** If it cannot be read, the command goes on with
  the live file's own inputs (tested for `status`, `stop`, `resume`, `live`). A `live` start then warns, because a
  live file made before release 3 states no inputs and runs on candles without the guard.
- **`status` already imported pandas** before this change; `stop` and `resume` do not. `bot/__init__.py` and
  `bot/spot/__init__.py` are empty; importing `release_inputs` loads no pandas, numpy or lightgbm (tested).
- **`preflight --capital`** used to save the override into the live file with the rest; now `preflight` writes only
  the two keys onto the file as read, so a `--capital` given to `preflight` is no longer saved. `wickctl` never
  passes `--capital`.
- **`wickctl paper-test`** runs `paper` with the live file, so it now runs the release's inputs (trades requests for
  the listed coins) with the live capital as paper capital.
- **The WARNING line goes to stdout** (`live_spot/stdout.log` under the service), which `wickctl log` does not show;
  the `warning` event is what reaches `wickctl log` and the phone.
- **`configure.py`** copies `config.json` whole when no live file exists, and otherwise re-saves the live file as it
  read it with the new capital. It never adds or removes input keys.
- **`run.py preflight` writes to any file that is not `bot/spot/config.json`** (unchanged behaviour); given
  `config.tb.json` or `config.w2.json` it would write into those tracked files.
- **This branch is behind `origin/main`** by commits in `reports/` and `scripts/owner/paper_status.py` only; nothing
  under `bot/` differs.
