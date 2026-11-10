"""Business logic. Keep Streamlit code OUT of this file so every function can be
tested on its own and reused by the assistant."""
from __future__ import annotations

import io
from dataclasses import asdict, dataclass, field

import pandas as pd

EXCEL_EXT = ('.xlsx', '.xlsm', '.xls')
TEXT_EXT = ('.csv', '.txt', '.tsv')


# ---------------------------------------------------------------- loading
def excel_sheet_names(file_bytes: bytes) -> list[str]:
    return pd.ExcelFile(io.BytesIO(file_bytes)).sheet_names


def load_table(file_bytes: bytes, filename: str, sheet_name=0, skiprows=0) -> pd.DataFrame:
    """Read an uploaded CSV / TXT / TSV / Excel file into a DataFrame."""
    name = filename.lower()
    buffer = io.BytesIO(file_bytes)
    if name.endswith(EXCEL_EXT):
        return pd.read_excel(buffer, sheet_name=sheet_name, skiprows=skiprows)
    if name.endswith(TEXT_EXT):
        # sep=None sniffs the delimiter; utf-8-sig drops the marker Excel's "CSV UTF-8" adds to the header
        return pd.read_csv(buffer, sep=None, engine='python', skiprows=skiprows, encoding='utf-8-sig')
    raise ValueError(f'Unsupported file type: {filename}')


def profile_table(df: pd.DataFrame) -> dict:
    """Basic profile: size, duplicates, missing values, data types."""
    missing = df.isna().sum()
    return {
        'rows': len(df),
        'columns': df.shape[1],
        'duplicate_rows': int(df.duplicated().sum()),
        'missing': pd.DataFrame({
            'column': missing.index,
            'missing': missing.values,
            'pct_missing': (missing.values / max(len(df), 1) * 100).round(2),
        }),
        'dtypes': pd.DataFrame({'column': df.columns, 'dtype': df.dtypes.astype(str).values}),
    }


# ---------------------------------------------------------- tool contract
@dataclass
class ToolResult:
    """Every analytical function returns this. The assistant may only narrate it.
    Keep `value` to plain Python types (numbers, strings, dicts, lists)."""
    tool: str
    value: object
    definition: str
    scope: dict
    rows_used: int
    caveats: list = field(default_factory=list)
    error: str | None = None

    def to_dict(self) -> dict:
        out = asdict(self)
        if out['error'] is None:  # the contract is the six keys; error appears only on failure
            del out['error']
        return out


def _error(tool: str, message: str, scope: dict | None = None) -> ToolResult:
    return ToolResult(tool=tool, value=None, definition='', scope=scope or {},
                      rows_used=0, caveats=[], error=message)


def _apply_filters(df: pd.DataFrame, filters: dict | None):
    """Validate filters against the LOADED data, then apply them."""
    subset = df
    for col, wanted in (filters or {}).items():
        if col not in df.columns:
            return subset, f'Unknown column: {col}'
        wanted_list = list(wanted) if isinstance(wanted, (list, tuple, set)) else [wanted]
        valid = set(df[col].dropna().unique())
        bad = [w for w in wanted_list if w not in valid]
        if bad:
            examples = sorted(map(str, valid))[:20]
            return subset, f'{bad} not found in column {col}. Valid values include: {examples}'
        subset = subset[subset[col].isin(wanted_list)]
    if filters and subset.empty:  # each value exists, but not together
        return subset, f'No rows match this combination of filters: {filters}'
    return subset, None


# ------------------------------------------------------ analytical tools
def get_total(df: pd.DataFrame, value_col: str, filters: dict | None = None) -> ToolResult:
    """Sum of one numeric column, optionally filtered. EXAMPLE tool: replace the
    generic column names with your own definition of revenue."""
    name = 'get_total'
    if value_col not in df.columns:
        return _error(name, f'Unknown column: {value_col}')
    subset, err = _apply_filters(df, filters)
    if err:
        return _error(name, err, {'filters': filters})
    values = pd.to_numeric(subset[value_col], errors='coerce')
    n_bad = int(values.isna().sum())
    caveats = ['This is a sum of the chosen column. Revenue is not profit.']
    if n_bad:
        caveats.append(f'{n_bad} row(s) had a missing or non-numeric {value_col} and were excluded.')
    return ToolResult(tool=name, value=float(values.sum()), definition=f'Sum of {value_col}',
                      scope={'filters': filters or 'none (all rows)'},
                      rows_used=int(values.notna().sum()), caveats=caveats)


