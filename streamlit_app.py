"""Main app: layout and interaction only.
Calculations live in analytics.py, data joins in data_prep.py, the assistant in agent.py."""
import hashlib
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

import agent
import analytics
import config as C
import data_prep
import theme

MAX_QUESTIONS = 15  # per-session limit for the assistant

st.set_page_config(page_title='E-Presso BI Analyst', page_icon='🌲', layout='wide')
theme.apply()
st.title('E-Presso BI Analyst')
st.caption('Revenue dashboard and analytical assistant for E-Presso managers. '
           'Every number is calculated from the loaded data, never typed in.')


@st.cache_data(show_spinner=False)
def cached_load(file_bytes: bytes, filename: str, sheet_name, skiprows):
    # Keyed on the file CONTENTS, so a modified file never shows old numbers.
    return analytics.load_table(file_bytes, filename, sheet_name, skiprows)


# ---------------------------------------------------------------- sidebar
# Containers fix the order on screen (filters on top) even though the data
# has to load before the filter options are known.
side_filters = st.sidebar.container()
side_sources = st.sidebar.container()
with st.sidebar:
    st.header('Replace data')
    st.caption('Upload any E-Presso file to replace that table. Other tables keep '
               'the original data. Remove the upload (x) to go back.')
    uploads = st.file_uploader('Upload E-Presso files', accept_multiple_files=True,
                               type=['csv', 'txt', 'tsv', 'xlsx', 'xls'])

DATA_DIR = Path(__file__).parent / 'data'


def table_key(filename: str):
    """Which SOURCES table a file belongs to, by name (see config.py)."""
    return next((k for k, spec in C.SOURCES.items() if spec['match'] in filename.lower()), None)


def read(data: bytes, name: str):
    key = table_key(name)
    spec = C.SOURCES.get(key, {'sheet': 0, 'skiprows': 0})
    sheet = spec['sheet'] if name.lower().endswith(analytics.EXCEL_EXT) else 0
    return cached_load(data, name, sheet, spec['skiprows'])


# 1) Originals from data/ so the app works on a fresh load. 2) Uploads replace by table.
sources, files, fingerprint = {}, {}, hashlib.md5()
for path in sorted(DATA_DIR.glob('*')):
    if path.suffix.lower() in ('.csv', '.txt', '.tsv', '.xlsx', '.xls') and table_key(path.name):
        sources[table_key(path.name)] = ('original (data/)', path.name, path.read_bytes())
for up in uploads or []:
    key = table_key(up.name)
    if key is None:
        st.warning(f'{up.name}: name does not match any E-Presso table '
                   '(sales, products, categories, stores, survey). Ignored.')
        continue
    sources[key] = ('uploaded', up.name, up.getvalue())

if not sources:
    st.info('No data found. Upload the E-Presso files in the sidebar.')
    st.stop()
for key, (origin, name, data) in sources.items():
    fingerprint.update(data)
    try:
        files[name] = read(data, name)
    except Exception as exc:
        st.error(f'Could not read {name}: {exc}')
        st.stop()

built = data_prep.build_sales_table(files)
for p in built['problems']:
    st.warning(p)
sales = built['sales']
if sales is None:
    st.error('The sales table could not be built. See the messages above.')
    st.stop()

# New data = new answers. Clear assistant history so old numbers can't linger.
data_id = fingerprint.hexdigest()[:8]
if st.session_state.get('data_id') not in (None, data_id):
    st.session_state['history'] = []
    st.toast('New data loaded. Assistant history cleared.')
st.session_state['data_id'] = data_id

with side_filters:
    st.header('Filters')
    st.caption('Options come from the loaded data.')
    sidebar_filters = {}
    for col, label in ((C.YEAR, 'Year'), (C.CHANNEL, 'Sales channel'),
                       (C.STORE, 'Store'), (C.CATEGORY, 'Category')):
        options = agent.allowed_values(sales).get(col)
        if options:
            choice = st.selectbox(label, ['All'] + options)
            if choice != 'All':
                sidebar_filters[col] = choice

