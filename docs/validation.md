# Validation

## Power BI vs. app
Checked Nov 9 2026 against our own file (`POWER_BI-MOS.pbix`). We read the model's tables with pbixray and summed them. The Sales table in the .pbix is the same 25,200 rows as `data/Sales.csv`, with every revenue value identical.

Known discrepancy, now confirmed in the model's relationships: Sales[Store ID] is joined to Survey Results[Survey ID] ("SH01" vs "SH01_25"), and Survey Results joins to E-Presso Stores. Those keys never match, so a Power BI visual that splits revenue by a Stores field (StoreType, City, Market) can't be trusted. The app joins Sales to Stores directly on Store ID. The channel figures below come from the .pbix data joined the right way.

## Table (use the app's Validation tab, which ignores sidebar filters)
| Metric | Power BI result | App result | Match? / Explanation |
|---|---|---|---|
| Total revenue (five years) | $42,174,440 (from the .pbix model) | $42,174,440 | Match |
| Website revenue | $27,218,880 (from the .pbix model: Sales rows with Store ID SH00) | $27,218,880 (64.54%) | Match on the model data. See the discrepancy below: our report's StoreType chart cannot show this split. |
| Brick-and-mortar revenue | $14,955,560 (from the .pbix model: all other Store IDs) | $14,955,560 (35.46%) | Match on the model data. Same discrepancy. |
| Revenue by year | From the .pbix model: 2025 $7,181,750; 2026 $8,016,950; 2027 $8,824,720; 2028 $8,969,470; 2029 $9,181,550 | Same | Match |
| Monthly revenue pattern | From the .pbix model: Jan $3,266,270; Feb $1,616,410; Mar $1,873,190; Apr $2,173,470; May $2,411,110; Jun $2,743,370; Jul $2,706,590; Aug $2,718,500; Sep $3,000,500; Oct $3,502,890; Nov $5,361,150; Dec $10,800,990 | December 25.61%, November 12.71%, February lowest at 3.83% of 5-year revenue | Match. Monthly totals are summed across all five years in both. |
| Additional measure (your choice) | Beans category revenue: $5,672,720 (from the .pbix model) | Beans category revenue: $5,672,720 | Match |

Notes on the table: the Power BI column is read from the data model inside our .pbix (Sales table, 25,200 rows, implicit Sum of Revenue; the model has no DAX measures). It is not read from report visuals. TODO: confirm each figure from a visual in our own report and add a screenshot.

## Independent check
**What we calculated:** total revenue, revenue by channel, revenue by year, and each month's share of five-year revenue.

**How:** `docs/independent_check.py` reads the raw Sales and Stores files with plain pandas and no app code.

**What we got** (run Nov 6 2026; same figures as the app):

- Total $42,174,440; 25,200 rows after the store join, sum unchanged
- Brick & Mortar $14,955,560; Website $27,218,880
- By year: same five figures as the table above
- Month shares: December 25.61%, November 12.71%, February 3.83%

## Discrepancy investigated: the Power BI store relationship
Our model joins Sales[Store ID] to Survey Results[Survey ID], then Survey Results[Store ID] to E-Presso Stores[ID]. Sales holds "SH01" and Survey ID holds "SH01_25". Checked in the .pbix: 0 Store ID values match a Survey ID, while all 105 Sales[StoreYear] values do.

Our report's bar chart groups Sum(Sales.Revenue) by E-Presso Stores City, Market, and StoreType, so it depends on that broken path. Sales rows find no match, so the chart should not be able to split revenue correctly.

Fixed Nov 10 2026 in Power BI on the web (our .pbix uploaded to My workspace, edited in the semantic model's Editing mode). The relationship now runs Sales[StoreYear] to Survey Results[Survey ID], many-to-one, single direction, active (p01 before, p02 the edit, p03 after). A DAX query, `EVALUATE SUMMARIZECOLUMNS('E-Presso Stores'[StoreType], "Revenue", SUM(Sales[Revenue]))`, returns Website 27,218,880 and Brick & Mortar 14,955,560, an exact match with the app (p04). The fix is in the online copy of the model. Our local .pbix file is unchanged.

The total, year, and month visuals use Sales fields only, so the broken relationship does not affect them. The scatter chart uses Survey ID, Sum of Satisfaction, and Sum of Revenue, so its revenue values depend on the same relationship and should be checked too.

The app joins Sales to Stores directly on Store ID, and joins survey data at store-year grain (see `grain_and_merges.md`).

## $1,000 modified-data test
Done on the live app. Full record with predictions: `thousand_dollar_test.md`.