def group_total(df: pd.DataFrame, value_col: str, group_col: str,
                filters: dict | None = None) -> ToolResult:
    """Sum of one numeric column by group (store, channel, year, ...)."""
    name = 'group_total'
    for col in (value_col, group_col):
        if col not in df.columns:
            return _error(name, f'Unknown column: {col}')
    subset, err = _apply_filters(df, filters)
    if err:
        return _error(name, err, {'filters': filters})
    work = subset.assign(**{value_col: pd.to_numeric(subset[value_col], errors='coerce')})
    n_bad = int(work[value_col].isna().sum())
    n_nogroup = int(work[group_col].isna().sum())
    grouped = work.dropna(subset=[value_col, group_col]).groupby(group_col)[value_col].sum()
    caveats = ['Sums of the chosen column. Revenue is not profit.']
    if n_bad:
        caveats.append(f'{n_bad} row(s) with missing or non-numeric {value_col} were excluded.')
    if n_nogroup:
        caveats.append(f'{n_nogroup} row(s) with a missing {group_col} were excluded.')
    return ToolResult(tool=name, value={str(k): float(v) for k, v in grouped.items()},
                      definition=f'Sum of {value_col} by {group_col}',
                      scope={'filters': filters or 'none (all rows)'},
                      rows_used=int(len(work) - n_bad - n_nogroup), caveats=caveats)


def data_quality_report(df: pd.DataFrame) -> ToolResult:
    """Row count, duplicate rows, and missing values per column."""
    missing = {c: int(n) for c, n in df.isna().sum().items() if n > 0}
    caveats = []
    if missing:
        caveats.append('Missing values may limit conclusions drawn from those columns.')
    return ToolResult(tool='data_quality_report',
                      value={'rows': len(df), 'duplicate_rows': int(df.duplicated().sum()),
                             'columns_with_missing': missing,
                             **({'repeated_sales_ids': int(df['sales_id'].dropna().duplicated().sum())}
                                if 'sales_id' in df.columns else {})},
                      definition='Counts of duplicate rows and missing values in the loaded table',
                      scope={'filters': 'none (full table)'}, rows_used=len(df), caveats=caveats)


# ------------------------------------------------- E-Presso revenue tools
# These take the prepared sales table from data_prep.py, which uses the column
# names in config.py. Filters are explicit arguments, never hidden app state.
import config as C  # noqa: E402

REVENUE_CAVEAT = 'Revenue is not profit. No cost data is used.'


def _scope(filters: dict | None) -> dict:
    return {k: v for k, v in (filters or {}).items()} or {'filters': 'All data'}


def _revenue_subset(df, filters, tool):
    """Shared first step: check columns, apply filters, coerce revenue."""
    if C.REVENUE not in df.columns:
        return None, _error(tool, f'Column {C.REVENUE!r} is missing from the loaded data.')
    subset, err = _apply_filters(df, filters)
    if err:
        return None, _error(tool, err, _scope(filters))
    rev = pd.to_numeric(subset[C.REVENUE], errors='coerce')
    return subset.assign(**{C.REVENUE: rev}), None


def _missing_note(df, col) -> list:
    n = int(df[col].isna().sum()) if col in df.columns else 0
    if not n:
        return []
    lost = '' if col == C.REVENUE else f', worth ${df.loc[df[col].isna(), C.REVENUE].sum():,.2f},'
    return [f'{n} row(s) with missing {col}{lost} were excluded.']


def get_total_revenue(df, filters: dict | None = None) -> ToolResult:
    name = 'get_total_revenue'
    sub, err = _revenue_subset(df, filters, name)
    if err:
        return err
    return ToolResult(name, round(float(sub[C.REVENUE].sum()), 2),
                      'Sum of line-item revenue', _scope(filters),
                      int(sub[C.REVENUE].notna().sum()),
                      [REVENUE_CAVEAT] + _missing_note(sub, C.REVENUE))


