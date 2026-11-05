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
            df = files[hits[0]].rename(columns=spec['rename'])
            df.columns = [str(c).strip() for c in df.columns]
            tables[key] = df
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
    dates = pd.to_datetime(df[C.DATE], errors='coerce')
    return df.assign(**{C.DATE: dates, C.YEAR: dates.dt.year.astype('Int64'),
                        C.MONTH: dates.dt.month.astype('Int64')})


def _store_labels(stores: pd.DataFrame) -> pd.DataFrame:
    """'SH01 Orlando, FL'. City alone is not unique (two Orlando stores)."""
    def label(r):
        if pd.isna(r.get('City')) or str(r.get('City')).strip() == '':
            return f"{r['store_id']} {r.get(C.CHANNEL, '')}".strip()
        return f"{r['store_id']} {r['City']}, {r['State']}"
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
    lookup = table[[key] + cols]
    dups = int(lookup[key].duplicated().sum())
    if dups:
        problems.append(f'{name} has {dups} duplicate {key} value(s). Kept the first of each '
                        'so revenue is not duplicated.')
        lookup = lookup.drop_duplicates(key)
    merged, rep = analytics.check_merge(sales, lookup, on=key, value_col=C.REVENUE, how='left')
    unmatched = int(merged[cols[0]].isna().sum())  # rows that found no match
    if unmatched:
        problems.append(f'{unmatched} sales row(s) have a {key} not found in {name}.')
    merges.append({'merge': f'sales + {name} on {key}', **rep, 'unmatched_rows': unmatched})
    return merged


def build_sales_table(files: dict[str, pd.DataFrame]) -> dict:
    """Returns {'sales', 'survey', 'merges', 'problems', 'tables'}."""
    tables, problems = identify_tables(files)
    merges: list = []
    out = {'sales': None, 'survey': None, 'merges': merges, 'problems': problems,
           'tables': tables}

    if 'sales' not in tables:
        if len(files) == 1:  # a single pre-joined file with the needed columns
            tables['sales'] = next(iter(files.values()))
        else:
            problems.append("No uploaded file name contains 'sales'.")
            return out
    sales = add_revenue(tables['sales'])

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
    for col, n in sales[[C.DATE, C.REVENUE, C.CHANNEL]].isna().sum().items():
        if n:
            problems.append(f'{n} sales row(s) have a missing or unreadable {col}.')
    out['sales'] = sales

    if 'survey' in tables:
        out['survey'] = prepare_survey(tables['survey'], problems)
    return out


def prepare_survey(survey: pd.DataFrame, problems: list) -> pd.DataFrame | None:
    """Survey grain is store x year. It is NOT joined to the monthly sales rows;
    the satisfaction tool aggregates revenue to store x year first."""
    need = [C.STORE_YEAR, C.SATISFACTION]
    if any(c not in survey.columns for c in need):
        problems.append(f'Survey file is missing column(s): {need}. Expected sheet '
                        '"Survey Results" with headers on the third row.')
        return None
    s = survey.dropna(subset=[C.STORE_YEAR]).copy()
    for c in (C.SATISFACTION, C.INTEREST):
        if c in s.columns:
            s[c] = pd.to_numeric(s[c], errors='coerce')
    n_blank = int(s[C.SATISFACTION].isna().sum())
    if n_blank:
        problems.append(f'{n_blank} survey row(s) have no satisfaction score '
                        '(the website, SH00, has none).')
    return s


def merge_is_safe(lookup: pd.DataFrame, key) -> bool:
    """A lookup table is safe to join only if each key appears once."""
    return not lookup.duplicated(subset=key).any()
