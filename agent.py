"""Assistant: a tool registry, a dispatcher, and two routers.
A router (rules or a language model) only CHOOSES a tool and its arguments from
fixed options. Our code RUNS the tool. Nothing here executes model-written code,
and no tool changes the loaded data."""
from __future__ import annotations

import json
import re

import analytics
import config as C
from analytics import ToolResult

# --------------------------------------------------------------- registry
# The ONLY things the assistant may do.
TOOLS = {
    'get_total_revenue': {
        'fn': analytics.get_total_revenue,
        'params': {'filters'},
        'description': 'Total revenue, optionally filtered by year, month, store, channel, category, or product.',
    },
    'get_revenue_by': {
        'fn': analytics.get_revenue_by,
        'params': {'group', 'filters'},
        'description': 'Revenue and % share broken out by channel, store, category, product, year, or month.',
    },
    'get_growth': {
        'fn': analytics.get_growth,
        'params': {'group', 'filters'},
        'description': 'Percent change in revenue from the first year to the last year, per store, channel, category, or product. Always uses the first and last year in scope.',
    },
    'get_monthly_share': {
        'fn': analytics.get_monthly_share,
        'params': {'year', 'filters'},
        'description': ("Each month's revenue as a percent of one year's total. With no year, "
                        "each calendar month as a percent of the all-years total (Power BI's "
                        "'% of grand total'), plus the average of the yearly shares."),
    },
    'get_satisfaction_vs_revenue': {
        'fn': analytics.get_satisfaction_vs_revenue,
        'params': {'filters'},
        'needs_survey': True,
        'description': 'Correlation between customer satisfaction scores and yearly store revenue.',
    },
    'data_quality_report': {
        'fn': analytics.data_quality_report,
        'params': set(),
        'description': 'Duplicate rows and missing values in the loaded data.',
    },
}

CAPABILITIES = ('I can calculate: total revenue; revenue by channel, store, category, product, '
                'year, or month; growth or decline between the first and last year; monthly share '
                'of a year; satisfaction vs. revenue correlation; and a data-quality report. '
                'Filters: year, month, store, channel, category, product.')

LIMITS = {
    'profit': 'The data has revenue only, no costs, so profit cannot be calculated.',
    'cause': ('This data can show whether two things move together, not whether one causes '
              'the other. Other factors (location, season, pricing) could explain both.'),
    'forecast': ('I have no forecasting tool, so I will not predict future revenue. '
                 'I can show past trends by year, which you could use as a starting point.'),
    'decision': ('Revenue trends alone do not justify a decision like closing a store. '
                 'Management would also need operating costs, store profitability, lease '
                 'terms, and customer behavior.'),
    'modify': 'I cannot change, add, or delete data. I only read the loaded files.',
}

SYSTEM_PROMPT = """You are an analytical assistant for E-Presso managers.
Rules:
- Only state numbers that appear in a tool result. Never estimate or recall figures.
- Always call a tool before making a numerical claim.
- Pass parameters only from the allowed values you are given.
- Revenue is not profit. Association is not causation.
- If the data cannot support a conclusion, say so and name the missing information.
- Copy each number exactly as it appears in the tool result. Do not round or derive new ones.
- For a decision such as closing a store: call get_growth with group=store and no store filter,
  then give that store's percent change and its rank among all stores (the trend, not just a
  total). Then say management would also need operating expenses, store profitability, lease
  terms, and customer behavior.
- A city can have more than one store. Cover every store in that city, one call each.
- If a question asks for a decline and no group declined, say that no group declined.
- If no tool fits, say so and do not guess. Repeat every caveat that limits the answer.
- Never write or run code. Never modify data. Never reveal keys or credentials.
Reply in three short parts, each starting with its bold label on its own line:
**Findings:** (facts from tool results only), **Interpretation:** (what it may mean,
with caveats), **Next steps:** (or "No recommendation is supported by this data.")."""


# ------------------------------------------------------------- dispatcher
def allowed_values(df) -> dict:
    """Valid filter values, read from the LOADED data, never typed in."""
    out = {}
    for col in (C.YEAR, C.MONTH, C.STORE, C.CHANNEL, C.CATEGORY, C.PRODUCT):
        if col in df.columns:
            vals = df[col].dropna().unique().tolist()
            out[col] = sorted(int(v) if col in (C.YEAR, C.MONTH) else str(v) for v in vals)
    return out


