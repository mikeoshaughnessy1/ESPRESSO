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
- `config.py`: every file and column name. `data_prep.py`: joins with `check_merge`. `analytics.py`: the math. `agent.py`: tools, dispatcher, rules router, Gemini router. `streamlit_app.py`: layout. `theme.py`: green look.
- `data/`: original E-Presso data (Sales/Products/Categories exported from the Access db inside our .pbix; Stores CSV is tab-delimited; Survey has headers on row 3).
- `docs/`: grain and merges, validation, $1,000 test, agent tests, defense study guide, reflection template.

## Facts to check against (validation only, never put in app code)
Total $42,174,440. Website $27,218,880. Brick & Mortar $14,955,560. By year: 2025 7,181,750; 2026 8,016,950; 2027 8,824,720; 2028 8,969,470; 2029 9,181,550.

## Status (update after each session)
- Done: deployed app, real joins, 6 charts, filters, 6 tools, rules assistant, Gemini live with key in Streamlit Secrets (gemini-3.1-flash-lite), 26 tests, agent tests 1-4 passed live in both modes, two fix-and-retests documented.
- To do: Test 5 and the $1,000 test on the live app with screenshots; confirm Power BI numbers from our own report; reflection (our words); contribution table; teammate commits.