with side_sources:
    st.header('Loaded from')
    for key, (origin, name, _) in sources.items():
        raw = built['tables'].get(key)
        line = f'**{key.title()}**: {origin} · {name} · {len(raw):,} rows' if raw is not None else f'**{key.title()}**: {name}'
        if key == 'sales':
            line += f' · revenue sum ${sales[C.REVENUE].sum():,.2f}'
        st.markdown(line)
    st.caption(f'Data version: {data_id}')

view, _ = analytics._apply_filters(sales, sidebar_filters)
scope = agent.scope_text(sidebar_filters, sidebar_filters)

tab_dash, tab_data, tab_valid, tab_assistant = st.tabs(
    ['Dashboard', 'Data and quality', 'Validation', 'Assistant'])

# -------------------------------------------------------------- dashboard
with tab_dash:
    st.markdown(f'**Scope:** {scope}')
    total = analytics.get_total_revenue(sales, sidebar_filters)
    by_channel = analytics.get_revenue_by(sales, C.CHANNEL, sidebar_filters)
    k1, k2, k3, k4 = st.columns(4)
    k1.metric('Total revenue', f'${total.value:,.2f}' if not total.error else 'n/a',
              help='Sum of the Revenue column for the rows in scope.')
    k2.metric('Line items', f'{total.rows_used:,}')
    years = view[C.YEAR].dropna()
    k3.metric('Years in scope', f'{int(years.min())}–{int(years.max())}' if len(years) else 'n/a')
    if not by_channel.error and by_channel.value:
        top = max(by_channel.value.items(), key=lambda kv: kv[1]['revenue'])
        k4.metric('Largest channel', top[0], f"{top[1]['share_pct']}% of revenue", delta_color='off')

    left, right = st.columns(2)
    yearly = analytics.get_revenue_by(sales, C.YEAR, sidebar_filters)
    if not yearly.error and yearly.value:
        ydf = pd.DataFrame([{'Year': k, 'Revenue': v['revenue']} for k, v in yearly.value.items()])
        left.plotly_chart(px.bar(ydf, x='Year', y='Revenue', title='Revenue by year')
                          .update_layout(yaxis_tickprefix='$'), width='stretch')
    if not by_channel.error and by_channel.value:
        cdf = pd.DataFrame([{'Channel': k, 'Revenue': v['revenue']}
                            for k, v in by_channel.value.items()])
        right.plotly_chart(px.pie(cdf, names='Channel', values='Revenue',
                                  title='Revenue by sales channel'), width='stretch')

    monthly = (view.dropna(subset=[C.YEAR, C.MONTH])
               .groupby([C.YEAR, C.MONTH])[C.REVENUE].sum().reset_index())
    if len(monthly):
        monthly[C.YEAR] = monthly[C.YEAR].astype(str)
        st.plotly_chart(px.line(monthly, x=C.MONTH, y=C.REVENUE, color=C.YEAR, markers=True,
                                title='Monthly revenue by year',
                                labels={C.MONTH: 'Month', C.REVENUE: 'Revenue', C.YEAR: 'Year'})
                        .update_layout(yaxis_tickprefix='$', xaxis_dtick=1),
                        width='stretch')

    share = analytics.get_revenue_by(sales, C.MONTH, sidebar_filters)
    if not share.error and share.value:
        mdf = pd.DataFrame([{'Month': int(k), 'Share of revenue (%)': v['share_pct']}
                            for k, v in share.value.items()]).sort_values('Month')
        st.plotly_chart(px.bar(mdf, x='Month', y='Share of revenue (%)', text='Share of revenue (%)',
                               title='Percent of revenue by month (denominator: all revenue in scope)')
                        .update_layout(xaxis_dtick=1), width='stretch')
    if C.CATEGORY in sales.columns:
        cat = (view.dropna(subset=[C.YEAR, C.CATEGORY])
               .groupby([C.YEAR, C.CATEGORY])[C.REVENUE].sum().reset_index())
        cat[C.YEAR] = cat[C.YEAR].astype(str)
        st.plotly_chart(px.line(cat, x=C.YEAR, y=C.REVENUE, color=C.CATEGORY, markers=True,
                                title='Revenue by category and year',
                                labels={C.YEAR: 'Year', C.REVENUE: 'Revenue', C.CATEGORY: 'Category'})
                        .update_layout(yaxis_tickprefix='$'), width='stretch')
    if C.STORE in sales.columns:
        stores = analytics.get_revenue_by(sales, C.STORE, sidebar_filters)
        if not stores.error and stores.value:
            sdf = pd.DataFrame([{'Store': k, 'Revenue': v['revenue']}
                                for k, v in stores.value.items()]).sort_values('Revenue')
            st.plotly_chart(px.bar(sdf, x='Revenue', y='Store', orientation='h',
                                   title='Revenue by store').update_layout(xaxis_tickprefix='$'),
                            width='stretch')
    st.caption(analytics.REVENUE_CAVEAT)

