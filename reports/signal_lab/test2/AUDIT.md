# Signal lab 2: the independent look-ahead audit (Nov 9 2026)

A separate Opus agent at max effort, read-only, audited the print-feature test before the holdout was read. It gave
two reports, reproduced below as received by the orchestrator. Times are ET from the shell clock.
- First report, 18:59: pass with conditions. The conditions were adopted in deviation 3 of
  ../prospective_prereg.md before any holdout number existed.
- Second report, 19:15: final pass, after the margin code, the leak counts and the 60 s tables existed. The lock
  (AUDIT_PASSED) was created at 19:19, once the selection reading on the 60 s table had finished.

Its scratch scripts are kept in audit_scripts/ (as it left them; not reviewed). Its recount of the leak flags can be
redone from ../prints/leak_flags.parquet. The later fact-check of the report recomputed every number with its own code
(factcheck_scripts/seeds.py is kept), and the orchestrator's own recomputation of the gates and scorecard is
verify_scorecard.py.

## First report

**Look-ahead audit before the holdout read: PASS WITH CONDITIONS. One major finding (the candle/print boundary), three minor.**

I worked read-only, created no RF6/RF6H result and opened none. Both light unit tests pass (test_lab2 7/7, test_prints). Scratch scripts are in /tmp/claude-0/-home-claude/6293119a-99b0-5c43-9377-f506742f80e1/scratchpad/audit2/.

**Major**

1. **B: the candle clock can put prints stamped before q into the fill candle, and this is more common in the holdout eras.**
   - `ts` is the start of the candle minute: px_last (last print before q) equals the close of candle ts−1 in 95.9% of candidates, and the close of candle ts in only 1.4%. So "prints < q" excludes the fill minute on the print clock (prints_features.py:91-93).
   - Where the candle and print clocks disagree at q:
     | Read era | q edge disagrees | Leak direction, full candle windows | Leak direction, incl. windows with missing candle rows |
     |---|---|---|---|
     | Selection | 3.5% | 0.08–0.14% | 0.6% |
     | Apr–Nov 2026 | 7.4% | 0.20–0.32% | 1.6% |
     | 2022-23 | 7.7% | <0.05% | 1.6% |
   - About 90% of the signed disagreements go the safe way (candle q−1 holds prints stamped at or after q). "Leak direction" means candle q holds prints stamped before q.
   - In windows with missing candle rows, a whole minute of prints may sit in candle q, and only a 60 s margin removes that.
   - Bias: inflates RF6/RF6H, more in the holdout than in selection.
   - Deviation 2 applies its 0.5% bar per data era (prospective_prereg.md:124-125). Pooling 2024-26 into one "main" era dilutes Apr–Nov 2026.
   - Fix:
     - Apply the 0.5% bar in each read era, and count missing or merged q−1 candles as leaks.
     - Use at least 5 s, and 60 s if those cases exceed 0.5% (my broad estimate says they do).
     - Use one margin for every row. Don't set flagged rows to NaN: the flag is computed from candle q, so masking would itself leak.
     - Log this before any holdout number.

**Minor**

2. **D: the mixed panel follows deviation 1 exactly** (lab2.py:191-203, model.py:927-951; zero armed-state mismatches is asserted).
   - No price look-ahead: the candidate set only chooses which of two decisions known at q−1 is used.
   - Residual approximations act only when cash binds, which is rare at $250K because the ADV cap binds (prereg.md:202):
     - (a) RF6's own arming at non-candidate minutes is replaced by the twin's. This flatters a less selective RF6 and handicaps a more selective one.
     - (b) At the same minute, fill-minute bids carry RF6's values while competing bids carry the twin's values shifted to RF6's threshold. This flatters RF6 if its values above threshold are more spread out.
   - The frozen simulator is immune to both, and armed_cand_only bounds (a) conservatively. Report both, as already declared.
3. **E: holdout hygiene.** RF6H's selection reading trains on 2022-23 labels and F6, which the plan intends. Two unlocked file sets pair holdout F6 with labels: test2_m0/cand_early.parquet, and f6_main joined to lab 1's cand_main.parquet. Nobody should compute F6-vs-label statistics from them before the read.
4. **G: RF6H against RF0 credits the 2021-23 history to the prints.** Lab 1 showed history alone at +0.12 / +0.35. Read RF6H's result together with RF6's.

**No defect (all checked directly)**

- **A:**
  - Windows are [q−30m, q) and [q−5m, q) (prints_features.py:91-105).
  - The big-print pool is strictly before the window start (94, 106-111), and the sweep stays inside the window (115-118).
  - Timestamps are UTC-naive ns throughout (prints_fetch.py:79).
  - I recomputed ADV: day D uses days D−30..D−1 (0 mismatches in 400 days). The join takes each candidate's own day (prints_features.py:221); the largest difference is 2.7e-16 and no row matches the next day's value.
