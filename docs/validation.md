# Validation

## Power BI vs. app
The Power BI column comes from the Sales table inside our .pbix (same 25,200 rows). Confirm each figure from a table visual in our own report and screenshot it.

Known discrepancy to explain: our Power BI model joined Sales[Store ID] to Survey Results[Survey ID] ("SH01" vs "SH01_25"). Those never match, so any Power BI visual that splits revenue by a Stores-table field (City, StoreType, Market) is not reliable. The app joins Sales to Stores directly on Store ID.

## Table (use the app's Validation tab, which ignores sidebar filters)
| Metric | Power BI result | App result | Match? / Explanation |
|---|---|---|---|
| Total revenue (five years) | $42,174,440.00 (confirm in our report) | $42,174,440.00 | |
| Website revenue | $27,218,880.00 (confirm) | $27,218,880.00 (64.54%) | |
| Brick-and-mortar revenue | $14,955,560.00 (confirm) | $14,955,560.00 (35.46%) | |
| Revenue by year | | 2025 $7,181,750; 2026 $8,016,950; 2027 $8,824,720; 2028 $8,969,470; 2029 $9,181,550 | |
| Monthly revenue pattern | | December is 25.61% of 5-year revenue, November 12.71%, February lowest at 3.83% | |
| Additional measure: | | | |

## Independent check
What we calculated, how (Excel pivot / script), and what we got:

`docs/independent_check.py` reads the raw Sales CSV with plain pandas (no app code) and gets the same total ($42,174,440), channel split, yearly, and monthly figures. Redo one of these in an Excel pivot table too, so one check is fully outside Python.

## $1,000 modified-data test
Write the predictions BEFORE uploading the modified file.

| Item | Entry |
|---|---|
| Table and row identifier | |
| Date / store / channel of the row | |
| Original value | |
| Modified value | |
| Expected total revenue after change | $42,175,440.00 |
| Actual total revenue after change | $42,175,440.00 in a local test (row S0020250101, SH00 Website, Jan 2025, $6,780 -> $7,780). Redo on the live app and screenshot. |
| Chart that should change, and what we saw | |
| Filter combinations checked (changed / unchanged) | |
| Assistant answer before / after | |
| Code changes required? | No |
| Original data restored? | |
