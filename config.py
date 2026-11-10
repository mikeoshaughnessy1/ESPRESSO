"""Every file name and column name the app depends on lives HERE, and only here.

The guide says updated data keeps the same file names, sheet names, and column
names, so a modified dataset loads with no code changes.
"""

# Names the rest of the app uses. analytics.py only ever sees these.
DATE = 'date'
REVENUE = 'revenue'
STORE = 'store'            # label like "SH01 Orlando, FL" (two stores share Orlando)
CHANNEL = 'channel'        # from Stores.StoreType: Website or Brick & Mortar
CATEGORY = 'category'
PRODUCT = 'product'        # "Base Model" is 3 products, so labels add the category
YEAR = 'year'              # added by data_prep from DATE
MONTH = 'month'            # added by data_prep from DATE (1-12)
STORE_YEAR = 'store_year'  # e.g. SH01_25, links sales to the survey
SATISFACTION = 'satisfaction'
INTEREST = 'interest'

REQUIRED = [DATE, REVENUE, CHANNEL]

# One entry per source file. 'match' = text found in the uploaded file name
# (lower case). 'rename' maps the file's columns to the names above.
SOURCES = {
    'sales': {          # Access table Sales, exported to CSV
        'match': 'sales', 'sheet': 0, 'skiprows': 0,
        'rename': {'Sales ID': 'sales_id', 'Date': DATE, 'Store ID': 'store_id',
                   'StoreYear': STORE_YEAR, 'Category ID': 'category_id',
                   'Product ID': 'product_id', 'Revenue': REVENUE},
        'grain': 'one store x one product x one month (month-end date)',
        'key': 'sales_id',
    },
    'products': {       # Access table Products
        'match': 'product', 'sheet': 0, 'skiprows': 0,
        'rename': {'Product ID': 'product_id', 'Product': PRODUCT},
        'grain': 'one product', 'key': 'product_id',
    },
    'categories': {     # Access table Categories
        'match': 'categor', 'sheet': 0, 'skiprows': 0,
        'rename': {'Category ID': 'category_id', 'Category': CATEGORY},
        'grain': 'one product category', 'key': 'category_id',
    },
    'stores': {         # Support_EX_B_Stores.csv (tab-delimited)
        'match': 'store', 'sheet': 0, 'skiprows': 0,
        'rename': {'ID': 'store_id', 'StoreType': CHANNEL, 'City': 'City', 'State': 'State'},
        'grain': 'one store (SH00 is the website)', 'key': 'store_id',
    },
    'survey': {         # Support_EX_B_Survey.xlsx, sheet "Survey Results"
        'match': 'survey', 'sheet': 'Survey Results', 'skiprows': 2,
        'rename': {'Survey ID': STORE_YEAR, 'Store ID': 'store_id', 'Year': 'survey_year',
                   'Satisfaction': SATISFACTION, 'Interest': INTEREST},
        'grain': 'one store x one year', 'key': STORE_YEAR,
    },
}

# Revenue is stored in the Sales table, so these stay None.
QUANTITY = None
UNIT_PRICE = None