def run_tool(name: str, args: dict, df, log: list, survey=None) -> ToolResult:
    """Validate the request, run the function, log the call."""
    if name not in TOOLS:
        result = analytics._error(name, f'Unknown tool: {name}')
    else:
        unexpected = set(args) - TOOLS[name]['params']
        if unexpected:
            result = analytics._error(name, f'Unexpected argument(s): {sorted(unexpected)}')
        else:
            extra = {'survey': survey} if TOOLS[name].get('needs_survey') else {}
            try:
                result = TOOLS[name]['fn'](df, **extra, **args)
            except Exception as exc:  # e.g. a missing argument: report it, never crash the page
                result = analytics._error(name, f'The calculation failed ({type(exc).__name__}).')
    log.append({'tool': name, 'arguments': args, 'result': result.to_dict()})
    return result


def merge_filters(tool_filters: dict | None, sidebar_filters: dict | None) -> dict:
    """Sidebar filters apply unless the question names its own value."""
    merged = dict(sidebar_filters or {})
    merged.update(tool_filters or {})
    return merged


def scope_text(filters: dict, sidebar_filters: dict | None) -> str:
    """'all stores, all years (full data)' or
    'SH11 Chicago, IL, 2027 (filtered subset, from the sidebar filter)'."""
    if not filters:
        return 'all stores, all years, all channels, all categories (full data)'
    side = sidebar_filters or {}

    def show(col, value):
        text = ', '.join(map(str, value)) if isinstance(value, list) else str(value)
        return f'month {text}' if col == C.MONTH else text

    what = ', '.join(show(k, v) for k, v in filters.items())
    from_side = [k for k, v in filters.items() if side.get(k) == v]
    source = ('from the question' if not from_side else 'from the sidebar filter'
              if len(from_side) == len(filters) else 'from the sidebar filter and the question')
    replaced = [k for k, v in filters.items() if k in side and side[k] != v]
    extra = f'; the question replaced the sidebar {", ".join(replaced)} filter' if replaced else ''
    return f'{what} (filtered subset, {source}{extra})'


# ----------------------------------------------------------- rules router
MONTH_NAMES = ('january', 'february', 'march', 'april', 'may', 'june', 'july', 'august',
               'september', 'october', 'november', 'december')
MONTH_ABBR = tuple(m[:3] for m in MONTH_NAMES) + ('sept',)
GENERIC_WORDS = ('all', 'each', 'every', 'store', 'stores', 'product', 'products', 'category',
                 'categories', 'channel', 'channels', 'company', 'total', 'revenue', 'sales')
# Things the data or the tools do not cover. Without this, "revenue by region" would
# fall through to the company total.
UNSUPPORTED = (r'\b(regions?|markets?|states?|quarters?|q[1-4]|customers?|employees?|staff|'
               r'managers?|units?|quantity|quantities|prices?|costs?|expenses?|weeks?|days?)\b')


def _find_filters(q: str, df, question: str = '') -> dict:
    """Pull filter values out of the question by matching the loaded data.
    Several matches ('2027 and 2028') give a list, so none is silently dropped."""
    found = {}
    allowed = allowed_values(df)
    for col in (C.YEAR, C.CHANNEL, C.CATEGORY, C.STORE):
        hits = [v for v in allowed.get(col, []) if re.search(rf'\b{re.escape(str(v).lower())}\b', q)]
        if hits:
            found[col] = hits[0] if len(hits) == 1 else hits
    # A year the data does not have stays in, so the tool says "not found" instead of
    # quietly answering for all years.
    years = [int(y) for y in re.findall(r'\b(?:19|20)\d\d\b', q)]
    if C.YEAR in allowed and any(y not in allowed[C.YEAR] for y in years):
        found[C.YEAR] = years[0] if len(years) == 1 else years
    if C.STORE not in found and C.STORE in allowed:
        found.update(_match_store(q, allowed[C.STORE]))
    months = [i for i, m in enumerate(MONTH_NAMES, 1) if re.search(
        r'\b(in|of|for) may\b|\bmay \d{4}\b' if m == 'may' else rf'\b{m[:3]}(?:{m[3:]})?\b', q)]
    if months and C.MONTH in allowed:
        found[C.MONTH] = months[0] if len(months) == 1 else months
    # 'Base Model' is three products (labels add the category), so match the name before ' ('
    products = [p for p in allowed.get(C.PRODUCT, [])
                if re.search(rf"\b{re.escape(p.split(' (')[0].lower())}\b", q)]
    if products:
        found[C.PRODUCT] = products[0] if len(products) == 1 else products
    return found


