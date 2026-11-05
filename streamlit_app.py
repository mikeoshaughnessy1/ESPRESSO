"""Main app: layout and interaction only.
Calculations live in analytics.py, data joins in data_prep.py, the assistant in agent.py,
and the design system (colors, type, chart template, HTML blocks) in theme.py."""
import hashlib
import re
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import agent
import analytics
import config as C
import data_prep
import theme as T

MAX_QUESTIONS = 15  # per-session limit for the assistant
SECTIONS = ['01  Overview', '02  Data & quality', '03  Validation', '04  Assistant']
MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

st.set_page_config(page_title='E-Presso Analyst', page_icon='☕', layout='wide')
T.apply()


@st.cache_data(show_spinner=False)
def cached_load(file_bytes: bytes, filename: str, sheet_name, skiprows):
    # Keyed on the file CONTENTS, so a modified file never shows old numbers.
    return analytics.load_table(file_bytes, filename, sheet_name, skiprows)


# ---------------------------------------------------------------- sidebar
# Containers fix the order on screen even though the data has to load first.
with st.sidebar:
    T.html('<div class="ep-mark">E&#8209;Presso<span>.</span></div>'
           '<div class="ep-label" style="margin:0.35rem 0 1rem">Revenue analyst</div>')
nav_slot = st.sidebar.container()
side_filters = st.sidebar.container()
side_sources = st.sidebar.container()
with st.sidebar:
    st.header('Replace data')
    st.caption('Upload an E-Presso file to replace that one table. Remove it (x) to go back.')
    uploads = st.file_uploader('Upload E-Presso files', accept_multiple_files=True,
                               type=['csv', 'txt', 'tsv', 'xlsx', 'xls'],
                               label_visibility='collapsed')

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
notes = built['problems']  # data-quality findings, shown on the Data and quality tab
sales = built['sales']
if sales is None:  # can't build the dashboard at all: show the problems up top
    for p in notes:
        st.warning(p)
    st.error('The sales table could not be built. See the messages above.')
    st.stop()

# New data = new answers. Clear assistant history so old numbers can't linger.
data_id = fingerprint.hexdigest()[:8]
data_changed = st.session_state.get('data_id') not in (None, data_id)
if data_changed:
    st.session_state['history'] = []
    st.toast('New data loaded. All numbers recalculated; assistant history cleared.',
             icon='📂', duration=10)
st.session_state['data_id'] = data_id
uploaded = {k: name for k, (origin, name, _) in sources.items() if origin == 'uploaded'}


with nav_slot:
    nav_label = {SECTIONS[1]: f'{SECTIONS[1]}   ·{len(notes)}' if notes else SECTIONS[1]}
    section = st.radio('Section', SECTIONS, key='section', label_visibility='collapsed',
                       format_func=lambda s: nav_label.get(s, s))

with side_filters:
    st.header('Filters')
    sidebar_filters = {}
    for col, label in ((C.YEAR, 'Year'), (C.CHANNEL, 'Sales channel'),
                       (C.STORE, 'Store'), (C.CATEGORY, 'Category')):
        options = agent.allowed_values(sales).get(col)  # built from the loaded data
        if options:
            choice = st.selectbox(label, ['All'] + options)
            if choice != 'All':
                sidebar_filters[col] = choice

with side_sources:
    st.header('Sources')
    lines = []
    for key, (origin, name, _) in sources.items():
        raw = built['tables'].get(key)
        flag = '<span class="ep-accent">uploaded</span>' if origin == 'uploaded' else 'original'
        rows = f'{len(raw):,} rows' if raw is not None else ''
        lines.append(f'<div class="ep-meta" style="margin:0.25rem 0"><b style="color:{T.INK}">{key.title()}</b>'
                     f' · {flag} · {rows}</div>')
    lines.append(f'<div class="ep-meta" style="margin-top:0.5rem">Sales revenue sum '
                 f'<b style="color:{T.INK}">{T.money(sales[C.REVENUE].sum())}</b></div>'
                 f'<div class="ep-meta">Data version {data_id}</div>')
    T.html(''.join(lines))

