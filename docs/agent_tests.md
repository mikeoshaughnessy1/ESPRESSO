# Agent tests
Attach a screenshot of the tool-call log for tests 1, 2, and 5.

| Test | Question asked | Function(s) used | Expected result / behavior | Actual result | Pass / Fail | Revision made |
|---|---|---|---|---|---|---|
| 1. Numerical calculation | How much revenue did the website generate in 2028? | get_total_revenue | | | | |
| 2. Numerical comparison | Which store had the greatest percentage revenue decline? | get_growth | If none declined, says so | | | |
| 3. Missing information | Which store is the most profitable? | | Says profit can't be calculated from revenue | | | |
| 4. Analytical judgment | Does higher customer satisfaction cause higher revenue? | | Association, not causation | | | |
| 5. Updated data | (repeat test 1 after the $1,000 upload) | get_total_revenue | Answer reflects new total | | | |
| Extra: fix and retest | "Website revenue in 2027" | get_total_revenue | One website total | Before fix: returned a breakdown by channel | Fail, then Pass | Router now treats a named channel value as a filter, not a group-by |
