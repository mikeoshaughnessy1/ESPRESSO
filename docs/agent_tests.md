# Agent tests

Tests 1-4 were run on the live app twice on Nov 5 2026: first in rules-based mode (no key), then with Gemini (`gemini-3.1-flash-lite`, function calling) after adding the API key. Both modes passed tests 1-4.
Screenshots: `docs/screenshots/test2-live-after-fix.jpg` (rules mode, tool log), `docs/screenshots/test3-gemini-live.jpg` (Gemini).
Test 5 ran live on Nov 9 2026 in Gemini mode. Tool-call screenshots: `k03-before-toolcall.jpg`, `k11-after-toolcall.jpg`.
TODO for us: screenshot the Gemini tool-call log for tests 1 and 2.

## Gemini mode results (live)
| Test | Function the model called | Answer | Pass |
|---|---|---|---|
| 1 | get_total_revenue (channel=Website, year=2028) | $6,339,640; scope "channel = Website, year = 2028"; said revenue is not profit | Pass |
| 2 | get_growth (group=store) | SH11 Chicago, IL, -66.81% (2025 vs 2029); said it doesn't explain why | Pass |
| 3 | get_revenue_by (group=store) | Said profit can't be determined without costs; listed top revenue stores as revenue only | Pass |
| 4 | get_satisfaction_vs_revenue | r = 0.235 over 100 store-years, weak positive, correlation is not causation, store size/market could drive both | Pass |
| 5 | get_total_revenue (year=2025, channel=Website), 240 rows | $3,160,230 before the $1,000 upload, $3,161,230 after, no code change (screenshots k02, k03, k10, k11) | Pass |

## Rules-based mode results (live)

| Test | Question asked | Function(s) used | Expected result / behavior | Actual result | Pass / Fail | Revision made |
|---|---|---|---|---|---|---|
| 1. Numerical calculation | How much revenue did the website generate in 2028? | get_total_revenue, filters year=2028, channel=Website | $6,339,640.00 (independent pandas check) | $6,339,640.00, scope "year = 2028, channel = Website", 240 rows | Pass | — |
| 2. Numerical comparison | Which store experienced the greatest percentage revenue decline? | get_growth, group=store | Names the store with the biggest % drop, 2025 vs 2029. If none declined, says so. | First live run: returned revenue shares by store (wrong tool). After fix: "Largest decline: SH11 Chicago, IL (-66.81%)" | Fail, then Pass | See "Fix and retest" row |
| 3. Missing information | Which E-Presso store is the most profitable? | get_revenue_by, group=store | Says profit can't be calculated from revenue alone; shows revenue instead and labels it | "The data has revenue only, no costs, so profit cannot be calculated. Revenue is shown instead." | Pass | — |
| 4. Analytical judgment | Does higher customer satisfaction cause higher revenue? | get_satisfaction_vs_revenue | Gives the correlation from real data, says correlation is not causation, notes website has no survey scores | r = 0.235 across 100 store-years; says the data shows association, not cause; 5 website store-years excluded | Pass | — |
| 5. Updated data | Website revenue in 2025, before and after the $1,000 upload | get_total_revenue, filters year=2025, channel=Website | $3,160,230.00 before, $3,161,230.00 after, no code change | Local test: $3,160,230.00 -> $3,161,230.00. Live run (Gemini mode, Nov 9): same numbers, see Gemini table | Pass | — |
| Extra 2: Gemini display fix | Which E-Presso store is the most profitable? (Gemini) | — | Dollar amounts readable; one "Findings:" label | Before: "Findings: Findings:" and the two $ amounts rendered as a garbled math formula. After escaping $ outside code blocks and letting the model write its own labels: clean. | Fail, then Pass | streamlit_app.py answer display, commit "Fix answer display..." |
| Extra: fix and retest | Same as Test 2 | get_growth | Growth question with the word "percentage" should go to the growth tool | Before: the new "percent/share" rule ran before the growth rule, so it showed shares. After: growth wording takes priority. Retested live: correct. Regression test `test_assignment_test2_wording_routes_to_growth` added. | Fail, then Pass | agent.py rules_router, commit "Fix: 'percentage revenue decline'..." |

## Other fixes found by testing (before the five tests)
- "SH11 Chicago revenue in 2029" ignored the store and returned the whole company's 2029 total. Store names are labels like "SH11 Chicago, IL", so plain text matching missed them. Fixed by matching store ID or city.
- "Website revenue in 2027" returned a breakdown by channel instead of one number. A named channel value is now a filter, not a group-by.
- "How did Orlando do?" matched nothing because Orlando has two stores. Now both are shown.
- A partial last year (one month of 2030) produced a fake -99% growth. Growth now warns when the first and last years have different numbers of months.