view, _ = analytics._apply_filters(sales, sidebar_filters)
scope = agent.scope_text(sidebar_filters, sidebar_filters)
years_all = sorted(int(y) for y in view[C.YEAR].dropna().unique())
span = f'{years_all[0]}–{years_all[-1]}' if years_all else 'no years'
data_label = 'Uploaded: ' + ', '.join(uploaded.values()) if uploaded else 'Original E-Presso files'


def top_notices():
    """Upload banner and data-note link, shown under every masthead."""
    if uploaded:
        which = ', '.join(f'<b>{k.title()}</b> ({name})' for k, name in uploaded.items())
        T.note(f'<span class="ep-label ep-accent">Uploaded data in use</span><br>'
               f'{which} replaced the original. Sales revenue sum is now '
               f'<b>{T.money(sales[C.REVENUE].sum())}</b>. Remove the upload in the sidebar to go back.')
    elif data_changed:
        T.note('<span class="ep-label">Original data restored</span><br>All numbers recalculated.')


# =================================================================== overview
if section == SECTIONS[0]:
    total = analytics.get_total_revenue(sales, sidebar_filters)
    by_channel = analytics.get_revenue_by(sales, C.CHANNEL, sidebar_filters)
    growth = analytics.get_growth(sales, C.CHANNEL, sidebar_filters)
    month_share = analytics.get_revenue_by(sales, C.MONTH, sidebar_filters)

    # Deck sentence written from calculated results only.
    deck = 'Every figure on this page is calculated from the loaded files.'
    if not by_channel.error and by_channel.value:
        top = max(by_channel.value.items(), key=lambda kv: kv[1]['revenue'])
        deck = (f'{top[0]} carries {top[1]["share_pct"]:.1f}% of revenue in scope.' if len(by_channel.value) > 1
                else f'All revenue in scope is {top[0].lower()}.')
        if not growth.error and growth.value:
            first = years_all[0]
            moves = [f'{k} {"grew" if v["pct_change"] >= 0 else "fell"} {abs(v["pct_change"]):.1f}%'
                     for k, v in sorted(growth.value.items(), key=lambda kv: -kv[1]['pct_change'])]
            deck += f' Since {first}, ' + (' while '.join(moves) if len(moves) == 2 else ', '.join(moves)) + '.'
    T.masthead(f'E-Presso · Revenue report · {span}', f'Revenue, {span}', T.escape(deck))
    T.scope_bar([('Scope', scope), ('Data', data_label), ('Version', data_id)])
    top_notices()

    if total.error:
        st.error(total.error)
        st.stop()
    yearly = analytics.get_revenue_by(sales, C.YEAR, sidebar_filters)
    stats = []
    for name, v in sorted((by_channel.value or {}).items(), key=lambda kv: -kv[1]['revenue']):
        stats.append((name, T.money_short(v['revenue']), f'{v["share_pct"]:.1f}% share'))
    if not yearly.error and len(yearly.value or {}) > 1:
        ys = sorted(yearly.value, key=int)
        a, b = yearly.value[ys[0]]['revenue'], yearly.value[ys[-1]]['revenue']
        stats.append((f'Since {ys[0]}', f'{(b - a) / a * 100:+.1f}%' if a else 'n/a',
                      f'{ys[-1]} vs {ys[0]}'))
    if not month_share.error and month_share.value:
        pk = max(month_share.value.items(), key=lambda kv: kv[1]['revenue'])
        stats.append(('Peak month', MONTHS[int(pk[0]) - 1], f'{pk[1]["share_pct"]:.1f}% of revenue'))
    T.hero('Total revenue', T.money(total.value), f'{total.rows_used:,} line items · revenue, not profit', stats)

    # ---- Fig 1 + Fig 2: asymmetric pair
    left, right = st.columns([7, 5], gap='large')
    with left:
        T.figure_head(1, 'Revenue by year, by channel',
                      '<span class="ep-key ep-key-web"></span>Website &nbsp;'
                      '<span class="ep-key"></span>Brick &amp; mortar. Total labeled above each year.')
        if not yearly.error and yearly.value:
            yrs = sorted(yearly.value, key=int)
            fig = go.Figure()
            for ch in sorted(by_channel.value or {}, key=lambda c: T.channel_color(c) == T.ACCENT):
                part = analytics.get_revenue_by(sales, C.YEAR, {**sidebar_filters, C.CHANNEL: ch})
                vals = [(part.value or {}).get(y, {}).get('revenue', 0) for y in yrs] if not part.error else []
                fig.add_trace(go.Bar(x=yrs, y=vals, name=ch, marker=dict(color=T.channel_color(ch),
                                     line=dict(color=T.PAPER, width=1.5)),
                                     hovertemplate=f'{ch} · %{{x}}<br>$%{{y:,.0f}}<extra></extra>'))
            for i, y in enumerate(yrs):  # category axis: place by position, or '2025' is read as index 2025
                fig.add_annotation(x=i, y=yearly.value[y]['revenue'], text=T.money_short(yearly.value[y]['revenue']),
                                   showarrow=False, yshift=11, font=dict(family='JetBrains Mono', size=10, color=T.INK_2))
            fig.update_layout(barmode='stack', height=300, bargap=0.55, xaxis=dict(type='category'),
                              yaxis=dict(tickprefix='$', tickformat='~s'))
            st.plotly_chart(fig, width='stretch', config={'displayModeBar': False})
    with right:
        T.figure_head(2, 'Share by channel', 'Revenue in scope.')
        if not by_channel.error and by_channel.value:
            items = sorted(by_channel.value.items(), key=lambda kv: -kv[1]['revenue'])
            T.share_rule([(n, v['share_pct'], T.channel_color(n)) for n, v in items])
            T.table([{'Channel': n, 'Revenue': T.money(v['revenue']), 'Share': f'{v["share_pct"]}%'}
                     for n, v in items], numeric=('Revenue', 'Share'))

    # ---- Fig 3: full width
    T.figure_head(3, 'Monthly revenue, year over year',
                  'Each line is one year: older years in lighter gray, the latest in ink. November and December carry the year.')
    monthly = (view.dropna(subset=[C.YEAR, C.MONTH])
               .groupby([C.YEAR, C.MONTH])[C.REVENUE].sum().reset_index())
    if len(monthly):
        fig = go.Figure()
        yrs = sorted(monthly[C.YEAR].unique())
        colors = {}
        for i, y in enumerate(yrs):
            latest = i == len(yrs) - 1
            ramp = T.YEAR_RAMP[max(0, len(T.YEAR_RAMP) - (len(yrs) - 1) + i)] if not latest else T.INK
            colors[int(y)] = ramp
            part = monthly[monthly[C.YEAR] == y].sort_values(C.MONTH)
            fig.add_trace(go.Scatter(
                x=part[C.MONTH], y=part[C.REVENUE], mode='lines+markers' if latest else 'lines', name=str(int(y)),
                line=dict(color=ramp, width=2.25 if latest else 1.25),
                marker=dict(size=7, color=ramp, line=dict(color=T.PAPER, width=2)),
                hovertemplate=f'{int(y)} · %{{x}}<br>$%{{y:,.0f}}<extra></extra>'))
        last = monthly[monthly[C.YEAR] == yrs[-1]].sort_values(C.MONTH).iloc[-1]
        fig.add_annotation(x=last[C.MONTH], y=last[C.REVENUE], text=str(int(yrs[-1])), showarrow=False,
                           xanchor='left', xshift=8, font=dict(family='JetBrains Mono', size=11, color=T.INK))
        fig.update_layout(height=360, margin=dict(l=8, r=48, t=28, b=8), hovermode='x unified',
                          showlegend=len(yrs) > 1,
                          legend=dict(orientation='h', x=0, y=1.08, font=dict(size=11, color=T.INK_2)),
                          xaxis=dict(tickmode='array', tickvals=list(range(1, 13)), ticktext=MONTHS),
                          yaxis=dict(tickprefix='$', tickformat='~s'))
        st.plotly_chart(fig, width='stretch', config={'displayModeBar': False})

    # ---- Fig 4 + Fig 5: reversed asymmetric pair
    left, right = st.columns([5, 7], gap='large')
    with left:
        T.figure_head(4, 'Share of revenue by month', 'Denominator: all revenue in scope, all years combined.')
        if not month_share.error and month_share.value:
            ms = sorted(month_share.value.items(), key=lambda kv: int(kv[0]))
            vals = [v['share_pct'] for _, v in ms]
            peak = vals.index(max(vals))
            fig = go.Figure(go.Bar(
                x=[MONTHS[int(k) - 1] for k, _ in ms], y=vals, cliponaxis=False,
                marker=dict(color=[T.INK if i == peak else T.MUTED for i in range(len(vals))], cornerradius=1),
                text=[f'{v:.1f}%' if i == peak else '' for i, v in enumerate(vals)], textposition='outside',
                textfont=dict(family='JetBrains Mono', color=T.INK, size=11),
                hovertemplate='%{x}<br>%{y}% of revenue<extra></extra>'))
            fig.update_layout(height=300, bargap=0.45, yaxis=dict(ticksuffix='%'))
            st.plotly_chart(fig, width='stretch', config={'displayModeBar': False})
    with right:
        T.figure_head(5, 'Revenue by category',
                      'Revenue in scope, with the change from the first to the last year.')
        cats = analytics.get_revenue_by(sales, C.CATEGORY, sidebar_filters) if C.CATEGORY in sales.columns else None
        cgrowth = analytics.get_growth(sales, C.CATEGORY, sidebar_filters) if C.CATEGORY in sales.columns else None
        if cats is not None and not cats.error and cats.value:
            items = sorted(cats.value.items(), key=lambda kv: kv[1]['revenue'])
            change = {} if cgrowth is None or cgrowth.error else cgrowth.value
            labels = [f"{T.money_short(v['revenue'])}   "
                      + (f"{change[k]['pct_change']:+.1f}%" if k in change else '') for k, v in items]
            fig = go.Figure(go.Bar(
                y=[k for k, _ in items], x=[v['revenue'] for _, v in items], orientation='h',
                marker=dict(color=T.INK, cornerradius=1),
                text=labels, textposition='outside', cliponaxis=False,
                textfont=dict(family='JetBrains Mono, monospace', size=11, color=T.INK_2),
                hovertemplate='%{y}<br>$%{x:,.0f}<extra></extra>'))
            fig.update_layout(height=300, margin=dict(l=8, r=130, t=12, b=8), bargap=0.55,
                              xaxis=dict(visible=False), yaxis=dict(tickfont=dict(color=T.INK, size=12)))
            st.plotly_chart(fig, width='stretch', config={'displayModeBar': False})
            if cgrowth is not None and cgrowth.error:
                st.caption(f'Change not shown: {cgrowth.error}')

    # ---- Fig 6: stores, full width
    if C.STORE in sales.columns:
        stores = analytics.get_revenue_by(sales, C.STORE, sidebar_filters)
        web = next((v for k, v in (stores.value or {}).items() if k.startswith('SH00')), None)
        cap = (f"The website is {web['share_pct']}% of revenue in scope, so it is hidden by default "
               'to keep the stores readable.') if web else 'Store revenue in scope.'
        T.figure_head(6, 'Revenue by location', cap + ' Each bar shows revenue and the change since the first year.')
        with_web = st.checkbox('Include the website (SH00)', value=False)
        if not stores.error and stores.value:
            rows = [(k, v['revenue']) for k, v in stores.value.items()
                    if with_web or not k.startswith('SH00')]
            if not rows:
                st.caption('Only the website is in scope. Tick the box to show it.')
            else:
                rows.sort(key=lambda r: r[1])
                sg = analytics.get_growth(sales, C.STORE, sidebar_filters)
                chg = {} if sg.error else sg.value
                fig = go.Figure(go.Bar(
                    y=[r[0] for r in rows], x=[r[1] for r in rows], orientation='h',
                    marker=dict(color=[T.ACCENT if r[0].startswith('SH00') else T.INK for r in rows], cornerradius=1),
                    text=[f"{T.money_short(r[1])}   " + (f"{chg[r[0]]['pct_change']:+.1f}%" if r[0] in chg else '')
                          for r in rows], textposition='outside', cliponaxis=False,
                    textfont=dict(family='JetBrains Mono, monospace', size=10, color=T.INK_2),
                    hovertemplate='%{y}<br>$%{x:,.0f}<extra></extra>'))
                fig.update_layout(height=max(220, 24 * len(rows) + 40), bargap=0.5,
                                  margin=dict(l=8, r=120, t=8, b=8),
                                  xaxis=dict(visible=False),
                                  yaxis=dict(gridcolor='rgba(0,0,0,0)', tickfont=dict(color=T.INK, size=11)))
                st.plotly_chart(fig, width='stretch', config={'displayModeBar': False})
    T.colophon([('Source', data_label), ('Method', 'Sum of the Revenue column after joining Sales to '
                'Stores, Products and Categories; every join checked'), ('Caveat', analytics.REVENUE_CAVEAT)])

