"""Turns the uploaded E-Presso files into one sales table at the Sales grain
(one store x product x month). No Streamlit code here. Every merge goes through
analytics.check_merge so rows and revenue before and after are recorded."""
from __future__ import annotations

import pandas as pd

import analytics
import config as C


def identify_tables(files: dict[str, pd.DataFrame]) -> tuple[dict, list[str]]:
    """Match uploaded file names to SOURCES. Returns (tables, problems)."""
    tables, problems = {}, []
    for key, spec in C.SOURCES.items():
        hits = [name for name in files if spec['match'] in name.lower()]
        if len(hits) == 1:
            tables[key] = (files[hits[0]].rename(columns=lambda c: str(c).strip())
                           .rename(columns=spec['rename']))
        elif len(hits) > 1:
            problems.append(f"More than one file looks like '{key}': {hits}")
    return tables, problems


def add_revenue(df: pd.DataFrame) -> pd.DataFrame:
    """Use stored revenue, or calculate quantity x price if config says so."""
    if C.REVENUE not in df.columns and C.QUANTITY and C.UNIT_PRICE:
        qty = pd.to_numeric(df[C.QUANTITY], errors='coerce')
        price = pd.to_numeric(df[C.UNIT_PRICE], errors='coerce')
        df = df.assign(**{C.REVENUE: qty * price})
    if C.REVENUE in df.columns:
        df = df.assign(**{C.REVENUE: pd.to_numeric(df[C.REVENUE], errors='coerce')})
    return df


def add_dates(df: pd.DataFrame) -> pd.DataFrame:
    # 'mixed' reads each cell on its own, so one odd format cannot blank out the rest
    dates = pd.to_datetime(df[C.DATE], errors='coerce', format='mixed')
    return df.assign(**{C.DATE: dates, C.YEAR: dates.dt.year.astype('Int64'),
                        C.MONTH: dates.dt.month.astype('Int64')})


def _store_labels(stores: pd.DataFrame) -> pd.DataFrame:
    """'SH01 Orlando, FL'. City alone is not unique (two Orlando stores)."""
    def label(r):
        place = ', '.join(str(r[c]).strip() for c in ('City', 'State') if pd.notna(r.get(c)))
        if not place and pd.notna(r.get(C.CHANNEL)):
            place = r[C.CHANNEL]
        return f"{r['store_id']} {place}".strip()
    return stores.assign(**{C.STORE: stores.apply(label, axis=1)})


def _product_labels(products: pd.DataFrame, sales: pd.DataFrame) -> pd.DataFrame:
    """Product names that repeat (e.g. 'Base Model') get their category added."""
    if C.CATEGORY not in sales.columns:
        return products
    cat = sales.drop_duplicates('product_id').set_index('product_id')[C.CATEGORY]
    dup = products[C.PRODUCT].duplicated(keep=False)
    labels = products[C.PRODUCT].where(
        ~dup, products[C.PRODUCT] + ' (' + products['product_id'].map(cat).fillna('?') + ')')
    return products.assign(**{C.PRODUCT: labels})


def _lookup(sales, table, key, cols, name, merges, problems):
    """Left-join a lookup table, after checking it has one row per key."""
    missing = [c for c in [key] + cols if c not in table.columns]
    if missing:
        problems.append(f'{name} file is missing column(s): {missing}')
        return sales
    lookup = table[[key] + cols].dropna(subset=[key])  # a blank key must not match a blank key
    dups = int(lookup[key].duplicated().sum())
    if dups:
        problems.append(f'{name} has {dups} duplicate {key} value(s). Kept the first of each '
                        'so revenue is not duplicated.')
        lookup = lookup.drop_duplicates(key)
    if key not in sales.columns:
        problems.append(f'Sales file is missing column {key!r}, so {name} could not be joined.')
        return sales
    # object keys: a key column that is all blank loads as numbers, and pandas refuses that merge
    sales = sales.assign(**{key: sales[key].astype(object)})
    lookup = lookup.assign(**{key: lookup[key].astype(object)})
    merged, rep = analytics.check_merge(sales, lookup, on=key, value_col=C.REVENUE, how='left')
    unmatched = int((~sales[key].isin(lookup[key])).sum())  # keys with no match in the lookup
    if unmatched:
        problems.append(f'{unmatched} row(s) have a {key} not found in {name}: '
                        f'{sorted(sales.loc[~sales[key].isin(lookup[key]), key].astype(str).unique())[:10]}')
    merges.append({'merge': f'sales + {name} on {key}', **rep, 'unmatched_rows': unmatched})
    return merged