- **C:**
  - Keys are (coin as string, ts as int64 ns): all 32,090 rows map one-to-one with 0 unused, and the join equals a plain key merge.
  - The exported history rows carry exactly their own F6.
  - The walk-forward is unchanged: training uses rows before the quarter minus one day (model.py:315-318).
- **E:**
  - Every holdout path is locked: model.py:121-127 and 416, score.py:252 and 288, test2.py:111.
  - With --sel the walk-forward stops at 2026Q1 (model.py:105, 592), and the NaN predictions after it produce no trades (464).
  - No AUDIT_PASSED file exists. The selection reading now running into test2_m0 uses the 0 s table, which deviation 2 allows.
- **F:** Every book gets the same replay, exit pricing, R2-08 volume factors, ADV table and 15 seeds. Gates, Holm across the two candidates and the scorecard match prereg.md:86-107 (score.py:320-357). maxdd and worst are negative, so the inequalities point the right way.

**Not yet verified:** how many seconds the lag is per candidate, and whether the missing-candle cases are really merged into candle q. The data agent's diagnostic will settle both.

**PASS WITH CONDITIONS:**
1. Choose the margin as in finding 1.
2. Every step, including `early export`, reads the chosen table, saved as f6_<era>.parquet in the --f6 directory, with its sha256 logged. Current 0 s tables: main 5cbf7178…, early 29bb9c1e….
3. Report the frozen-simulator and armed sensitivities beside the binding result.

## Second report

**Second pass: FINAL PASS. No look-ahead found, and the 60 s choice holds. One ordering step remains: start b only after the running m60 selection reading exits.** Read-only throughout; I opened no model results.

1. **Margin code.** The committed version at 440314f is the one I reviewed and ran.
   - With margin 60 the windows are [q−30m, q−60s) and [q−5m, q−60s); the window end is `searchsorted(t, q−m·1e9, "left")`. The sweep and n_prints use the same slice.
   - The big-print threshold is passed through unchanged from the 0 s pool, which ends at q−30 min.
   - The unit test's margin check (5 s and 60 s, 42 cases) passes. A print at q−m or later is excluded, one 1 µs earlier is included, sums match brute force and the threshold is unchanged.

2. **Leak flags.** prints_leak.py implements deviations 2 and 3 as written.
   - My recomputation from leak_flags.parquet matches deviation 4 exactly, including the upper bounds of 1.84% / 5.30% / 5.11%.
   - leak_60 uses only minutes that were fetched, so the undecidable last candidates affect only the 0 s and 5 s bounds.
   - If every "candle q−1 missing, merged into q" case also counted at 60 s, the shares would be 0.01% (selection), 0.29% (Apr–Nov 2026) and 0.34% (2022-23). All stay under 0.5%.
   - No sign of a lag over 60 s: the last print before q matches candle q's close (not q−1's) in 0.13–0.20% of candidates per era, no more than chance matches at candles q+1 and q−3. 80% of the unexplained boundaries match candle q−1 by price.

3. **Tables.**
   - The 60 s tables match the 0 s tables on keys, order, columns, `complete`, threshold and ADV. Every sum and n_prints is no larger (ulp-level only), and no window is empty.
   - sha256: main 583d3de7722160d128cfd2f2abd3ba88a20f69b96e4a1896ac469ec6935d01b6, early 9e65299409ea6434d67b6153dbef43d5673749742113167e54613228aedb982f. The prints_m60 copies are byte-identical.
   - test2_m60/cand_early.parquet (2c4bffba…) was joined from prints_m60, per its log. It equals the 60 s table on all 14,563 rows.

4. **Holdout commands (b and c).**
   - test2.py passes `--out` and `--f6` to every model.py step. The 0 s folder is never read, because F6 is loaded only from the `--f6` path (model.py:383, 400).
   - The history rows are `<out>/cand_early.parquet` (model.py:104). They are re-verified against prints_m60 at fit time (model.py:392-406).
   - The scorer reads reports/signal_lab/test2/config.json (score.py:70), suffix `_u15`.
   - The chain tags `{main,early}_{RF0,RF6,RF6H}_u15[_armed]` don't exist on disk, and lab 1's tags have no `_u15`. test2_m60/cells is absent, so no stale cell can be reused.

5. **Ordering.** The m60 selection reading (PID 26322) is still running.
   - b shares its `main_dose_seed` dataset files and needs about 4.5 GB.
   - Start b only after it exits, and let nothing write to test2_m60/cells before c.

FINAL PASS (create the lock); run b only after the m60 selection reading has exited.