# ============================================================= data + quality
elif section == SECTIONS[1]:
    T.masthead('E-Presso · Data & quality', 'The data behind the numbers',
               'What was loaded, what one row of each table means, how the tables were joined, '
               'and anything that looked wrong.')
    T.scope_bar([('Data', data_label), ('Version', data_id)])
    top_notices()

    T.section('Data issues found')
    if notes:
        T.html('<ul style="margin:0 0 0.5rem 1.1rem">' +
               ''.join(f'<li>{T.escape(p)}</li>' for p in notes) + '</ul>')
    else:
        T.html('<p>No missing values, unmatched keys, or duplicates found in the loaded data.</p>')
    dq = analytics.data_quality_report(sales).value
    T.html(f'<p class="ep-meta">Joined sales table: {dq["rows"]:,} rows · {dq["duplicate_rows"]} duplicate rows · '
           f'{len(dq["columns_with_missing"])} columns with blanks</p>')

    T.section('Source tables')
    rows = []
    for key, (origin, name, _) in sources.items():
        df = built['tables'].get(key)
        if df is None:
            continue
        prof = analytics.profile_table(df)
        rows.append({'Table': key.title(), 'File': name, 'Origin': origin, 'Rows': f'{prof["rows"]:,}',
                     'Columns': prof['columns'], 'Duplicate rows': prof['duplicate_rows'],
                     'One row =': C.SOURCES[key]['grain']})
    T.table(rows, numeric=('Rows', 'Columns', 'Duplicate rows'))
    for name, df in files.items():
        with st.expander(f'Preview · {name}'):
            st.dataframe(df.head(20), hide_index=True)
            prof = analytics.profile_table(df)
            a, b = st.columns(2)
            a.dataframe(prof['missing'])
            b.dataframe(prof['dtypes'])

    T.section('Merge checks')
    T.html('<p class="ep-cap" style="color:#77766F">Every join is checked: if rows or the revenue sum '
           'change, the join duplicated or dropped revenue.</p>')
    if built['merges']:
        T.table([{'Merge': m['merge'], 'Rows before': f'{m["rows_before"]:,}', 'Rows after': f'{m["rows_after"]:,}',
                  'Revenue before': T.money(m['sum_before']), 'Revenue after': T.money(m['sum_after']),
                  'Unmatched': m.get('unmatched_rows', 0), 'Changed?': 'yes' if m['changed'] else 'no'}
                 for m in built['merges']],
                numeric=('Rows before', 'Rows after', 'Revenue before', 'Revenue after', 'Unmatched'))
    T.colophon([('Source', data_label), ('Grain', 'Sales: one store x one product x one month'),
                ('Rule', 'Lookup tables must have one row per key, or revenue is duplicated')])

