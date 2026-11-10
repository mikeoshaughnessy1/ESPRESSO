# $1,000 modified-data test

## Step 1. Predictions (written BEFORE uploading)

Row chosen: Sales table, Sales ID S0020250101. Date 2025-01-31, store SH00 (Website), channel Website, category Beans, product French Roast.
Original Revenue 6,780. Modified Revenue 7,780 (+1,000). No other cell changes.

| What | Before | Predicted after | Why |
|---|---|---|---|
| Total revenue (no filters) | $42,174,440.00 | $42,175,440.00 | the row is in every total |
| Year = 2025 | $7,181,750.00 | $7,182,750.00 | row is in 2025 |
| Channel = Website | $27,218,880.00 | $27,219,880.00 | row is a website sale |
| Channel = Brick & Mortar | $14,955,560.00 | $14,955,560.00 (no change) | row is not B&M |
| Category = Beans | $5,672,720.00 | $5,673,720.00 | row is Beans |
| Year = 2026 to 2029 | unchanged | unchanged | row is 2025 only |
| Website 2025 (assistant Test 5) | $3,160,230.00 | $3,161,230.00 | |
| Revenue by year chart | 2025 bar $7,181,750 | 2025 bar +$1,000, other bars same | |
| Monthly share chart | January 7.74% | January up a hair, other months down a hair (shares still add to 100%) | the denominator grows by $1,000 too |
| Website share KPI | 64.54% | about 64.54% (moves in the 4th decimal) | $1,000 out of $42M is tiny |
| Sidebar "Loaded from" | Sales: original (data/), revenue sum $42,174,440.00 | Sales: uploaded, revenue sum $42,175,440.00 | proves the right file loaded |

What should not change: Brick & Mortar revenue, years 2026 to 2029, every other category, and every other store. The assistant gets the same question before and after: "How much revenue did the website generate in 2025?"

## Step 2. Results on the live app (Nov 6 2026, no code edits, no restart)

| Item | Entry |
|---|---|
| Table and row identifier | Sales, S0020250101 |
| Date / store / channel of the row | 2025-01-31 / SH00 Website / Website |
| Original value | 6,780 |
| Modified value | 7,780 |
| Expected total revenue after change | $42,175,440.00 |
| Actual total revenue after change | $42,175,440 (k04). Banner says "Uploaded data in use", sidebar shows Sales: uploaded, data version changed e06d3923 to 15ee6dbb |
| Chart that should change, and what you saw | Revenue by year: 2025 bar total went from $7,181,750 to $7,182,750. Other years unchanged (k05, k06). Fig. 01, Website 2025 segment: 3,160,230 -> 3,161,230 in the chart's own data. All 9 other points unchanged. The on-screen label rounds to $7.18M both times, so the exact change is shown in the Validation tables (2025 $7,182,750; Jan 2025 $549,340, up from $548,340). |
| Filter combinations checked (changed / unchanged) | Changed: Year 2025 $7,182,750 (k05), Website $27,219,880 (k08), Beans $5,673,720 (k09), Website 2025 $3,161,230 (k05 table). Unchanged: Year 2026 $8,016,950 (k06), Brick & Mortar $14,955,560 (k07) |
| Assistant answer before / after | Gemini mode, "How much revenue did the website generate in 2025?": $3,160,230 before (k02, k03), $3,161,230 after (k10, k11). Same tool call both times: get_total_revenue, year=2025, channel=Website, 240 rows |
| Code changes required? | None. Same deployed commit before and after |
| Original data restored? | Yes. Removed the upload: "Original data restored", sidebar back to Sales: original, $42,174,440, version e06d3923 (k12, k13) |

Run on the live app Nov 9 2026. Every prediction in Step 1 matched. Screenshots are `docs/screenshots/k01` to `k13`, in order.
For this run the modified file was built in the browser from the repo's `data/Sales.csv` with only row S0020250101 changed (6780.0 to 7780.0), then dropped into the "Replace data" uploader as `Sales.csv`. Same result as the Excel method below.

Every prediction in Step 1 held. A line-by-line comparison of the Validation page before and after shows only the total, Website, 2025, and Jan 2025 figures changed. The modified file differs from the original on one line (`diff`), and that line is the Revenue value.

Screenshots in `docs/screenshots/`: `thousand-1` to `thousand-3` (before), `thousand-4` to `thousand-6` (after), `thousand-7` (restored), and `agent-test5-before`, `-after`, `-restored`.

## How to make the modified file
1. Download `data/Sales.csv` from GitHub (open it, then the download button).
2. Open in Excel. Row 2, Revenue column: change 6780 to 7780. Save as CSV, keep the name `Sales.csv`, in a different folder (e.g. Desktop/modified).
3. Upload that file in the app's sidebar under "Replace data".