def get_revenue_by(df, group: str, filters: dict | None = None) -> ToolResult:
    """Revenue grouped by one of: channel, store, category, product, year, month."""
    name = 'get_revenue_by'
    allowed = [c for c in (C.CHANNEL, C.STORE, C.CATEGORY, C.PRODUCT, C.YEAR, C.MONTH)
               if c in df.columns]
    if group not in allowed:
        return _error(name, f'Cannot group by {group!r}. Options in this data: {allowed}')
    sub, err = _revenue_subset(df, filters, name)
    if err:
        return err
    clean = sub.dropna(subset=[C.REVENUE, group])
    totals = clean.groupby(group)[C.REVENUE].sum().round(2)
    grand = float(totals.sum())
    value = {str(k): {'revenue': float(v),
                      'share_pct': round(float(v) / grand * 100, 2) if grand else 0.0}
             for k, v in totals.items()}
    single = [f'Only one {group} is in scope, so its share is 100%.'] if len(value) == 1 else []
    return ToolResult(name, value, f'Sum of line-item revenue by {group}; share = group revenue / '
                      f'total revenue in scope with a known {group}', _scope(filters), len(clean),
                      [REVENUE_CAVEAT] + single + _missing_note(sub, group)
                      + _missing_note(sub, C.REVENUE))


def get_growth(df, group: str, filters: dict | None = None) -> ToolResult:
    """Percent change in revenue from the first to the last year, per group.
    Answers 'which store/channel grew or declined the most'. If the two years cover
    different months, only the months in both are compared, so a partial year
    cannot look like a collapse."""
    name = 'get_growth'
    if C.YEAR not in df.columns:
        return _error(name, 'No year column. Check the date column in config.py.')
    if group not in df.columns or group in (C.YEAR, C.MONTH):
        return _error(name, f'Cannot compare growth by {group!r}.')
    sub, err = _revenue_subset(df, filters, name)
    if err:
        return err
    clean = sub.dropna(subset=[C.REVENUE, group, C.YEAR])
    years = sorted(clean[C.YEAR].unique())
    if len(years) < 2:
        return _error(name, 'Need at least two years of data in scope to measure growth. '
                      'If a Year filter is on, set it to All.', _scope(filters))
    first, last = int(years[0]), int(years[-1])
    partial_note = None
    compared = clean
    if C.MONTH in clean.columns:
        m_first = set(clean.loc[clean[C.YEAR] == first, C.MONTH].dropna())
        m_last = set(clean.loc[clean[C.YEAR] == last, C.MONTH].dropna())
        shared = sorted(int(m) for m in m_first & m_last)
        if m_first != m_last:
            partial_note = (f'Partial year: {first} has {len(m_first)} month(s) of data and '
                            f'{last} has {len(m_last)}. ')
            if shared:
                compared = clean[clean[C.MONTH].isin(shared)]
                partial_note += f'Only month(s) {shared}, found in both years, are compared.'
            else:
                partial_note += 'They share no months, so this is not a like-for-like comparison.'
    pivot = compared.pivot_table(index=group, columns=C.YEAR, values=C.REVENUE, aggfunc='sum')
    value, caveats = {}, [REVENUE_CAVEAT, f'Compares {first} to {last} only; '
                          'years in between are not used.']
    for g, row in pivot.iterrows():
        a, b = row.get(first), row.get(last)
        if pd.isna(a) or pd.isna(b) or a <= 0:
            caveats.append(f'{g}: no revenue in {first} or {last}, growth not calculated.')
            continue
        value[str(g)] = {f'revenue_{first}': round(float(a), 2),
                         f'revenue_{last}': round(float(b), 2),
                         'pct_change': round((float(b) - float(a)) / float(a) * 100, 2)}
    if not value:
        return _error(name, f'Growth could not be calculated: no {group} has revenue in both '
                      f'{first} and {last}.', _scope(filters))
    if partial_note:
        caveats.insert(0, partial_note)
    caveats += _missing_note(sub, group) + _missing_note(sub, C.YEAR)
    if not any(v['pct_change'] < 0 for v in value.values()):
        caveats.append(f'No {group} had lower revenue in {last} than in {first}.')
    return ToolResult(name, value, f'(revenue {last} - revenue {first}) / revenue {first} x 100, '
                      f'by {group}', _scope(filters), len(compared), caveats)


