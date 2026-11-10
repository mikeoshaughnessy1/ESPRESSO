# Defense study guide

Read this, then open the code and find each thing it mentions. Your professor will ask you to explain it in your own words, so practice saying the answers out loud.

## How the app works, start to finish

1. **Load.** `streamlit_app.py` reads the five files in `data/`. If you upload a file in the sidebar, it replaces just that one table. Files are recognized by name (sales, product, categor, store, survey). That's set in `config.py`.
2. **Rename.** `config.py` maps the real column names (like `Store ID`) to the names the code uses (`store_id`). If the professor's modified data keeps the same column names, nothing in the code has to change.
3. **Join.** `data_prep.py` starts with Sales and adds Categories, Products, and Stores with left joins. Every join goes through `check_merge()`, which records the row count and revenue sum before and after. If either changes, the join duplicated or dropped something.
4. **Calculate.** `analytics.py` has the math. Every function takes the data plus explicit filters and returns the same "tool contract": value, definition, scope, rows used, and caveats.
5. **Show.** The Overview calls those same functions (Fig. 3 and the Validation month table group the same loaded rows directly). So does the assistant. One set of math, used everywhere.
6. **Ask.** `agent.py` picks which function to run (Gemini function calling on the live app, keyword rules if the API fails or no key is set), runs it, logs the call, and writes the answer as Findings / Interpretation / Next steps.

## Key decisions you should be able to defend

- **Grain of Sales is one store × one product × one month.** 21 stores × 20 products × 60 months = 25,200 rows exactly. That's how we know nothing is missing or duplicated.
- **Channel comes from Stores.StoreType.** SH00 is the website, and the other 20 stores are brick & mortar.
- **The survey is NOT joined to the monthly sales rows.** The survey is one row per store per year. Joining it to monthly rows would copy each score 240 times (12 months × 20 products). For the satisfaction question, we add up revenue to store × year first, then join. Same grain on both sides.
- **Store labels are "SH01 Orlando, FL", not just the city.** Two stores are in Orlando. Grouping by city would merge them.
- **"Base Model" gets its category added.** Three different products share that name (a machine, a grinder, a frother).
- **Our Power BI model had a broken join:** Sales[Store ID] to Survey[Survey ID]. "SH01" never equals "SH01_25". The right key is Sales[StoreYear]. In the app we join Sales to Stores directly on Store ID.
- **Filters come from the data.** The year, store, channel, and category lists are built from whatever is loaded, never typed in. A new year in the modified data shows up on its own.
- **The cache is keyed on file contents.** That's why uploading a changed file shows new numbers without a restart (the #1 reason teams fail the $1,000 test).

## Questions he might ask, with short answers

**Where is total revenue calculated?** `analytics.get_total_revenue`. It sums the Revenue column after applying the filters. Nothing is hardcoded.

**How do you know your joins didn't duplicate revenue?** The merge-check table on the Data & quality page. Every lookup join kept 25,200 rows and $42,174,440 before and after, and the survey check kept 105 store-years and the same total. Products, Categories, and Stores each have one row per key, so the joins are many-to-one.

**What does "grain" mean?** What one row stands for. Sales = one store, one product, one month. Stores = one store. Survey = one store, one year.

**What happens if I upload data with a new store that isn't in the Stores file?** Revenue still counts in the total. The app names the store ID that wasn't found, and the Overview says how many dollars have no channel, so the total and the channel figures can be reconciled.

**Why is monthly share different with a filter on?** The denominator is all revenue in scope. Filter to Chicago and December becomes a share of Chicago's revenue, not the company's.

**Can the assistant make up a number?** It can only pick from six named functions with allowed parameters, and our code runs them on the loaded data. No eval, no exec, no model-written pandas or SQL. The model still writes the sentences, so we cannot promise it never misstates a number. That is why `agent.untraced_numbers` checks every number in the reply against the tool results and shows a warning for any it can't find, and the tool-call log under each answer shows the function, the arguments, and the raw result.

**What if the last year is only partly loaded?** Growth compares only the months found in both the first and last year, and says so. One January in 2030 can't look like a 90% collapse.

**What if Gemini is down or out of quota?** It falls back to the rules-based assistant and says so at the top of the answer. There's also a 15-question limit per session.

**Is satisfaction driving revenue?** We can't say. r = 0.235 across 100 store-years is a weak positive association. Big stores in big markets could have both higher revenue and different satisfaction. Correlation is not causation, and the website has no survey scores.

**Should E-Presso close Chicago?** Chicago revenue fell about 67% from 2025 to 2029, the biggest drop of any store. But revenue isn't profit. We'd need costs, lease terms, staffing, and whether those customers moved to the website before recommending that.

**What would you not trust this app for?** Anything about profit, forecasting, or cause and effect. It also trusts the source files. If a store is labeled wrong (Flushing, NY shows "Southwest"), the app shows it as given.

**What did AI do and what did you do?** Be honest. Claude wrote most of the code. We decided what to check, compared it to Power BI, ran the tests, caught the Test 2 routing bug on the live app, and chose how to handle the survey grain and the broken Power BI join.

## Run the tests yourself
```
pip install -r requirements-dev.txt
pytest
```
Tests use tiny made-up tables where you can check the answer by hand, plus a few that run the real page (see `tests/test_analytics.py`).
