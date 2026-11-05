# E-Presso BI Analyst (starter)

> Replace this README as you build. Your final version should cover every section below.

## What this application does
A revenue dashboard for E-Presso managers. Upload the five E-Presso files and it shows total revenue, website vs. brick-and-mortar, yearly and monthly trends, and store and category performance, all recalculated from whatever files are uploaded. An assistant answers business questions by running approved calculations and showing its work.

## Live app
_URL here. Note that the app may take a moment to wake up._

## How to use it
The app loads the original data from `data/` when it opens. To test changed data, upload a file in the sidebar; it replaces only that table. The sidebar shows where each table came from and the Sales revenue sum. Expected files: `EPresso_Sales.csv`, `EPresso_Products.csv`, `EPresso_Categories.csv` (the three Access tables exported to CSV), `Support_EX_B_Stores.csv`, and `Support_EX_B_Survey.xlsx` (sheet "Survey Results"). Files are recognized by the words sales, product, categor, store, and survey in their names. Then use the filters or ask the assistant.

## Data model
See `docs/grain_and_merges.md`. Sales is one store x product x month. Products, Categories, and Stores join many-to-one; every merge is checked for row and revenue changes. The survey is store x year, so sales are summed to that level before comparing.

## Metric definitions
Revenue = sum of the Sales table Revenue column. Channel comes from Stores.StoreType. Revenue is not profit; there is no cost data.

## Assistant
_State exactly what you built (live language-model agent, or rules-based assistant). List each tool, what it calculates, and what the assistant is not allowed to do._

## Validation
_Link to or summarize your Power BI comparison, independent check, and $1,000 test._

## Limitations
_Revenue is not profit. What else can this app not tell a manager?_

## Files
| File | Purpose |
|---|---|
| `streamlit_app.py` | Screen layout and interaction |
| `analytics.py` | Metrics and analytical functions (no Streamlit code) |
| `config.py` | Every file and column name the app depends on |
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