def get_monthly_share(df, year: int | None = None, filters: dict | None = None) -> ToolResult:
    """Each month's revenue as a % of that YEAR's total. With no year, two definitions:
    % of the all-years total (Power BI's '% of grand total') and the average yearly share."""
    name = 'get_monthly_share'
    filters = dict(filters or {})
    if year is not None:
        filters[C.YEAR] = year
    sub, err = _revenue_subset(df, filters, name)
    if err:
        return err
    clean = sub.dropna(subset=[C.REVENUE, C.MONTH])
    totals = clean.groupby(C.MONTH)[C.REVENUE].sum()
    annual = float(totals.sum())
    caveats = [REVENUE_CAVEAT]
    if year is None:
        by_year = clean.groupby([C.YEAR, C.MONTH])[C.REVENUE].sum()
        yearly_share = by_year / by_year.groupby(level=0).transform('sum') * 100
        avg = yearly_share.groupby(level=1).mean()
        value = {int(m): {'revenue': round(float(v), 2),
                          'share_pct': round(float(v) / annual * 100, 2) if annual else 0.0,
                          'avg_share_of_own_year_pct': round(float(avg.get(m, 0)), 2)}
                 for m, v in totals.items()}
        caveats.append('share_pct = month across all years / all-years total (Power BI). '
                       'avg_share_of_own_year_pct = average of each year\'s monthly share.')
        return ToolResult(name, value, 'Monthly revenue (all years) / all-years revenue x 100',
                          _scope(filters), len(clean), caveats)
    value = {int(m): {'revenue': round(float(v), 2),
                      'share_pct': round(float(v) / annual * 100, 2) if annual else 0.0}
             for m, v in totals.items()}
    if len(value) < 12:
        caveats.append(f'Only {len(value)} month(s) have revenue in {year}.')
    return ToolResult(name, value, f'Monthly revenue / total {year} revenue x 100',
                      _scope(filters), len(clean), caveats)


def get_satisfaction_vs_revenue(df, survey, filters: dict | None = None) -> ToolResult:
    """Correlation between survey satisfaction and revenue, at store x year grain.
    Monthly sales are summed to store x year FIRST, so survey scores are not repeated."""
    name = 'get_satisfaction_vs_revenue'
    if survey is None or C.SATISFACTION not in getattr(survey, 'columns', []):
        return _error(name, 'No survey data is loaded. Upload the Survey workbook.')
    sub, err = _revenue_subset(df, filters, name)
    if err:
        return err
    per_store_year = sub.groupby(C.STORE_YEAR, as_index=False)[C.REVENUE].sum()
    joined, rep = check_merge(per_store_year, survey[[C.STORE_YEAR, C.SATISFACTION]]
                              .drop_duplicates(C.STORE_YEAR), on=C.STORE_YEAR,
                              value_col=C.REVENUE, how='left')
    usable = joined.dropna(subset=[C.SATISFACTION, C.REVENUE])
    caveats = [REVENUE_CAVEAT,
               'Correlation shows the two move together. It does not show that satisfaction '
               'causes revenue; store size and market could drive both.',
               f'{len(joined) - len(usable)} store-year(s) had no satisfaction score '
               '(e.g. the website) and were excluded, which limits any conclusion about '
               'satisfaction.']
    if len(usable) < 3:
        return _error(name, 'Fewer than 3 store-years have both revenue and satisfaction.',
                      _scope(filters))
    r = float(usable[C.SATISFACTION].corr(usable[C.REVENUE]))
    if pd.isna(r):
        return _error(name, 'Correlation is undefined: satisfaction or revenue does not vary '
                      'in this scope.', _scope(filters))
    if rep['changed']:
        caveats.append('Warning: the survey join changed the revenue total.')
    return ToolResult(name, {'pearson_r': round(r, 3), 'store_years': len(usable),
                             'avg_satisfaction': round(float(usable[C.SATISFACTION].mean()), 2)},
                      'Pearson correlation of yearly store revenue with that store-year\'s '
                      'satisfaction score (0-5)', _scope(filters), int(len(usable)), caveats)


# ------------------------------------------------------------ merge check
def check_merge(left: pd.DataFrame, right: pd.DataFrame, on, value_col: str, how: str = 'left'):
    """Merge, and report whether the join changed the row count or the revenue sum.
    `value_col` must be a numeric column in `left`. Returns (merged, report)."""
    before_rows = len(left)
    before_sum = float(pd.to_numeric(left[value_col], errors='coerce').sum())
    merged = left.merge(right, on=on, how=how)
    after_rows = len(merged)
    after_sum = float(pd.to_numeric(merged[value_col], errors='coerce').sum())
    fan_out = after_rows > before_rows or abs(after_sum - before_sum) > 1e-9
    report = {
        'rows_before': before_rows, 'rows_after': after_rows,
        'sum_before': before_sum, 'sum_after': after_sum,
        'changed': fan_out,
        'warning': ('The join changed the row count or the total. Check the grain and keys '
                    'of both tables before using this result.') if fan_out else '',
    }
    return merged, report