def _unknown_name(question: str, df) -> str | None:
    """'Revenue in Boston': a capitalized name after in/at/for/from that matches nothing
    loaded. Returned so it can go to the tool, which says 'not found', instead of the
    answer quietly covering the whole company."""
    known = ' '.join(str(v) for vals in allowed_values(df).values() for v in vals).lower()
    for word in re.findall(r'\b(?:in|at|for|from)\s+(?:the\s+)?([A-Z][a-z]+)', question):
        w = word.lower()
        if w in known or w in MONTH_NAMES + GENERIC_WORDS or w in MONTH_ABBR or _normalize(w) != w:
            continue  # a month ('Jan') or a channel word ('Online') is not a store name
        return word
    return None


def _match_store(q: str, stores: list) -> dict:
    """Store labels look like 'SH11 Chicago, IL'. Match on store ID or city.
    One match gives one store. Several (e.g. 'Denver and Seattle', or Orlando,
    which has two stores) give a list, so the answer covers each of them."""
    hits = [lab for lab in stores if re.search(rf'\b{re.escape(lab.split()[0].lower())}\b', q)]
    hits += [lab for lab in stores if ',' in lab and lab not in hits and re.search(
        rf"\b{re.escape(lab.split(' ', 1)[1].split(',')[0].lower())}\b", q)]
    if not hits:
        return {}
    return {C.STORE: hits[0] if len(hits) == 1 else hits}


def _find_group(q: str, filters: dict) -> str | None:
    """The first breakdown word in the question, skipping one already used as a filter,
    so 'top product in the Chicago store' groups by product, not store."""
    for word, col in (('channel', C.CHANNEL), ('store', C.STORE), ('location', C.STORE),
                      ('city', C.STORE), ('cities', C.STORE), ('categor', C.CATEGORY),
                      ('product', C.PRODUCT), ('month', C.MONTH), ('year', C.YEAR),
                      ('annual', C.YEAR)):
        if word in q and col not in filters:
            return col
    return None


def _normalize(question: str) -> str:
    """Everyday words for the two channels, so 'online' does not fall through to all revenue."""
    q = re.sub(r'brick[\s-]*(and|&|n)[\s-]*mortar|\bphysical\b|\bin-store\b|\bretail\b',
               'brick & mortar', question.lower())
    return re.sub(r'\bonline\b|\be-?commerce\b|\bweb site\b', 'website', q)


