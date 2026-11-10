# Agent tests

Option A: the live app uses Gemini (`gemini-3.1-flash-lite`) function calling. All five tests below were run on the live app on Nov 6 2026 with the tool-call log open. Rules-based results are in a separate table further down.
Test 5 ran live on Nov 9 2026 in Gemini mode. Tool-call screenshots: `k03-before-toolcall.jpg`, `k11-after-toolcall.jpg`.
Gemini tool-call screenshots for tests 1 and 2 (Nov 9): `g01`/`g02` (Test 1), `g03`/`g04` (Test 2).

| Test | Question asked | Function(s) used | Expected result / behavior | Actual result | Pass / Fail | Revision made |
|---|---|---|---|---|---|---|
| 1. Numerical calculation | How much revenue did the website generate in 2028? | get_total_revenue (channel=Website, year=2028) | $6,339,640 (independent pandas check) | $6,339,640; scope "channel = Website, year = 2028"; said revenue is not profit | Pass | None |
| 2. Numerical comparison | Which store experienced the greatest percentage revenue decline? | get_growth (group=store) | Names the store with the biggest % drop, 2025 vs 2029. If no store declined, says so. | SH11 Chicago, IL, -66.81% (2025 vs 2029); said it doesn't explain why. The "no store declined" case does not occur in this data; it is covered by pytest `test_no_store_declined_says_so_in_the_answer` (local, rules mode), and the Gemini prompt now tells the model to say it. | Pass | See Extra: fix and retest |
| 3. Missing information | Which E-Presso store is the most profitable? | get_revenue_by (group=store) | Says profit can't be calculated from revenue alone; shows revenue and labels it | Said profit can't be determined without costs; listed top revenue stores as revenue only | Pass | Display fix, see Extra 2 below |
| 4. Analytical judgment | Does higher customer satisfaction cause higher revenue? | get_satisfaction_vs_revenue | Gives the correlation, says correlation is not causation, notes the website has no scores | r = 0.235 over 100 store-years, weak positive, correlation is not causation, store size/market could drive both | Pass | None |
| 5. Updated data | How much revenue did the website generate in 2025? (before and after the $1,000 upload) | get_total_revenue (channel=Website, year=2025) | $3,160,230 before, $3,161,230 after, no code change | $3,160,230 before upload, $3,161,230 after, $3,160,230 after restoring | Pass | None |
| Extra: fix and retest | Same as Test 2 | get_growth | Growth question with the word "percentage" should go to the growth tool | Before: the new "percent/share" rule ran before the growth rule, so it showed shares. After: growth wording takes priority. Retested live: correct. Regression test `test_assignment_test2_wording_routes_to_growth` added. | Fail, then Pass | agent.py rules_router, commit "Fix: 'percentage revenue decline'..." |

Tool-call log screenshots in `docs/screenshots/`: Test 1 `agent-test1-gemini.png`, Test 2 `agent-test2-gemini.png`, Test 3 `agent-test3-gemini.png`, Test 4 `agent-test4-gemini.png`, Test 5 `agent-test5-before.png`, `-after`, `-restored`. Also `agent-filtered-scope.png`, `agent-unsupported-before-fix.png`, and earlier `test2-live-after-fix.jpg` (rules mode), `test3-gemini-live.jpg`.

TODO after the next push: rerun the five tests on the live app and retake the screenshots. The scope wording changed (for example "2028, Website (filtered subset, from the question)"), so the quotes above are from the earlier version.

## Other live Gemini checks
| Test | Function the model called | Answer | Pass |
|---|---|---|---|
| Filtered scope | get_total_revenue (year=2027), with the sidebar Year filter on 2027 | "What was total revenue?" gave $8,824,720; scope line "year = 2027 (includes sidebar filters)" | Pass |
| Unsupported | none | "What will the weather be in Chicago tomorrow?" said it has no weather data, 0 tool calls | Fail, then fixed (see Extra 3) |

## Rules-based mode results (live, Nov 5 2026)
Rules mode runs when no key is set or the API fails.

