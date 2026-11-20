# The standstill window of Nov 17 2026, by itself (reported next to the result; it decides nothing in Part 3)

From 21:19 to 21:57 UTC the venue's public trades list showed no new trade for almost any coin while its
candles kept coming (plan, deviation log, Nov 18). Each book's new bids in the window against the research,
and the veto rule fixed on Nov 18 for the fallback: five or more of the fourth book's bids in the window
wrong against the research (a bid it would not have placed, or more than 5 bp from its level) would have
dropped the fallback.

```
== fourth book, 2026-11-17 21:19 to 2026-11-17 21:57 UTC
   bot new bids: 8
     11-17 21:40 DOGE  bot_px 0.05883 res_level 0.058835 err_bp 0 bot_pred 40.3 res_score 40.2775 in_decision True other_side False -> ok
     11-17 21:40 PEPE  bot_px 3.69e-06 res_level 3.69094e-06 err_bp 0 bot_pred 30.7 res_score 30.5987 in_decision True other_side False -> ok
     11-17 21:42 PEPE  bot_px 3.69e-06 res_level 3.69409e-06 err_bp 0 bot_pred 30.7 res_score 30.7181 in_decision True other_side False -> ok
     11-17 21:44 HBAR  bot_px 0.05606 res_level 0.0560695 err_bp 0 bot_pred 41.9 res_score 41.8904 in_decision True other_side False -> ok
     11-17 21:45 DOGE  bot_px 0.05883 res_level 0.0588349 err_bp 0 bot_pred 35 res_score 34.9861 in_decision True other_side False -> ok
     11-17 21:47 HBAR  bot_px 0.05605 res_level 0.0560505 err_bp 0 bot_pred 34.7 res_score 34.7078 in_decision True other_side False -> ok
     11-17 21:49 DOGE  bot_px 0.0588 res_level 0.0588052 err_bp 0 bot_pred 34 res_score 38.327 in_decision True other_side False -> ok
     11-17 21:50 PEPE  bot_px 3.67e-06 res_level 3.67338e-06 err_bp 0 bot_pred 33.1 res_score 33.0995 in_decision True other_side False -> ok
   wrong against the research (other side, or more than 5 bp from the level): 0 of 8
   the research's new bids in the window: 8; with a bot bid within a minute: 8; stale_input_t true on 2
     research 11-17 21:39 DOGE  score 40.0985 bot_arm_pm1 True stale_t True
     research 11-17 21:39 PEPE  score 30.715 bot_arm_pm1 True stale_t True
     research 11-17 21:42 PEPE  score 30.7181 bot_arm_pm1 True stale_t False
     research 11-17 21:44 HBAR  score 41.8904 bot_arm_pm1 True stale_t False
     research 11-17 21:45 DOGE  score 34.9861 bot_arm_pm1 True stale_t False
     research 11-17 21:47 HBAR  score 34.7078 bot_arm_pm1 True stale_t False
     research 11-17 21:49 DOGE  score 38.327 bot_arm_pm1 True stale_t False
     research 11-17 21:50 PEPE  score 33.0995 bot_arm_pm1 True stale_t False
   stale-guard minutes in the window: 2; fills in the window: 0 []
== fifth book, 2026-11-17 21:19 to 2026-11-17 21:57 UTC
   bot new bids: 0
   wrong against the research (other side, or more than 5 bp from the level): 0 of 0
   the research's new bids in the window: 8; with a bot bid within a minute: 0; stale_input_t true on 8
     research 11-17 21:39 DOGE  score 40.0985 bot_arm_pm1 False stale_t True
     research 11-17 21:39 PEPE  score 30.715 bot_arm_pm1 False stale_t True
     research 11-17 21:42 PEPE  score 30.7181 bot_arm_pm1 False stale_t True
     research 11-17 21:44 HBAR  score 41.8904 bot_arm_pm1 False stale_t True
     research 11-17 21:45 DOGE  score 34.9861 bot_arm_pm1 False stale_t True
     research 11-17 21:47 HBAR  score 34.7078 bot_arm_pm1 False stale_t True
     research 11-17 21:49 DOGE  score 38.327 bot_arm_pm1 False stale_t True
     research 11-17 21:50 PEPE  score 33.0995 bot_arm_pm1 False stale_t True
   stale-guard minutes in the window: 38; fills in the window: 0 []
VETO RULE: the fourth book's bids in the window: 8; wrong: 0; the fallback is NOT vetoed
```
