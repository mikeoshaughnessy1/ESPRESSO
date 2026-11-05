# E-Presso BI Analyst (starter)

> Replace this README as you build. Your final version should cover every section below.

## What this application does
A revenue dashboard for E-Presso managers. Upload the five E-Presso files and it shows total revenue, website vs. brick-and-mortar, yearly and monthly trends, and store and category performance, all recalculated from whatever files are uploaded. An assistant answers business questions by running approved calculations and showing its work.

## Live app
https://mikeoshaughnessy1-espresso-streamlit-app-svrb7p.streamlit.app/ (it may take a moment to wake up)

## How to use it
The app loads the original data from `data/` when it opens. To test changed data, upload a file in the sidebar; it replaces only that table. The sidebar shows where each table came from and the Sales revenue sum. Expected files: `EPresso_Sales.csv`, `EPresso_Products.csv`, `EPresso_Categories.csv` (the three Access tables exported to CSV), `Support_EX_B_Stores.csv`, and `Support_EX_B_Survey.xlsx` (sheet "Survey Results"). Files are recognized by the words sales, product, categor, store, and survey in their names. Then use the filters or ask the assistant.

## Data model
See `docs/grain_and_merges.md`. Sales is one store x product x month. Products, Categories, and Stores join many-to-one; every merge is checked for row and revenue changes. The survey is store x year, so sales are summed to that level before comparing.

## Metric definitions
Revenue = sum of the Sales table Revenue column. Channel comes from Stores.StoreType. Revenue is not profit; there is no cost data.

## Assistant
Two routers share one dispatcher. **Rules-based** (keyword matching) runs when no API key is set. **Language model** (Google Gemini function calling, default `gemini-3.1-flash-lite`) runs when `GEMINI_API_KEY` is in Streamlit Secrets, and falls back to rules if the API fails or the quota runs out. The app shows which mode answered.

Tools (all in `analytics.py`, all return the tool contract):
| Tool | Calculates |
|---|---|
| get_total_revenue | total revenue for any filters (year, store, channel, category) |
| get_revenue_by | revenue and % share by channel, store, category, product, year, or month |
| get_growth | % change from first to last year per store, channel, or category; flags partial years |
| get_monthly_share | each month's % of one year's revenue |
| get_satisfaction_vs_revenue | correlation of store-year satisfaction with store-year revenue |
| data_quality_report | duplicates and missing values |

Not allowed: running model-written code (no eval/exec, no pandas agents), changing data, stating numbers that aren't in a tool result. Each answer shows its scope, a tool-call log, and Findings / Interpretation / Next steps. Profit, causation, forecasting, and "should we close a store" questions get an explicit limitation. 15 questions per session.

## Validation
See `docs/validation.md`, `docs/thousand_dollar_test.md`, and `docs/agent_tests.md`. Independent check: `python docs/independent_check.py`.

## Limitations
Revenue is not profit (no cost data). No forecasting. Correlation with satisfaction is not cause. The website has no survey scores. Growth compares only the first and last year. The app trusts the source files as given (e.g. Flushing, NY is labeled Southwest).

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

## Run it
Hosted: deploy from this repository on share.streamlit.io with main file `streamlit_app.py`.

Locally (optional): `pip install -r requirements-dev.txt`, then `streamlit run streamlit_app.py`. Run tests with `pytest`.

## Secrets
Never commit API keys. Use Streamlit Secrets (see `.streamlit/secrets.toml.example`).
