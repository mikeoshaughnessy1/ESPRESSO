# Validation

## Power BI vs. app
Checked Nov 9 2026 against our own file (`POWER_BI-MOS.pbix`). We read the model's tables with pbixray and summed them. The Sales table in the .pbix is the same 25,200 rows as `data/Sales.csv`, with every revenue value identical.

Known discrepancy, now confirmed in the model's relationships: Sales[Store ID] is joined to Survey Results[Survey ID] ("SH01" vs "SH01_25"), and Survey Results joins to E-Presso Stores. Those keys never match, so a Power BI visual that splits revenue by a Stores field (StoreType, City, Market) can't be trusted. The app joins Sales to Stores directly on Store ID. The channel figures below come from the .pbix data joined the right way.

## Table (use the app's Validation tab, which ignores sidebar filters)
| Metric | Power BI result | App result | Match? / Explanation |
|---|---|---|---|
| Total revenue (five years) | $42,174,440 | $42,174,440.00 | Match |
| Website revenue | $27,218,880 (Store ID join) | $27,218,880.00 (64.54%) | Match. A StoreType visual in our report would not show this, because of the bad relationship above |
| Brick-and-mortar revenue | $14,955,560 (Store ID join) | $14,955,560.00 (35.46%) | Match, same note |
| Revenue by year | 2025 $7,181,750; 2026 $8,016,950; 2027 $8,824,720; 2028 $8,969,470; 2029 $9,181,550 | 2025 $7,181,750; 2026 $8,016,950; 2027 $8,824,720; 2028 $8,969,470; 2029 $9,181,550 | Match, all five years |
| Monthly revenue pattern | December 25.61%, November 12.71%, February 3.83% | December is 25.61% of 5-year revenue, November 12.71%, February lowest at 3.83% | Match |
| Additional measure: Beans revenue | $5,672,720 | $5,672,720 (Category = Beans) | Match |

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