# ================================================================ validation
elif section == SECTIONS[2]:
    T.masthead('E-Presso · Validation', 'Figures to check against Power BI',
               'Always the full dataset. Sidebar filters do not apply on this page.')
    T.scope_bar([('Scope', 'All data, filters ignored'), ('Data', data_label), ('Version', data_id)])
    top_notices()
    v_total = analytics.get_total_revenue(sales)
    v_chan = analytics.get_revenue_by(sales, C.CHANNEL)
    v_year = analytics.get_revenue_by(sales, C.YEAR)
    T.hero('Total revenue, all years', T.money(v_total.value) if not v_total.error else 'n/a',
           f'{v_total.rows_used:,} line items', [
               (k, T.money(v['revenue']), f'{v["share_pct"]}%') for k, v in (v_chan.value or {}).items()])
    left, right = st.columns([5, 7], gap='large')
    with left:
        T.section('By year')
        T.table([{'Year': k, 'Revenue': T.money(v['revenue']), 'Share': f'{v["share_pct"]}%'}
                 for k, v in sorted((v_year.value or {}).items())], numeric=('Revenue', 'Share'))
    with right:
        T.section('By month and year')
        piv = sales.pivot_table(index=C.MONTH, columns=C.YEAR, values=C.REVENUE, aggfunc='sum')
        T.table([{'Month': MONTHS[int(m) - 1], **{str(int(y)): T.money(piv.loc[m, y]) for y in piv.columns}}
                 for m in piv.index], numeric=tuple(str(int(y)) for y in piv.columns))
    T.html('<p class="ep-meta">Independent check: <code>python docs/independent_check.py</code> '
           'recomputes these from the raw Sales file without any app code.</p>')
    T.colophon([('Source', data_label), ('Compare with', 'Our E-Presso Power BI report'),
                ('Caveat', analytics.REVENUE_CAVEAT)])