def rules_router(question: str, df):
    """Option B. Returns (limit_key, tool_name, args). Any part may be None."""
    q = _normalize(question)
    # Refuse requests to change data, not read questions that use the word:
    # "Delete Chicago from the data" yes; "latest update on 2027 sales", "remove X and show Y" no.
    if re.search(r'\b(delete|remove|overwrite|edit|modify|update|alter|change)\b[^.?!]*\b(data|rows?|'
                 r'values?|numbers?|figures?|files?|records?|revenue|sales|stores?)\b', q) and \
            not re.search(r'\b(show|list|display|what|how|which|compare)\b', q):
        return 'modify', None, None
    limit = None
    if re.search(r'\bshould\b|\bclos(e|ing|ure)\b|\bshut|\bopen a\b|\brecommend|\bworth\b|'
                 r'\binvest\b|\bexpand', q):
        limit = 'decision'
    elif 'profit' in q or 'margin' in q:
        limit = 'profit'
    elif re.search(r'\bcaus|\bbecause\b|\bdrive|\bwhy\b|\bimpact|\baffect|\beffect|\bleads? to\b|'
                   r'\breason', q):
        limit = 'cause'
    elif re.search(r'forecast|predict|next year|will .*(revenue|sales)|\b20[3-9]\d\b', q) and \
            not any(str(y) in q for y in allowed_values(df).get(C.YEAR, [])):
        limit = 'forecast'

    if limit != 'decision' and any(w in q for w in ('missing', 'duplicate', 'quality', 'blank',
                                                    'clean', 'error', 'issue', 'problem', 'dirty')):
        return limit, 'data_quality_report', {}
    if 'satisf' in q or 'survey' in q:
        return limit, 'get_satisfaction_vs_revenue', {'filters': _find_filters(q, df)}
    if not limit and re.search(UNSUPPORTED, q):
        return None, None, None

    filters = _find_filters(q, df)
    if limit == 'decision' and C.YEAR in filters:  # "close Chicago before 2030": a future year is no evidence
        loaded = allowed_values(df).get(C.YEAR, [])
        asked = filters.pop(C.YEAR)
        years = [y for y in (asked if isinstance(asked, list) else [asked]) if y in loaded]
        if years:
            filters[C.YEAR] = years[0] if len(years) == 1 else years
    if limit == 'forecast':
        filters.pop(C.YEAR, None)
        return limit, 'get_revenue_by', {'group': C.YEAR, 'filters': filters}
    unknown = _unknown_name(question, df)
    if unknown and C.STORE not in filters and limit != 'decision':
        filters[C.STORE] = unknown
    group = _find_group(q, filters)

    wants_growth = any(w in q for w in ('grow', 'grew', 'decline', 'drop', 'increase', 'decrease',
                                        'trend', 'change', 'fell', 'fall', 'shrink', 'shrank',
                                        'rose', 'rise'))
    one_year = C.YEAR in filters and not isinstance(filters[C.YEAR], list)
    how_did = re.search(r'how (did|is|are|has)|perform|doing|compare', q)
    if limit == 'decision' and group is None and not one_year and C.STORE in filters:
        # "Should we close Chicago?": rank that store against every store, not just its own trend
        focus = filters.pop(C.STORE)
        return limit, 'get_growth', {'group': C.STORE, 'filters': filters, '_focus': focus}
    if group is None and not one_year and (limit == 'decision' or how_did or wants_growth):
        for col in (C.STORE, C.PRODUCT, C.CATEGORY, C.CHANNEL):  # that store's (or item's) trend
            if col in filters:
                return limit, 'get_growth', {'group': col, 'filters': filters}
    if re.search(r'percent|share|%|portion|proportion', q) and group != C.MONTH and not wants_growth:
        # "What percent came from the website in 2026?" -> breakdown, so the share has a denominator
        for col in (C.CHANNEL, C.CATEGORY, C.PRODUCT, C.STORE, C.MONTH):
            if col in filters or group == col:
                filters.pop(col, None)
                if col == C.MONTH and one_year:
                    return limit, 'get_monthly_share', {'year': filters.pop(C.YEAR), 'filters': filters}
                return limit, 'get_revenue_by', {'group': col, 'filters': filters}
    if wants_growth and group not in (None, C.YEAR, C.MONTH):
        return limit, 'get_growth', {'group': group, 'filters': filters}
    if wants_growth and group != C.MONTH:  # "Has revenue grown?": show every year
        if one_year:
            filters.pop(C.YEAR)
        return limit, 'get_revenue_by', {'group': C.YEAR, 'filters': filters}
    if group == C.MONTH and one_year:
        return limit, 'get_monthly_share', {'year': filters.pop(C.YEAR), 'filters': filters}
    if group == C.MONTH and C.YEAR not in filters and re.search(r'percent|share|%|portion', q):
        return limit, 'get_monthly_share', {'year': None, 'filters': filters}
    if group:
        return limit, 'get_revenue_by', {'group': group, 'filters': filters}
    for col, value in filters.items():  # "Compare 2027 and 2028 revenue", "How did Orlando do?"
        if isinstance(value, list):
            return limit, 'get_revenue_by', {'group': col, 'filters': filters}
    if limit == 'decision':  # no store named: still give the evidence
        return limit, 'get_revenue_by', {'group': C.YEAR, 'filters': filters}
    if unknown or (how_did and filters) or any(w in q for w in (
            'revenue', 'sales', 'sold', 'earn', 'generate', 'make', 'profit', 'total', 'income',
            'how much')):
        return limit, 'get_total_revenue', {'filters': filters}
    return limit, None, None


