# E-Presso BI Analyst

MSU BMGT 535, AI Business Intelligence Challenge.

## What this application does
A revenue dashboard for E-Presso managers. It opens on the supplied E-Presso data with no login and shows total revenue, website vs. brick-and-mortar, yearly and monthly trends, and store and category performance. Everything recalculates from whatever data is loaded, including uploaded replacements. A live language-model assistant (Option A: Gemini function calling) answers business questions by choosing approved calculations and showing its work.

## Live app
https://mikeoshaughnessy1-espresso-streamlit-app-svrb7p.streamlit.app/ (it may take a moment to wake up)

## How to use it
The app loads the original data from `data/` when it opens. To test changed data, upload a file in the sidebar; it replaces only that table. The sidebar shows where each table came from and the Sales revenue sum. Expected files: `Sales.csv`, `Products.csv`, `Categories.csv` (the three Access tables exported to CSV), `Support_EX_B_Stores.csv`, and `Support_EX_B_Survey.xlsx` (sheet "Survey Results"). Files are recognized by the words sales, product, categor, store, and survey in their names. Then use the filters or ask the assistant.

Updated data needs no code change if column names stay the same. Rows, stores, products, categories, and years may change. Blanks and unreadable values are listed on the Data & quality page. A missing column gives a message naming it. Access files (.accdb) cannot be uploaded; export the table to CSV first.

## Data model
See `docs/grain_and_merges.md` and the Table relationships section on the Data & quality page. Sales is one store x product x month. Products, Categories, and Stores join many-to-one; every merge is checked for row and revenue changes, because a repeated lookup key would duplicate revenue. The survey is store x year, so sales are summed to that level before comparing.

## Metric definitions
Revenue = sum of the Sales table Revenue column. Channel comes from Stores.StoreType. Revenue is not profit; there is no cost data. Share = group revenue / total revenue in scope with a known group. Monthly share of a year = month revenue / that year's revenue. Growth = (last year - first year) / first year, on the months found in both years.

## Assistant
Built as Option A. **Language model** (Google Gemini function calling, default `gemini-3.1-flash-lite`) runs when `GEMINI_API_KEY` is in Streamlit Secrets, as it is on the live app. The model only chooses a named function and parameters from a fixed list of allowed values; our code runs it. **Rules-based** keyword matching is the fallback when no key is set, the API fails, or the quota runs out. The app shows which mode answered.

API limits: the key is on Gemini's free tier, which caps requests per minute and per day. A question that calls a function uses two or more requests. Past the cap the app says so and answers in rules mode, which covers common phrasings only.

Tools (all in `analytics.py`, all return the tool contract):
| Tool | Calculates |
|---|---|
| get_total_revenue | total revenue for any filters (year, month, store, channel, category, product) |
| get_revenue_by | revenue and % share by channel, store, category, product, year, or month |
| get_growth | % change from first to last year per store, channel, category, or product; if the years cover different months, compares only months in both |
| get_monthly_share | each month's % of one year's revenue |
| get_satisfaction_vs_revenue | correlation of store-year satisfaction with store-year revenue |
| data_quality_report | duplicate rows, repeated Sales IDs, and missing values |

Not allowed: running model-written code (no eval/exec, no pandas agents), changing data, stating numbers that aren't in a tool result. In Gemini mode the prompt forbids it and the app also flags any number in the reply that no tool result contains. Each answer starts with its scope (full data or filtered subset, and whether the filter came from the sidebar or the question), then Findings / Interpretation / Next steps, then a tool-call log. Profit, causation, forecasting, and "should we close a store" questions get an explicit limitation. 15 questions per session, with a message and a locked chat box at the limit.

## Validation
See `docs/validation.md`, `docs/thousand_dollar_test.md`, and `docs/agent_tests.md`. Independent check: `python docs/independent_check.py`.

## Limitations
Revenue is not profit (no cost data). No forecasting. Correlation with satisfaction is not cause. The website has no survey scores, and missing survey responses limit any satisfaction conclusion. Growth compares only the first and last year. Rows with a blank group are left out of that group's figures and the amount is reported. Repeated Sales IDs are reported, not removed. Rules mode matches keywords, so unusual phrasing may get "I cannot answer that one". The app trusts the source files as given (e.g. Flushing, NY is labeled Southwest).

## Files
| File | Purpose |
|---|---|
| `streamlit_app.py` | Screen layout and interaction |
| `analytics.py` | Metrics and analytical functions (no Streamlit code) |
| `config.py` | Every file and column name the app depends on |
| `theme.py` | Design system: colors, type, chart template, page building blocks (looks only, no math) |
| `data_prep.py` | Joins the uploaded files, with merge checks |
| `docs/` | Grain, validation, agent tests, reflection |
| `agent.py` | Tool registry, dispatcher, and routers |
| `tests/` | Tests with hand-checkable answers |
| `requirements.txt` | Packages the hosted app needs |
| `requirements-dev.txt` | Adds pytest for local testing |
| `data/` | The original E-Presso data the app opens with |

## Run it
Hosted: deploy from this repository on share.streamlit.io with main file `streamlit_app.py`.

Locally (optional): `pip install -r requirements-dev.txt`, then `streamlit run streamlit_app.py`. Run tests with `pytest`.

## Secrets
Never commit API keys. Use Streamlit Secrets (see `.streamlit/secrets.toml.example`).
