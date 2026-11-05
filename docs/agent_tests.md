# Agent tests

Run on the live app (rules-based mode, no API key yet), Nov 5 2026.
Screenshot of a tool-call log: `docs/screenshots/test2-live-after-fix.jpg`.
TODO for us: re-run all five after adding the Gemini key, and screenshot the tool-call log for tests 1, 2, and 5.

| Test | Question asked | Function(s) used | Expected result / behavior | Actual result | Pass / Fail | Revision made |
|---|---|---|---|---|---|---|
| 1. Numerical calculation | How much revenue did the website generate in 2028? | get_total_revenue, filters year=2028, channel=Website | $6,339,640.00 (independent pandas check) | $6,339,640.00, scope "year = 2028, channel = Website", 240 rows | Pass | — |
| 2. Numerical comparison | Which store experienced the greatest percentage revenue decline? | get_growth, group=store | Names the store with the biggest % drop, 2025 vs 2029. If none declined, says so. | First live run: returned revenue shares by store (wrong tool). After fix: "Largest decline: SH11 Chicago, IL (-66.81%)" | Fail, then Pass | See "Fix and retest" row |
| 3. Missing information | Which E-Presso store is the most profitable? | get_revenue_by, group=store | Says profit can't be calculated from revenue alone; shows revenue instead and labels it | "The data has revenue only, no costs, so profit cannot be calculated. Revenue is shown instead." | Pass | — |
| 4. Analytical judgment | Does higher customer satisfaction cause higher revenue? | get_satisfaction_vs_revenue | Gives the correlation from real data, says correlation is not causation, notes website has no survey scores | r = 0.235 across 100 store-years; says the data shows association, not cause; 5 website store-years excluded | Pass | — |
| 5. Updated data | Website revenue in 2025, before and after the $1,000 upload | get_total_revenue, filters year=2025, channel=Website | $3,160,230.00 before, $3,161,230.00 after, no code change | Local test: $3,160,230.00 -> $3,161,230.00. TODO: repeat on live app with screenshots | Pass (local) | — |
| Extra: fix and retest | Same as Test 2 | get_growth | Growth question with the word "percentage" should go to the growth tool | Before: the new "percent/share" rule ran before the growth rule, so it showed shares. After: growth wording takes priority. Retested live: correct. Regression test `test_assignment_test2_wording_routes_to_growth` added. | Fail, then Pass | agent.py rules_router, commit "Fix: 'percentage revenue decline'..." |

## Other fixes found by testing (before the five tests)
- "SH11 Chicago revenue in 2029" ignored the store and returned the whole company's 2029 total. Store names are labels like "SH11 Chicago, IL", so plain text matching missed them. Fixed by matching store ID or city.
- "Website revenue in 2027" returned a breakdown by channel instead of one number. A named channel value is now a filter, not a group-by.
- "How did Orlando do?" matched nothing because Orlando has two stores. Now both are shown.
- A partial last year (one month of 2030) produced a fake -99% growth. Growth now warns when the first and last years have different numbers of months.