def missing_columns(tables: dict) -> list[str]:
    """One plain message per table that lacks a column the app needs, using the
    file's own column names. The survey is checked in prepare_survey, because the
    dashboard still works without it."""
    messages = []
    for key, table in tables.items():
        gone = [src for src, name in C.SOURCES[key]['rename'].items() if name not in table.columns
                and not (name == C.REVENUE and C.QUANTITY and C.UNIT_PRICE)]  # add_revenue makes it
        if gone and key != 'survey':
            messages.append(f'The {key} file is missing required column(s): {gone}. '
                            'Column names must stay the same as the original file.')
    return messages


def quality_notes(sales: pd.DataFrame) -> list[str]:
    """Blanks, repeated Sales IDs, and negative revenue. Rows are reported, never removed."""
    notes = [f'{n} sales row(s) have a missing or unreadable {col}.'
             for col, n in sales.drop(columns=[C.YEAR, C.MONTH]).isna().sum().items() if n]
    repeated = sales['sales_id'].notna() & sales['sales_id'].duplicated(keep='first')
    if repeated.any():
        notes.append(f'{int(repeated.sum())} sales row(s) repeat a Sales ID, worth '
                     f'${sales.loc[repeated, C.REVENUE].sum():,.2f}. They are still counted in '
                     'revenue; check the source file.')
    negative = sales[C.REVENUE] < 0
    if negative.any():
        notes.append(f'{int(negative.sum())} sales row(s) have negative revenue, totaling '
                     f'${sales.loc[negative, C.REVENUE].sum():,.2f}. They are still counted.')
    return notes


def build_sales_table(files: dict[str, pd.DataFrame]) -> dict:
    """Returns {'sales', 'survey', 'merges', 'problems', 'tables'}."""
    tables, problems = identify_tables(files)
    merges: list = []
    out = {'sales': None, 'survey': None, 'merges': merges, 'problems': problems,
           'tables': tables}

    if 'sales' not in tables:
        problems.append("No uploaded file name contains 'sales'.")
        return out
    gone = missing_columns({k: t for k, t in tables.items() if k in C.SOURCES})
    if gone:
        problems.extend(gone)
        return out
    if tables['sales'].empty:
        problems.append('The sales file has no data rows.')
        return out
    sales = add_revenue(tables['sales'])
    if C.REVENUE not in sales.columns:
        problems.append("The sales file has no 'Revenue' column (see config.py), so revenue "
                        f"cannot be calculated. Columns found: {list(tables['sales'].columns)}")
        return out

    if 'categories' in tables:
        sales = _lookup(sales, tables['categories'], 'category_id', [C.CATEGORY],
                        'categories', merges, problems)
    if 'products' in tables:
        prods = _product_labels(tables['products'], sales)
        sales = _lookup(sales, prods, 'product_id', [C.PRODUCT], 'products', merges, problems)
    if 'stores' in tables:
        stores = _store_labels(tables['stores'])
        sales = _lookup(sales, stores, 'store_id', [C.CHANNEL, C.STORE], 'stores', merges,
                        problems)

    missing = [c for c in C.REQUIRED if c not in sales.columns]
    if missing:
        problems.append(f'Required column(s) missing: {missing}. Upload the Stores file '
                        '(for channel) and check config.py.')
        return out

    sales = add_dates(sales)
    problems.extend(quality_notes(sales))
    out['sales'] = sales

    if 'survey' in tables:
        out['survey'] = prepare_survey(tables['survey'], problems)
    if out['survey'] is not None:  # same check the satisfaction tool relies on, at store-year grain
        yearly = sales.groupby(C.STORE_YEAR, as_index=False)[C.REVENUE].sum()
        _lookup(yearly, out['survey'], C.STORE_YEAR, [C.SATISFACTION],
                'survey (sales summed to store x year first)', merges, problems)
    return out


def prepare_survey(survey: pd.DataFrame, problems: list) -> pd.DataFrame | None:
    """Survey grain is store x year. It is NOT joined to the monthly sales rows;
    the satisfaction tool aggregates revenue to store x year first."""
    need = [C.STORE_YEAR, C.SATISFACTION]
    if any(c not in survey.columns for c in need):
        problems.append("The survey file is missing required column(s): ['Survey ID', "
                        "'Satisfaction']. Expected sheet \"Survey Results\" with headers on the "
                        'third row. The dashboard still works; satisfaction questions will not.')
        return None
    s = survey.dropna(subset=[C.STORE_YEAR]).copy()
    for c in (C.SATISFACTION, C.INTEREST):
        if c in s.columns:
            s[c] = pd.to_numeric(s[c], errors='coerce')
    blank = s.loc[s[C.SATISFACTION].isna(), C.STORE_YEAR].astype(str).tolist()
    if blank:
        problems.append(f'{len(blank)} survey row(s) have no satisfaction score: {blank[:10]}.')
    return s


def merge_is_safe(lookup: pd.DataFrame, key) -> bool:
    """A lookup table is safe to join only if each key appears once."""
    return not lookup.duplicated(subset=key).any()