# ================================================================= assistant
else:
    try:  # no secrets file at all is fine: rules-based mode
        key = st.secrets.get('GEMINI_API_KEY')
        model = st.secrets.get('GEMINI_MODEL', 'gemini-3.1-flash-lite')
    except Exception:
        key, model = None, None
    mode = 'llm' if key else 'rules'
    st.session_state.setdefault('n_questions', 0)
    st.session_state.setdefault('history', [])
    left_q = MAX_QUESTIONS - st.session_state['n_questions']
    T.masthead('E-Presso · Analyst', 'Ask the data',
               T.escape(agent.CAPABILITIES) + ' Every number in an answer comes from a calculation '
               'on the loaded data, listed under Method.')
    T.scope_bar([('Mode', f'Gemini · {model}' if key else 'Rules-based (no API key)'),
                 ('Sidebar scope', scope), ('Questions left', f'{left_q} of {MAX_QUESTIONS}')])
    top_notices()

    def safe(text):
        """Two $ signs on a line render as a math formula, so escape them,
        except inside ``` code blocks, where a backslash would show."""
        parts = str(text).split('```')
        return '```'.join(p if i % 2 else p.replace('$', '\\$') for i, p in enumerate(parts))

    def split_parts(text):
        """Split a model answer on its **Findings:** / **Interpretation:** / **Next steps:** labels."""
        pieces = re.split(r'\*{0,2}(Findings|Interpretation|Next steps)\s*:\s*\*{0,2}', text)
        if len(pieces) < 3:
            return [('Answer', text.strip())]
        return [(pieces[i], pieces[i + 1].strip()) for i in range(1, len(pieces) - 1, 2)]

    def fmt(key, val):
        if not isinstance(val, (int, float)) or isinstance(val, bool):
            return str(val)
        if 'pct' in key or 'share' in key:
            return f'{val:+.2f}%' if 'change' in key else f'{val}%'
        if 'revenue' in key or key == 'value':
            return T.money(val)
        return f'{val:,}' if isinstance(val, int) else f'{val:,.3f}'.rstrip('0').rstrip('.')

    def value_rows(value):
        """The tool result as table rows (same numbers as the Method log, just readable)."""
        if isinstance(value, dict) and value and all(isinstance(v, dict) for v in value.values()):
            items = list(value.items())
            if all('pct_change' in v for _, v in items):  # growth: biggest decline first, so the answer leads
                items.sort(key=lambda kv: kv[1]['pct_change'])
            return [{'': str(k), **{c.replace('_', ' ').title(): fmt(c, x) for c, x in v.items()}}
                    for k, v in items]
        if isinstance(value, dict):
            return [{'Measure': k.replace('_', ' ').title(), 'Value': fmt(k, v)} for k, v in value.items()
                    if not isinstance(v, (dict, list))]
        return []

    def part(label, body, rows=None):
        a, b = st.columns([1.4, 5], gap='medium')
        a.markdown(f'<div class="ep-label" style="padding-top:0.3rem">{label}</div>', unsafe_allow_html=True)
        with b:
            st.markdown(safe(body))
            if rows:
                T.table(rows[:25], numeric=tuple(c for c in rows[0] if c not in ('', 'Measure')))
                if len(rows) > 25:
                    st.caption(f'{len(rows) - 25} more rows in the Method log.')

    if not st.session_state['history']:
        T.html('<p class="ep-meta" style="margin-top:1.5rem">Try: “Which store had the greatest percentage '
               'revenue decline?” · “What percent of revenue came from the website in 2026?” · '
               '“Does higher customer satisfaction cause higher revenue?”</p>')
    for n, item in enumerate(st.session_state['history'], start=1):
        ans = item['answer']
        T.html(f'<div class="ep-entry"><div class="ep-label">Q.{n:02d} · {T.escape(ans["mode"])}</div>'
               f'<div class="ep-q">{T.escape(item["question"])}</div>'
               f'<div class="ep-meta">Scope: {T.escape(ans["scope"])}</div></div>')
        if ans.get('note'):
            T.note(T.escape(ans['note']))
        if ans['mode'].startswith('Language model'):
            for label, body in split_parts(ans['findings']):
                part(label, body)
        else:
            text = ans['findings'].split('```')[0].rstrip().rstrip(':') + '.' if '```' in ans['findings'] \
                else ans['findings']
            log = ans['tool_log'][-1]['result'] if ans['tool_log'] else {}
            rows = value_rows(log.get('value')) if not log.get('error') else []
            scalar = log.get('value') if isinstance(log.get('value'), (int, float)) else None
            if scalar is not None:
                text += f"\n\n**{T.money(scalar)}** · {log.get('rows_used', 0):,} rows used"
            part('Findings', text, rows)
            if ans['interpretation']:
                part('Interpretation', ans['interpretation'])
            if ans['next_steps']:
                part('Next steps', ans['next_steps'])
        with st.expander(f"Method · {len(ans['tool_log'])} tool call{'s' if len(ans['tool_log']) != 1 else ''}"):
            st.json(ans['tool_log'] or 'No tool was called.')

    question = st.chat_input('Ask a question about the loaded data')
    if question:
        if st.session_state['n_questions'] >= MAX_QUESTIONS:
            st.warning('Question limit reached for this session. Reload the page to start over.')
        else:
            st.session_state['n_questions'] += 1
            with st.spinner('Calculating…'):
                answer = agent.answer_question(question, sales, mode=mode,
                                               sidebar_filters=sidebar_filters,
                                               api_key=key, model=model or 'gemini-3.1-flash-lite',
                                               survey=built['survey'])
            st.session_state['history'].append({'question': question, 'answer': answer})
            st.rerun()
