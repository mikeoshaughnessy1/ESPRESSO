# Grain statements and merge checks

## Grain
| Table | Source file / sheet | One row = | Key column(s) | Row count | Contains revenue? |
|---|---|---|---|---|---|
| Sales | Access `Support_EX_B_Sales.accdb`, table Sales (exported to EPresso_Sales.csv) | one store x one product x one month (month-end date) | Sales ID | 25,200 (21 stores x 20 products x 60 months) | Yes |
| Products | Access table Products (EPresso_Products.csv) | one product | Product ID | 20 | No |
| Categories | Access table Categories (EPresso_Categories.csv) | one category | Category ID | 5 | No |
| Stores | Support_EX_B_Stores.csv (tab-delimited) | one store; SH00 is the website | ID | 21 | No |
| Survey | Support_EX_B_Survey.xlsx, sheet "Survey Results" (headers on row 3) | one store x one year | Survey ID (e.g. SH01_25) | 105 | No |

## Merge checks (from the app's "Data and quality" tab)
| Merge | Rows before | Rows after | Revenue sum before | Revenue sum after | Explanation |
|---|---|---|---|---|---|
| sales + categories on Category ID | 25,200 | 25,200 | 42,174,440 | 42,174,440 | Many-to-one. Each category ID appears once. |
| sales + products on Product ID | 25,200 | 25,200 | 42,174,440 | 42,174,440 | Many-to-one. |
| sales + stores on Store ID = ID | 25,200 | 25,200 | 42,174,440 | 42,174,440 | Many-to-one. StoreType gives the channel. |
| sales (summed to store-year) + survey on StoreYear = Survey ID | 105 | 105 | 42,174,440 | 42,174,440 | Survey is store x year, so sales are summed to store x year first. Never joined to monthly rows. |

## Data issues found
- Product name "Base Model" is used by three different products (P11, P15, P19). The app labels them with their category.
- Two stores are in Orlando (SH01, SH08). Store labels use ID + city, never city alone.
- Survey sheet has two title rows above the header and years stored as text ("Y2025").
- The website (SH00) has no satisfaction or interest scores (5 survey rows blank).
- SH00 has blank City, State, and PostalCode. SH11's phone number is missing a parenthesis. SH07 (Flushing, NY) has Location = "Southwest".
- Our Power BI model joined Sales[Store ID] to Survey Results[Survey ID] ("SH01" vs "SH01_25"). Those keys never match. The correct key is Sales[StoreYear].