# ------------------------------------------------------------- LLM router

# Tried in order when the chosen model errors (busy server, per-model quota).
BACKUP_MODELS = ('gemini-3.5-flash-lite', 'gemini-3.6-flash')


def _generate_with_retry(client, model, contents, cfg, tries=2, wait=1.5):
    """Call Gemini. If Google's server is busy (a 5xx ServerError), wait and try again once.

    Free-tier models are often overloaded for a second or two. Other errors
    (bad key, quota) are not retried: they go straight to the rules fallback.
    """
    import time
    from google.genai import errors
    for attempt in range(tries):
        try:
            return client.models.generate_content(model=model, contents=contents, config=cfg)
        except errors.ServerError:
            if attempt == tries - 1:
                raise
            time.sleep(wait * (attempt + 1))


def llm_answer(question: str, df, api_key: str, model: str, sidebar_filters: dict | None,
               log: list, survey=None) -> dict:
    """Option A: Gemini picks tools via function calling. Our code runs them.
    Raises on any API problem so the caller can fall back to rules."""
    from google import genai
    from google.genai import types

    allowed = allowed_values(df)
    filter_schema = {'type': 'OBJECT', 'properties': {
        col: ({'type': 'INTEGER', 'description': f'One of {vals}'} if col in (C.YEAR, C.MONTH) else
              {'type': 'STRING', 'enum': vals}) for col, vals in allowed.items() if vals}}
    groups = [c for c in (C.CHANNEL, C.STORE, C.CATEGORY, C.PRODUCT, C.YEAR, C.MONTH)
              if c in df.columns]
    param_schemas = {
        'filters': filter_schema,
        'group': {'type': 'STRING', 'enum': groups},
        'year': {'type': 'INTEGER', 'description': f'One of {allowed.get(C.YEAR, [])}'},
    }
    decls = [types.FunctionDeclaration(
        name=n, description=t['description'],
        parameters={'type': 'OBJECT', 'properties': {p: param_schemas[p] for p in t['params']}}
        if t['params'] else None) for n, t in TOOLS.items()]

    client = genai.Client(api_key=api_key)
    cfg = types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT + f'\nSidebar filters currently applied: '
                                           f'{sidebar_filters or "none"}.',
        tools=[types.Tool(function_declarations=decls)],
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True))
    contents = [types.Content(role='user', parts=[types.Part(text=question)])]

    for _ in range(4):  # at most 4 rounds of tool calls per question
        resp = _generate_with_retry(client, model, contents, cfg)
        calls = resp.function_calls or []
        if not calls:
            return {'text': resp.text or 'The model returned no text.', 'used_tools': bool(log)}
        contents.append(resp.candidates[0].content)
        for call in calls:
            args = dict(call.args or {})
            if 'filters' in TOOLS.get(call.name, {}).get('params', set()):
                args['filters'] = merge_filters(args.get('filters'), sidebar_filters)
            result = run_tool(call.name, args, df, log, survey)
            contents.append(types.Content(role='user', parts=[types.Part.from_function_response(
                name=call.name, response={'result': json.loads(json.dumps(result.to_dict(),
                                                                          default=str))})]))
    return {'text': 'Stopped after too many tool calls.', 'used_tools': bool(log)}