| Test | Question asked | Function(s) used | Expected result / behavior | Actual result | Pass / Fail | Revision made |
|---|---|---|---|---|---|---|
| 1. Numerical calculation | How much revenue did the website generate in 2028? | get_total_revenue, filters year=2028, channel=Website | $6,339,640.00 (independent pandas check) | $6,339,640.00, scope "year = 2028, channel = Website", 240 rows | Pass | — |
| 2. Numerical comparison | Which store experienced the greatest percentage revenue decline? | get_growth, group=store | Names the store with the biggest % drop, 2025 vs 2029. If none declined, says so. | First live run: returned revenue shares by store (wrong tool). After fix: "Largest decline: SH11 Chicago, IL (-66.81%)" | Fail, then Pass | See "Fix and retest" row |
| 3. Missing information | Which E-Presso store is the most profitable? | get_revenue_by, group=store | Says profit can't be calculated from revenue alone; shows revenue instead and labels it | "The data has revenue only, no costs, so profit cannot be calculated. Revenue is shown instead." | Pass | — |
| 4. Analytical judgment | Does higher customer satisfaction cause higher revenue? | get_satisfaction_vs_revenue | Gives the correlation from real data, says correlation is not causation, notes website has no survey scores | r = 0.235 across 100 store-years; says the data shows association, not cause; 5 website store-years excluded | Pass | — |
| 5. Updated data | How much revenue did the website generate in 2025? (before and after the $1,000 upload) | get_total_revenue, filters year=2025, channel=Website | $3,160,230 before, $3,161,230 after, no code change | Live, Gemini: $3,160,230 -> $3,161,230 -> $3,160,230 after restore. Rules mode, local: same before and after. | Pass | — |
| Extra 2: Gemini display fix | Which E-Presso store is the most profitable? (Gemini) | — | Dollar amounts readable; one "Findings:" label | Before: "Findings: Findings:" and the two $ amounts rendered as a garbled math formula. After escaping $ outside code blocks and letting the model write its own labels: clean. | Fail, then Pass | streamlit_app.py answer display, commit "Fix answer display..." |
| Extra 3: unsupported question | What will the weather be in Chicago tomorrow? (Gemini) | none | Says what the assistant can answer (guide section 7); Method panel is clean | Before: the reply only said it had no weather data, and the Method panel showed "Json Parse Error" because a sentence was passed to st.json. After: reply lists what it can calculate; panel says "No tool was called." Passed in pytest and an AppTest walkthrough. TODO: retest live after pushing. | Fail, then Pass (local) | agent.py, streamlit_app.py, regression test `test_llm_answer_with_no_tool_call_says_what_it_can_answer` |

## Fixes found in the audit (local, pytest and AppTest; not yet on the live app)
Each has a regression test in `tests/test_analytics.py`. TODO: retest live after pushing.

| Question or data | Before | After |
|---|---|---|
| "Which sales channel grew most?" (rules) | Revenue shares, because "grew" was not a growth word | get_growth by channel |
| "What was online revenue in 2027?" (rules) | Whole-company 2027 total | Website 2027 |
| "What was revenue in December 2027?" (rules) | All of 2027 | December 2027 |
| "What was revenue in 2024?", "...in Boston?" (rules) | Whole-company total, a silent guess | Error result listing valid values |
| Partial last year | Fake large decline with a warning | Only months in both years are compared |
| Missing column (Store ID in Stores, Product ID in Sales, and others) | Python error | Plain message naming the column |
| Sales CSV saved by Excel as "CSV UTF-8" | First column name hidden by a byte marker | Reads normally |
| Gemini reply without a "Findings:" label (code review, Nov 10) | Page showed only the two fallback lines; the model's answer disappeared | Text is kept as Findings |
| "Revenue from Online sales in 2027", "Revenue in Jan 2027" (rules) | "Online" / "Jan" treated as an unknown store, error result | Website 2027 / January 2027 |
| "Should we close the Chicago store before 2030?" (rules) | Year 2030 sent to the tool, "not found", no evidence | Same evidence as "Should we close the Chicago store?" |
| "What is the latest update on 2027 sales?" (rules) | Refused as a request to change data | Answered |
| Model writes "$7.18 million" or rounds 2.675 to 2.68 | Flagged "do not rely on" | Not flagged; made-up numbers still are |
| Sidebar filters that are valid but match no rows | Red error, page stops | Plain warning saying to change a filter |

## Other fixes found by testing (before the five tests)
- "SH11 Chicago revenue in 2029" ignored the store and returned the whole company's 2029 total. Store names are labels like "SH11 Chicago, IL", so plain text matching missed them. Fixed by matching store ID or city.
- "Website revenue in 2027" returned a breakdown by channel instead of one number. A named channel value is now a filter, not a group-by.
- "How did Orlando do?" matched nothing because Orlando has two stores. Now both are shown.
- A partial last year (one month of 2030) produced a fake -99% growth. Growth now warns when the first and last years have different numbers of months.
