# Input release candidate (for release 5): facts for the release note

*Note, Nov 16 2026.* Merged onto `main` after release 4 (the order path) on branch `owner/release-5`. This build is
no longer "release 4"; it is the candidate for release 5. Renamed at the merge: this file (was
`reports/owner/release4_candidate.md`) and the runner driver's folder (`scripts/owner/release4/` is now
`scripts/owner/input_release/`; the driver now runs the union of the order path's and this build's test files).
The numbers below were made on branch `owner/release-4` before the merge; the runner commands quoted below are as
prepared there (`--ref owner/release-4`, the driver's old path). They are confirmed again by the runner suite on
`owner/release-5` (`scripts/owner/input_release/run_spot_tests.py`). Runner job: to be filled in by the owner.

Branch `owner/release-4`. Prepared as a candidate; whether it ships is decided by the fourth paper book's registered
read (reports/owner/bar_source_prereg.md, Part 2), due Nov 15. This file states facts only.

## What changed, file by file
- **`bot/spot/engine.py`: the option of branch `owner/engine-c`, brought over unchanged** (commits 8a9a1480 and
  58eba8bd; on this branch 0a68417e and fd0b2ff3). The change against `main` equals the change of 53f5ca08 to
  58eba8bd line for line (index lines aside). 36 lines added, 2 changed. `bot/market.py` is not changed.
  - **The key.** `"trades_rows"`: `"keep"` (the default; also what a missing key means) or `"candle_after"`. Any
    other value stops the engine at start-up (`ValueError`). It acts only with `"newest_bar": "trades"`.
  - **A provisional row.** In trades mode, the row of a listed coin's newest minute is built from the venue's public
    trades list at the step after the minute closes (as in release 3). With `"candle_after"` that row, and a minute
    the trades list proved empty, is provisional: it stands only until a late enough candle answer covers it.
  - **When a candle answer counts as late enough ("confirmed" for a minute).** The answer was made (Date header
    minus Age header) at least 60 + `confirm_s` seconds after the minute began; `confirm_s` defaults to 25, so 85 s.
    The minute that just closed is never confirmed at its own step, so the decision for a minute always uses its
    trades bar, and the stale guard and the trades pass work on it as with `"keep"`. With answers made about 6 s
    after each step, the replacement happens at the next step, one minute later.
  - **What is replaced.** A row in a confirmed answer replaces the provisional row (all five values). A verified
    empty minute is filled by the candle row the same way. The minute then counts as a confirmed candle row under
    the existing rules: an older answer cannot undo it, and the repair pass does not rebuild it.
  - **What is dropped.** If a confirmed answer has no row for a provisional trades-built minute that lies between the
    answer's first requested minute and its newest row (that newest row excluded), the row is deleted, because the
    venue has no bar there. A minute at or after the answer's newest row is left alone. An answer that is not
    confirmed for the minute changes nothing.
  - **Counters,** in the heartbeat, only in this mode: `tb_replaced` (trades-built rows replaced by a confirmed
    candle row), `tb_replaced_diff` (of those, the candle's close differed from the trades bar's by more than one
    tick), `tb_dropped` (trades-built rows deleted because the confirmed answer had none), `tb_pending` (rows 3 to 6
    minutes old still trades-built; counted per step and summed, like `rows_open`).
  - **With the key absent** the code takes exactly the old paths (`"keep"`): the replay, every event log and every
    test result below are identical to the untouched branch.
- **`bot/spot/candle_after_test.py`, `bot/spot/config.t18.json`, `scripts/owner/engine_c/run_spot_tests.py`** (from
  `owner/engine-c`, byte for byte). `config.t18.json` is the fourth paper book's file.
- **`bot/spot/tb_smoke.py`** (from `owner/engine-c`, the same change): `--parity` runs the paper engine in the same
  process and then compares the rows it holds with a new fetch of the venue's candles (below).
- **`bot/spot/release_inputs.py`: the inputs line in plain words.** `describe` appends `; the venue's candle replaces
  each trades row afterwards` for `"candle_after"`, nothing for `"keep"` (the default behaviour), and `; trades_rows
  <value>` for any other value. Nothing else in the file changed; `apply` already took `trades_rows` from the release.
- **`bot/spot/config.json`, `bot/spot/config.w2.json`: the fourth book's inputs** (own commit). `"newest_bar":
  "trades"`, `"stale_guard": true`, `"trades_coins"` with all 18 coins in `config.t18.json`'s order (BTC, ETH, SOL,
  XRP, DOGE, LTC, LINK, BCH, SUI, XLM, HBAR, NEAR, AAVE, HYPE, ENA, PEPE, ONDO, ZEC), `"trades_rows":
  "candle_after"`. `config.json` is now byte for byte `config.t18.json`; W2 differs from it only in its rung weights
  (`"8": 2`). `config.tb.json` and `config.t18.json` are not changed.
- **`bot/spot/README.md`.** The option's text from `owner/engine-c` in "Newest minute from trades"; the list
  `config.json` now carries; one sentence on why release 3's coin rule was for kept rows; the `wickctl status` example
  line; the test lines.
- **Tests.** `release_inputs_test.py` (new wording, three `describe` cases, a live file holding release 3's inputs);
  `live_sim_test.py` (`--switch-from`, and a made-up difference hook in its trades feed; the candle path is untouched);
  `live_sim_inputs_test.py` (cases C2 and D); new `scripts/owner/input_release/run_spot_tests.py`.
- **Not changed.** `bot/market.py`, `bot/spot/run.py`, every safety check in `bot/spot`, `wickctl`, `configure.py`,
  `setup_vm.sh`, `watchdog.py`, the service file, `.github/`, `reports/owner/RELEASES.md` and the other owner files.

## A VM that took release 3, at `wickctl update`
- **What `wickctl update` does** (unchanged since release 1): it stops the service, pulls, installs the new `wickctl`,
  and starts the bot again only if it was running.
- **At its next start** `run.py` takes the six input keys from the new `config.json` (release 3's rule): newest minute
  from trades for all 18 coins, stale guard on, and `"trades_rows": "candle_after"`. Capital, coins, fees and risk
  limits stay as the live file has them. The file is not rewritten.
- **A bot that was running** restarts on the new inputs with its existing state. In the simulation (C1, C2 below) the
  switch raised nothing, kept every open ladder, and every entry and exit was as in the run without a switch. The
  engine keeps no provenance in its state file; the new process rebuilds it from the start-up backfill.
- **A bot that was stopped** stays stopped and takes the new inputs when started.
- **What its owner sees in `wickctl status`.** First line:
  `inputs: newest minute from trades for BTC, ETH, SOL, XRP, DOGE, LTC, LINK, BCH, SUI, XLM, HBAR, NEAR, AAVE, HYPE,
  ENA, PEPE, ONDO, ZEC; candles for the other coins; stale guard on; the venue's candle replaces each trades row
  afterwards (from bot/spot/config.json)`.
  - A VM set up before release 3 (its live file has no input keys): no note line.
  - A VM set up on release 3 (`setup_vm.sh` copied release 3's `config.json`): one note,
    `trades_coins: the live config had ['BTC', 'ETH', 'SOL', 'XRP', 'ZEC'], the release's [...18 coins...] is used`.
    The file has no `trades_rows`, so there is no note for it; the release's value is in use.
  - Then the status lines as before. Both cases were run end to end (`release_inputs_test.py`).
- **No start-up warning.** `live` warns only when the inputs are not trades with the stale guard; these are.
- **Emergency switch** (unchanged): `"inputs_local": true` in `config.live.json` keeps the file's own inputs.

## Tests run here (offline, from a copy of the branch with `data/` linked read-only)
Baseline is the untouched branch (`4886e354`, equal to `origin/main`). Then the branch after step A (the two
picked commits, `fd0b2ff3`) and after step C (`c1e4ab57`, the final code). "Identical" means stdout and every event
log named in it equal line for line, heartbeats and their counters included (step timing and random order ids
masked). Commands from the repository root of the copy.

- **Parity replay** `python bot/spot/replay_test.py 2025-10-10 2025-10-12`: 156 rungs, 88 parents on both sides,
  "PARITY OK"; paper part 72 ladders, 135 entries, P&L $11,017. Baseline and after step A: stdout and both event logs
  (1021 and 1304 lines) identical. After step C (`c1e4ab57`): identical as well.
- **Live-path simulation** `python bot/spot/live_sim_test.py "2025-10-10 20:00" "2025-10-11 02:00"`: 540 minutes,
  111 entries, 134 exits, P&L $11,723.34, bot equity equal to the exchange's to $0.000151, PASSED. Baseline, after
  step A and after step C: stdout and event log (1504 lines) identical.
- **The same with `"--death=2025-10-10 21:10"`**: 109 entries, 135 exits, P&L $8,421.28, difference $0.000159,
  PASSED; identical all three times (1334 lines).
- **`merge_test.py`** 21 of 21, **`trades_bar_test.py`** 37, **`usdc_test.py`** 11 ok, **`newest_bar_test.py`** 73 of
  73, **`deploy/watchdog_test.py`** 31, **`bash deploy/paper_next_test.sh`** 11, **`paper_commit_test.sh`** 38,
  **`wickctl_test.sh`** 7, **`scripts/owner/bar_source/test_bar_source.py`** 53 (builds an engine from `config.json`):
  passed all three times with the same output. Lines that differ between runs carry a wall-clock time (watchdog), a
  set printed in a different order (`release_inputs_test`), or the known timing count of `paper_commit_test` check
  18 (3 or 2 of 11 attempts inside its deadline), as release 3 recorded; the checks are the same and pass.
- **`candle_after_test.py`** (from `owner/engine-c`): 30 of 30, "candle_after_test: all passed", after step A and
  after step C, identical output. Its part 2 ran here (the stored crash): the same event log with the key absent and
  `"keep"` in three modes (530 events in the "candle_after" run, no error).
- **`release_inputs_test.py`**: 66 of 66 on the baseline and after step A; 68 of 68 after step B (two new
  `describe` checks); 73 of 73 after step C (the case of a live file holding release 3's inputs, and one check that
  runs only when `config.json` sets `trades_rows`). Two `status` cases end to end on the step C config:
  - a live file as a VM set up before release 3 has it: first line the release's line with the marker, no note,
    then every status line as before; file unchanged;
  - a live file holding release 3's input keys: the same first line, one note (`trades_coins`, naming the five and
    the eighteen), no note for `trades_rows` (the file has none; the release's value is in use), then every status
    line as before; file unchanged.
- **`live_sim_inputs_test.py "2025-10-10 20:00" "2025-10-11 02:00"`** on the step C config: PASSED, 22 checks. On the
  baseline and after step A (the old file, release 3's inputs): PASSED, 9 checks, stdout identical, and the kept
  event logs of A, B and C identical, heartbeats included. To keep the event logs for these comparisons each run was
  repeated through a small wrapper that only turns off the test's clean-up of its temp folders; the plain command
  gave the same result lines.
  - B (the release inputs from the start, trades feed made from the candles): every log line equal to the candle
    run's, heartbeats aside (1487 lines; 111 entries, P&L $11,723.34); heartbeats equal apart from the counters and
    step timing. From the heartbeats: 8,187 bars built from trades, 8,153 trades rows replaced by the candle, 0 of
    them differing, 0 dropped, 0 still waiting (`tb_pending`), 0 fallbacks, `btc_stale` 0, `skip_old` 0. The
    non-heartbeat log is identical to release 3's B.
  - C1 (candle mode until 21:00, then the release inputs on the same state): no exception; 15 ladders open before
    and the same 15 after; every entry and exit (245 lines) as in the candle run. 7,168 bars built, 7,134 replaced,
    0 differing, 0 dropped, 0 waiting, no fallback. The whole log without heartbeats is identical to release 3's C
    (1496 lines; the new process logs its own start-up: a backfill, a fee tier, balance warnings).
  - C2 (release 3's inputs until 21:00, then the release inputs): the same as C1: 15 ladders kept, 245 entry and
    exit lines equal, the whole log without heartbeats identical to C1's. 7,328 bars built (the extra 160 are the
    first half hour on five coins), 7,134 replaced, 0 differing, 0 dropped.
  - D (only without the death): 20 altered minutes of ETH and SOL (every 37th traded minute of 20:00 to 02:00, close
    three ticks above the candle's) and one XRP minute (21:40) with trades but no candle. All 20 were handed out as
    trades bars and all 20 hold the candle's five values at the end; the XRP minute has no row;
    `tb_replaced_diff` 20 and `tb_dropped` 1 over the run (heartbeats plus the minutes after the last one); live-path
    checks pass.
  - **The made-up feed needed no change for the replacement:** its answers report being made 8 s after the request's
    end, so a minute's row is confirmed (85 s after the minute began) by the answer of the next step, 128 s after
    the minute began. Additions to the feed are only for case D (`alter`, `no_candle`, `served`).
- **The same with `"--death=2025-10-10 21:10"`**: PASSED, 16 checks (D is not run with the death). B: 1317 lines
  equal to the candle run's, 109 entries, P&L $8,421.28; 7,711 bars built, 7,643 replaced, 0 differing, 0 dropped, 0
  waiting, no fallback. C1 and C2: 15 ladders kept, 244 entry and exit lines equal; 6,692 and 6,852 bars built,
  6,624 replaced each, 0 differing, 0 dropped. The kept logs of A (in full) and of B, C1, C2 (heartbeats aside) are
  identical to the baseline's A, B and C. Release 3's file on the baseline and after step A: PASSED, 9 checks,
  identical.

Not run here: `sandbox_test.py` (Coinbase sandbox), `trades_bar_check.py` and `tb_smoke.py` (network),
`scripts/owner/bar_source/test_part2_rule.py` (needs `reports/owner/reconcile_tb/i2_t18`, not in this checkout),
`scripts/owner/input_release/run_spot_tests.py` and `scripts/owner/engine_c/run_spot_tests.py` themselves (their parts
were run one by one).

## Tests to be run on a runner
Both use the generic runner `hunt2.yml` on this branch; `commit` stays empty, nothing is written back.

- **Every offline spot test, one at a time** (`scripts/owner/input_release/run_spot_tests.py`: release 3's list plus
  `candle_after_test.py`; it prints, per file, the exit code, the PASS/ok and FAIL counts, the result lines and the
  time, and exits non-zero if any file fails). The live-path inputs test now runs five simulations without the death
  and four with it. About 2 to 2.5 hours on the runner (the parity replay took 35 to 45 minutes here when it had a
  core to itself).

  ```
  gh workflow run hunt2.yml -R milesmcqueen98-code/crypto-edge --ref owner/release-4 \
    -f script=scripts/owner/release4/run_spot_tests.py -f tag=rel4-spot-tests \
    -f sparse="bot edge scripts/owner scripts/forward reports/cfm_products.csv \
      reports/wick1m/spot_ticks_wide.csv data/minute data/cfm"
  ```

  Expected, from the runs here: the numbers above and "files with a failure: 0".
- **Paper run of the main book's new config on real market data, with the parity check** (no keys, no orders):

  ```
  gh workflow run hunt2.yml -R milesmcqueen98-code/crypto-edge --ref owner/release-4 \
    -f script=bot/spot/tb_smoke.py \
    -f args="--minutes 45 --parity --state-dir /tmp/main_smoke --config bot/spot/config.json" \
    -f tag=rel4-main-parity -f sparse="bot edge reports/cfm_products.csv reports/wick1m/spot_ticks_wide.csv"
  ```

  - **How long.** It waits until minute 20 or 50 of the hour (up to 30 minutes), builds the engine in its own process
    from `config.json`, backfills (3 to 5 minutes), steps for 45 minutes, then fetches 45 minutes of candles once
    per coin. About 50 to 80 minutes plus the runner's set-up. Run 43044140767 did the same with `config.t18.json`,
    whose input keys `config.json` now has byte for byte.
  - **(a) Every listed coin built from trades.** In each heartbeat: `tb_built` plus `tb_empty` (verified minutes
    with no trades) equals 18 times the minutes stepped since the previous heartbeat, and no `tb_fb_unverified`,
    `tb_fb_error`, `tb_fb_budget` or `tb_fb_limited`. The engine asks the trades list once per listed coin per step,
    so 18 a minute means every coin each minute; it logs counts, not names.
  - **(b) Trades rows replaced by the venue's candle.** `tb_replaced` in the heartbeats close to `tb_built` (each
    row is replaced one step later); `tb_replaced_diff` is the share whose candle close differed; `tb_dropped` the
    rows the venue had no bar for; `tb_pending` near 0. The fourth book's figures for comparison: below.
  - **(c) Every row equals a fresh fetch.** The table printed after "parity: venue candles ...": one row per coin,
    18 rows; for each, `differ` 0, `engine_only` 0, `venue_only` 0, `identical` equal to the minutes with a row, and
    `trades_built` 0 (no row older than three minutes still trades-built). No "REFUSED" line and exit code 0 (3 means
    the parity fetch was refused or rate-limited). Also: no `error` event in the event kinds, and the "errors and
    warnings" list empty apart from expected `stale_input` lines, if any.
  - **What it cannot show.** `tb_smoke.py --parity` builds the engine directly, so `run.py`'s inputs line and the
    live file path are not exercised there (they are in `release_inputs_test.py`).

## Not tested
- **A real VM.** No test ran `wickctl update`, `wickctl status` or the service on a real machine. `status` ran end
  to end on temp files; `live` only with a stand-in engine (release 3's tests, unchanged).
- **The option on real market data in this branch's configuration.** To be run on a runner (command above). The
  fourth paper book has run the same input keys since Nov 11 on engine commit 58eba8b, whose engine file is the one
  here.
- **18 trade requests a minute from the VM's own address.** Rate limits there were not measured; release 3 sends
  five. All measurements are from GitHub runners.
- **Differences between trades bars and candles on the live path come only from the made-up feed** (case D). The
  feed's candle answers are always on time; old or unreadable answers on the live path are tested only in
  `newest_bar_test.py` and `candle_after_test.py` (synthetic tables).
- **The two runner drivers** were not run here as wholes.
- **Python 3.8 to 3.10.** Checked only with Python 3.13 and `ast.parse(..., feature_version=(3, 8))` for the files
  `run.py` imports that changed (`release_inputs.py`, `engine.py`).

## Data step with 18 coins on trades, as the documents record it
- **The fourth paper book** (18 coins on trades, the same inputs; reports/owner/PAPER_STATUS.md as on `main` in the
  report of 22:42 UTC on Nov 14, which this branch does not carry): data step median 13.4 s after the minute over
  138 heartbeats, half-hour maximum 20 s or less in 97.8% of them, largest 23.4 s; by day the medians were 13.8,
  13.5, 13.4 and 12.5 s. Its registered bar is a median of 15 s or less (bar_source_prereg.md, deviation log Nov 11,
  11:13 ET). The report of 14:13 UTC, on this branch, had 13.5 s over 114 heartbeats. Also from the 22:42 report:
  71,588 of 71,622 attempted coin-minutes verified (99.95%; 32 budget fallbacks, 2 unverified, no rate limit);
  `tb_replaced` 68,429, `tb_replaced_diff` 10,533, `tb_dropped` 1,813; `tb_pending` 143 of 74,070 coin-minutes.
- **Smoke run 43044140767** (45 minutes, 18 coins): data step median 13.3 to 13.5 s, maximum 17.7 s.
- **For comparison,** the third book (six coins): median 10.1 s over its three days; release 3's runner smoke (five
  coins): median 11.1 s. Eighteen trade requests in a row take about 3.5 s more than six (LOG.md, Nov 11).

## Found while preparing this, for a bot with real money
- **The inputs line says "candles for the other coins" when all 18 are listed.** There are no other coins. The rule
  for the coin part is release 3's and was left as it is (`describe` has no coin list to compare with); the whole
  line for this config is the one under "What its owner sees" above.
- **The `trades_rows` part is printed in candle mode too.** `describe` adds it whenever the key is set, but the
  engine reads the key only in trades mode. A VM set up from this release copies `config.json` into its live file,
  `trades_rows` included. If its owner then uses the emergency switch as release 3's note gives it (`"inputs_local":
  true, "newest_bar": "candles", "stale_guard": false`), the bot runs on candles as intended, but `status` reads
  `inputs: candles for every coin; stale guard off; the venue's candle replaces each trades row afterwards`. A VM
  set up before this release has no `trades_rows` in its file and shows the plain candle line.
- **The emergency switch back to release 3's inputs** would need `"inputs_local": true` with release 3's three keys
  and no `trades_rows` (or `"keep"`) in the live file. Not tested as such; the rule (`apply`, `inputs_local`) is.
- **The start-up warning still names release 3** ("without the release 3 inputs (trades with the stale guard)"). It
  is not shown with these inputs. Left unchanged (a safety check).
- **The decision row differs from the candle that replaces it in about one replaced row in seven.** In the fourth
  book 10,533 of 68,429 replaced rows (15.4%, report of 22:42 UTC on Nov 14) had a candle close more than a tick from
  the trades bar the decision had used. The row is corrected one minute later; the decision of that minute is not.
  This is the late cut that bar_source_prereg.md describes; Part 2's read measures its effect.
- **No coin is left on the candle path.** Every coin's newest minute depends on the trades list. On Nov 13 the third
  book skipped 316 coin-minutes for an old candle answer in 12 hours while the fourth book, reading no newest bar
  from candles, skipped none for this (LOG.md, Nov 13, 08:46). A failing trades feed shows as fallbacks
  (`tb_fb_*`) for all 18; BTC's falls under the stale guard and its watchdog alert (release 3).
- **Restarts were clean in the simulation, but the engine keeps no provenance across a restart.** A new process
  starts from the backfill's candles and rebuilds the still-open recent minutes from trades (the repair pass); the
  old process's provisional rows and its counters since the last heartbeat are not carried over (in C2 the counters
  of 20:30 to 21:00 are not in any heartbeat).
- **The data step is about 3.5 s later than with five coins** (above): new bids go out later in the minute.
- **README.** The engine-c text says the option is the fourth book's (`config.t18.json`); this branch's README now
  also says `config.json` uses it from release 5 (it said release 4 before the merge). The release note and the
  other owner files are not touched.
- **Branch state.** No conflict came up in the cherry-pick: `main`'s README changes and the option's README lines
  merged by themselves at the place the brief named. Commits since `main`: the two picked commits (messages kept,
  the two trailer lines added), step B, a work-in-progress commit of step D's code (pushed at the coordinator's
  request before its runs), step C, then the results and these files. `main` moved on while this was prepared (to
  cfba1f0a at the time of writing) in `reports/` and the paper books' folders only; nothing under `bot/`,
  `scripts/`, `edge/` or `.github/` differs from the branch's base, and the engine and `tb_smoke.py` diffs against
  today's `main` are still the engine-c diffs line for line.
- **Test conditions here.** Another agent ran replay tests in the same two-core container for most of this work, so
  the times above are longer than they would be alone.