# ------------------------------------------------------------ formatting
def _headline(result: ToolResult) -> str:
    """One plain sentence on top of the raw numbers. Uses only the tool result."""
    v = result.value
    if result.tool == 'get_growth' and v:
        ranked = sorted(v.items(), key=lambda kv: kv[1]['pct_change'])
        low, high = ranked[0], ranked[-1]
        partial = next((c for c in result.caveats if c.startswith('Partial year')), '')
        warn = f' Caution: {partial}' if partial else ''
        if len(v) == 1:
            return f"{low[0]}: {low[1]['pct_change']:+.2f}% from first to last year.{warn}"
        if high[1]['pct_change'] < 0:
            return (f"Every group declined. Largest decline: {low[0]} ({low[1]['pct_change']:+.2f}%). "
                    f"Smallest decline: {high[0]} ({high[1]['pct_change']:+.2f}%).{warn}")
        if low[1]['pct_change'] >= 0:
            return (f"Largest growth: {high[0]} ({high[1]['pct_change']:+.2f}%). No group declined; "
                    f"smallest growth: {low[0]} ({low[1]['pct_change']:+.2f}%).{warn}")
        return (f"Largest decline: {low[0]} ({low[1]['pct_change']:+.2f}%). "
                f"Largest growth: {high[0]} ({high[1]['pct_change']:+.2f}%).{warn}")
    if result.tool == 'get_monthly_share' and v:
        ranked = sorted(v.items(), key=lambda kv: kv[1]['revenue'])
        return (f"Highest month: {ranked[-1][0]} ({ranked[-1][1]['share_pct']}% of {'the year' if 'avg_share_of_own_year_pct' not in ranked[-1][1] else 'all-years revenue'}). "
                f"Lowest: {ranked[0][0]} ({ranked[0][1]['share_pct']}%).")
    if result.tool == 'get_revenue_by' and v:
        top = max(v.items(), key=lambda kv: kv[1]['revenue'])
        low = min(v.items(), key=lambda kv: kv[1]['revenue'])
        total = f"Total in scope: ${sum(x['revenue'] for x in v.values()):,.2f}."
        if len(v) == 1:
            return total
        return (f"{total} Highest: {top[0]} (${top[1]['revenue']:,.2f}, {top[1]['share_pct']}%). "
                f"Lowest: {low[0]} (${low[1]['revenue']:,.2f}, {low[1]['share_pct']}%).")
    if result.tool == 'get_satisfaction_vs_revenue':
        return f"Correlation r = {v['pearson_r']} across {v['store_years']} store-years."
    return ''


def _focus_rank(result: ToolResult, focus) -> str:
    """Where the named store(s) sit among all stores, ranked from largest decline."""
    ranked = sorted(result.value.items(), key=lambda kv: kv[1]['pct_change'])
    lines = []
    for name in (focus if isinstance(focus, list) else [focus]):
        pos = next((i for i, (k, _) in enumerate(ranked, 1) if k == name), None)
        if pos:
            pct = result.value[name]['pct_change']
            lines.append(f'{name}: {pct:+.2f}% from first to last year, rank {pos} of '
                         f'{len(ranked)} stores (1 = largest decline).')
        else:
            lines.append(f'{name} has no revenue in both the first and last year, so it has no '
                         'growth figure to rank.')
    return ' '.join(lines)


NO_DATA_SCOPE = 'no data used (no calculation was run)'
NO_INTERPRETATION = 'No calculation supports an interpretation here.'
NO_RECOMMENDATION = 'No recommendation is supported by this data.'


def _fmt_value(result: ToolResult) -> str:
    v = result.value
    if isinstance(v, float):
        return f'${v:,.2f}'
    return json.dumps(v, indent=1, default=str)


def number_check(text: str, log: list) -> tuple[int, list]:
    """(numbers checked, numbers that match no tool result), at the precision written.
    Whole numbers up to 12 are skipped: they are usually counts or months in a sentence.
    Plain calendar years (2025, not $2,025) are dates, not claims, so they are skipped too.
    '$7.18 million' and '7.2M' are scaled first. A number matches if a result rounds to it."""
    known = [float(n) for n in re.findall(r'\d+(?:\.\d+)?', json.dumps(log, default=str))]
    checked, flagged = 0, []
    for dollar, raw, unit in re.findall(r'(\$?)(\d[\d,]*(?:\.\d+)?)\s*(million|billion|thousand|[mbk]\b)?',
                                        text, re.I):
        scale = SCALES.get(unit.lower()[:1], 1)
        number = float(raw.replace(',', '').rstrip('.') or 0) * scale
        places = len(raw.split('.')[1]) if '.' in raw else 0
        if not (places or number > 12):
            continue
        if not dollar and not unit and re.fullmatch(r'20\d\d', raw):
            continue
        checked += 1
        tolerance = 0.5 * 10 ** -places * scale + 1e-9  # float-safe "rounds to"
        if not any(abs(k - number) <= tolerance for k in known):
            flagged.append(raw)
    return checked, flagged


def untraced_numbers(text: str, log: list) -> list:
    return number_check(text, log)[1]


