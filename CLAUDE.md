# ESPRESSO: E-Presso BI app (MSU BMGT 535, "ADS midterm")

Team project for the AI Business Intelligence Challenge. Due Sun Nov 15, 2026, 11:59 pm.
Live app: https://mikeoshaughnessy1-espresso-streamlit-app-svrb7p.streamlit.app/
Repo: https://github.com/mikeoshaughnessy1/ESPRESSO (branch main; pushing redeploys the app)

## How to work with us
- Explain what you're about to change and why, in plain English. We have to defend this code in an oral check.
- Small changes, one at a time. Run `pytest` after every change.
- Show the commit before committing. Don't push unless asked.
- Each teammate commits from their own GitHub account (it's graded).

## Hard rules from the assignment (the Project Guide wins over the assignment page)
- Never hardcode totals, chart values, filter lists, or expected answers. Calculate from loaded data.
- The assistant may only call the named functions in `agent.TOOLS`. No eval/exec, no model-written pandas or SQL, no LangChain pandas agent or PandasAI, no function that changes data.
- Every tool returns the tool contract (`analytics.ToolResult`): value, definition, scope, rows_used, caveats.
- Answers start with Scope and are split into Findings / Interpretation / Next steps.
- API keys only in Streamlit Secrets (`GEMINI_API_KEY`, optional `GEMINI_MODEL`). Never in the repo or chat.
- Cache must stay keyed on file contents (the $1,000 test depends on it).

## Files
- `config.py`: every file and column name. `data_prep.py`: joins with `check_merge`. `analytics.py`: the math. `agent.py`: tools, dispatcher, rules router, Gemini router. `streamlit_app.py`: layout (left-rail nav, 4 sections). `theme.py`: design system (tokens, CSS, chart template, HTML blocks; looks only, no math).
- `data/`: original E-Presso data (Sales/Products/Categories exported from the Access db inside our .pbix; Stores CSV is tab-delimited; Survey has headers on row 3).
- `docs/`: grain and merges, validation, $1,000 test, agent tests, defense study guide, reflection template.

## Facts to check against (validation only, never put in app code)
Total $42,174,440. Website $27,218,880. Brick & Mortar $14,955,560. By year: 2025 7,181,750; 2026 8,016,950; 2027 8,824,720; 2028 8,969,470; 2029 9,181,550.

## Status (update after each session)
- Done: deployed app, real joins, 6 charts, filters, 6 tools, Gemini live with key in Streamlit Secrets (gemini-3.1-flash-lite) and a rules fallback. Agent tests 1-5 and the $1,000 test passed live (Nov 6, and again Nov 9: screenshots k01-k13, g01-g04). Power BI figures confirmed from our .pbix model (docs/validation.md). Audit and code-review fixes pushed Nov 10 (see "Fixes found in the audit" in docs/agent_tests.md); run `pytest` for the current test count.
- To do: on the live app, confirm answers show Language model mode, then spot-check tests 1-5 after the Nov 10 push; screenshot our own Power BI visuals, including the StoreType chart; reflection (our words); contribution table; teammate commits.