# ---------------------------------------------------------- data + quality
with tab_data:
    st.subheader('Source tables')
    for name, df in files.items():
        prof = analytics.profile_table(df)
        with st.expander(f'{name}: {prof["rows"]:,} rows, {prof["columns"]} columns, '
                         f'{prof["duplicate_rows"]} duplicate rows'):
            st.dataframe(df.head(20))
            a, b = st.columns(2)
            a.dataframe(prof['missing'])
            b.dataframe(prof['dtypes'])
    st.subheader('Grain of each table')
    st.dataframe(pd.DataFrame([{'table': k, 'one row =': v['grain']}
                               for k, v in C.SOURCES.items()]), hide_index=True)
    st.subheader('Merge checks')
    if built['merges']:
        st.dataframe(pd.DataFrame(built['merges']), hide_index=True)
    else:
        st.caption('No merges yet. Add them in data_prep.build_sales_table().')
    st.subheader('Prepared sales table quality')
    st.json(analytics.data_quality_report(sales).to_dict()['value'])

# -------------------------------------------------------------- validation
with tab_valid:
    st.markdown('Numbers to compare with Power BI. Always **all data**, ignoring sidebar filters.')
    v_total = analytics.get_total_revenue(sales)
    v_chan = analytics.get_revenue_by(sales, C.CHANNEL)
    v_year = analytics.get_revenue_by(sales, C.YEAR)
    st.metric('Total revenue (all years)', f'${v_total.value:,.2f}' if not v_total.error else 'n/a')
    a, b = st.columns(2)
    a.write('By channel'); a.json(v_chan.value or {})
    b.write('By year'); b.json(v_year.value or {})
    st.write('By year and month')
    st.dataframe(sales.pivot_table(index=C.MONTH, columns=C.YEAR, values=C.REVENUE,
                                   aggfunc='sum').round(2))

# --------------------------------------------------------------- assistant
with tab_assistant:
    try:  # no secrets file at all is fine: rules-based mode
        key = st.secrets.get('GEMINI_API_KEY')
        model = st.secrets.get('GEMINI_MODEL', 'gemini-2.5-flash')
    except Exception:
        key, model = None, None
    mode = 'llm' if key else 'rules'
    st.caption(f"Mode: {'Language model (Gemini) with rules-based fallback' if key else 'Rules-based (no API key set)'}. "
               f'{agent.CAPABILITIES} Limit: {MAX_QUESTIONS} questions per session.')
    st.session_state.setdefault('n_questions', 0)
    st.session_state.setdefault('history', [])
    for item in st.session_state['history']:
        with st.chat_message('user'):
            st.write(item['question'])
        with st.chat_message('assistant'):
            ans = item['answer']
            if ans.get('note'):
                st.info(ans['note'])
            st.markdown(f"**Scope:** {ans['scope']}")
            st.markdown(f"**Findings:** {ans['findings']}")
            if ans['interpretation']:
                st.markdown(f"**Interpretation:** {ans['interpretation']}")
            if ans['next_steps']:
                st.markdown(f"**Next steps:** {ans['next_steps']}")
            with st.expander(f"Tool-call log ({ans['mode']})"):
                st.json(ans['tool_log'] or 'No tool was called.')
    question = st.chat_input('Ask a question about the loaded data')
    if question:
        if st.session_state['n_questions'] >= MAX_QUESTIONS:
            st.warning('Question limit reached for this session. Reload the page to start over.')
        else:
            st.session_state['n_questions'] += 1
            answer = agent.answer_question(question, sales, mode=mode,
                                           sidebar_filters=sidebar_filters,
                                           api_key=key, model=model or 'gemini-2.5-flash',
                                           survey=built['survey'])
            st.session_state['history'].append({'question': question, 'answer': answer})
            st.rerun()