def number_check_line(text: str, log: list) -> str:
    checked, flagged = number_check(text, log)
    if flagged:
        return f'Number check: {len(flagged)} of {checked} numbers match no tool result: {flagged}'
    return (f'Number check: all {checked} numbers in this answer match a tool result.' if checked
            else 'Number check: this answer states no figures.')


SCALES = {'t': 1e3, 'k': 1e3, 'm': 1e6, 'b': 1e9}


def answer_question(question: str, df, mode: str = 'rules', sidebar_filters: dict | None = None,
                    api_key: str | None = None, model: str = 'gemini-3.1-flash-lite',
                    survey=None) -> dict:
    log: list = []
    note = ''
    if mode == 'llm':
        if not api_key:
            note = 'No API key is set, so the rules-based assistant answered instead.'
        else:
            # Google's free tier is often busy on one model, so try backups before rules mode.
            for m in dict.fromkeys((model, *BACKUP_MODELS)):
                try:
                    out = llm_answer(question, df, api_key, m, sidebar_filters, log, survey)
                    if not out['used_tools']:
                        out['text'] += ('\n\n_No analytical function was called, so this answer '
                                        f'contains no calculated figures. {CAPABILITIES}_')
                    flagged = untraced_numbers(out['text'], log)
                    if 'findings' not in out['text'].lower():  # unlabeled text would be dropped by the UI split
                        out['text'] = f"**Findings:** {out['text']}"
                    for label, fallback in (('Interpretation', NO_INTERPRETATION),
                                            ('Next steps', NO_RECOMMENDATION)):
                        if label.lower() not in out['text'].lower():  # the model skipped a part
                            out['text'] += f'\n\n**{label}:** {fallback}'
                    used = [l['arguments'].get('filters', {}) | ({C.YEAR: l['arguments']['year']}
                            if 'year' in l['arguments'] else {}) for l in log]
                    scope = '; '.join(dict.fromkeys(scope_text(f, sidebar_filters) for f in used)) \
                        or NO_DATA_SCOPE
                    return {'mode': f'Language model ({m}, function calling)',
                            'scope': scope,
                            'findings': out['text'], 'interpretation': '', 'next_steps': '',
                            'tool_log': log,
                            'number_check': number_check_line(out['text'], log),
                            'note': f'Not found in any tool result, so do not rely on: {flagged}'
                            if flagged else ''}
                except Exception as exc:  # quota, network, bad key: never crash
                    note = (f'The language model was unavailable ({type(exc).__name__}), '
                            'so the rules-based assistant answered instead.')
                    log.clear()

    limit, name, args = rules_router(question, df)
    if name is None:
        findings = LIMITS[limit] if limit else f"I cannot answer that one. {CAPABILITIES}"
        return {'mode': 'Rules-based', 'scope': NO_DATA_SCOPE, 'findings': findings,
                'interpretation': NO_INTERPRETATION, 'next_steps': NO_RECOMMENDATION,
                'tool_log': log, 'note': note}

    focus = args.pop('_focus', None)
    if 'filters' in args:
        args['filters'] = merge_filters(args['filters'], sidebar_filters)
    result = run_tool(name, args, df, log, survey)
    scope = scope_text(args.get('filters', {}) | ({C.YEAR: args['year']} if 'year' in args else {}),
                       sidebar_filters)
    if result.error:
        findings = f'Could not calculate that: {result.error}'
    else:
        head = _headline(result)
        if limit in ('profit', 'forecast'):
            head = f"{LIMITS[limit]} Revenue is shown instead. {head}"
        if focus and result.tool == 'get_growth' and result.value:
            head = _focus_rank(result, focus) + (f' {head}' if head else '')
        findings = (f'{head}\n\n' if head else '') + f'{result.definition}:\n\n```\n{_fmt_value(result)}\n```\nRows used: {result.rows_used:,}'
    notes = ([LIMITS[limit]] if limit else []) + result.caveats
    interp = ' '.join(dict.fromkeys(notes))  # drop repeated caveats
    next_steps = (NO_RECOMMENDATION if limit
                  else 'Check this against the dashboard and the validation table.')
    return {'mode': 'Rules-based', 'scope': scope, 'findings': findings,
            'interpretation': interp, 'next_steps': next_steps, 'tool_log': log, 'note': note,
            'number_check': 'Number check: rules mode prints figures straight from the tool '
                            'result, so every number comes from it.'}
