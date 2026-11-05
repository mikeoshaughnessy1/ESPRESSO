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
        'description': 'Total revenue, optionally filtered by year, store, channel, or category.',
    },
    'get_revenue_by': {
        'fn': analytics.get_revenue_by,
        'params': {'group', 'filters'},
        'description': 'Revenue and % share broken out by channel, store, category, product, year, or month.',
    },
    'get_growth': {
        'fn': analytics.get_growth,
        'params': {'group', 'filters'},
        'description': 'Percent change in revenue from the first year to the last year, per store, channel, or category.',
    },
    'get_monthly_share': {
        'fn': analytics.get_monthly_share,
        'params': {'year', 'filters'},
        'description': "Each month's revenue as a percent of one year's total.",
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

CAPABILITIES = ('I can calculate: total revenue; revenue by channel, store, category, year, '
                'or month; growth or decline between the first and last year; monthly share '
                'of a year; satisfaction vs. revenue correlation; and a data-quality report. Filters: year, store, channel, category.')

LIMITS = {
    'profit': 'The data has revenue only, no costs, so profit cannot be calculated.',
    'cause': ('This data can show whether two things move together, not whether one causes '
              'the other. Other factors (location, season, pricing) could explain both.'),
    'decision': ('Revenue trends alone do not justify a decision like closing a store. '
                 'Management would also need operating costs, store profitability, lease '
                 'terms, and customer behavior.'),
}

SYSTEM_PROMPT = """You are an analytical assistant for E-Presso managers.
Rules:
- Only state numbers that appear in a tool result. Never estimate or recall figures.
- Always call a tool before making a numerical claim.
- Pass parameters only from the allowed values you are given.
- Revenue is not profit. Association is not causation.
- If the data cannot support a conclusion, say so and name the missing information.
- Never write or run code. Never modify data.
Reply in three short labeled parts: Findings (facts from tool results only),
Interpretation (what it may mean, with caveats), Next steps (or "No recommendation
is supported by this data.")."""


# ------------------------------------------------------------- dispatcher
def allowed_values(df) -> dict:
    """Valid filter values, read from the LOADED data, never typed in."""
    out = {}
    for col in (C.YEAR, C.STORE, C.CHANNEL, C.CATEGORY):
        if col in df.columns:
            vals = df[col].dropna().unique().tolist()
            out[col] = sorted(int(v) if col == C.YEAR else str(v) for v in vals)
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
            result = TOOLS[name]['fn'](df, **extra, **args)
    log.append({'tool': name, 'arguments': args, 'result': result.to_dict()})
    return result


def merge_filters(tool_filters: dict | None, sidebar_filters: dict | None) -> dict:
    """Sidebar filters apply unless the question names its own value."""
    merged = dict(sidebar_filters or {})
    merged.update(tool_filters or {})
    return merged


def scope_text(filters: dict, sidebar_filters: dict | None) -> str:
    if not filters:
        return 'All data (all years, stores, channels, categories)'
    parts = [f'{k} = {v}' for k, v in filters.items()]
    src = ' (includes sidebar filters)' if sidebar_filters else ''
    return ', '.join(parts) + src


# ----------------------------------------------------------- rules router
def _find_filters(q: str, df) -> dict:
    """Pull filter values out of the question by matching the loaded data."""
    found = {}
    for col, values in allowed_values(df).items():
        for v in values:
            if re.search(rf'\b{re.escape(str(v).lower())}\b', q):
                found[col] = v
                break
    if C.STORE not in found and C.STORE in df.columns:
        found.update(_match_store(q, allowed_values(df)[C.STORE]))
    return found


def _match_store(q: str, stores: list) -> dict:
    """Store labels look like 'SH11 Chicago, IL'. Match on the ID or the city.
    A city with two stores (Orlando) is ambiguous, so it matches nothing."""
    for label in stores:
        if re.search(rf'\b{label.split()[0].lower()}\b', q):  # store ID, e.g. sh11
            return {C.STORE: label}
    by_city = [lab for lab in stores if ',' in lab
               and re.search(rf"\b{re.escape(lab.split(' ', 1)[1].split(',')[0].lower())}\b", q)]
    return {C.STORE: by_city[0]} if len(by_city) == 1 else {}


def _find_group(q: str) -> str | None:
    for word, col in (('channel', C.CHANNEL), ('store', C.STORE), ('location', C.STORE), ('category', C.CATEGORY),
                      ('product', C.PRODUCT), ('month', C.MONTH), ('year', C.YEAR),
                      ('annual', C.YEAR)):
        if word in q:
            return col
    return None


def rules_router(question: str, df):
    """Option B. Returns (limit_key, tool_name, args). Any part may be None."""
    q = question.lower()
    limit = None
    if 'profit' in q or 'margin' in q:
        limit = 'profit'
    elif re.search(r'\bcaus|\bbecause\b|\bdrive', q):
        limit = 'cause'
    elif re.search(r'\bshould\b|\bclose\b|\bopen a\b', q):
        limit = 'decision'

    if any(w in q for w in ('missing', 'duplicate', 'quality', 'blank')):
        return limit, 'data_quality_report', {}
    if 'satisf' in q or 'survey' in q:
        return limit, 'get_satisfaction_vs_revenue', {'filters': _find_filters(q, df)}

    filters = _find_filters(q, df)
    group = _find_group(q)

    if limit == 'decision' and C.STORE in filters:
        return limit, 'get_growth', {'group': C.STORE, 'filters': filters}  # that store's trend
    if any(w in q for w in ('grow', 'growth', 'decline', 'drop', 'increase', 'decrease', 'trend')) \
            and group not in (None, C.YEAR, C.MONTH):
        return limit, 'get_growth', {'group': group, 'filters': filters}
    if group == C.MONTH and C.YEAR in filters:
        year = filters.pop(C.YEAR)
        return limit, 'get_monthly_share', {'year': year, 'filters': filters}
    if group and group in filters and ' by ' not in f' {q} ':
        group = None  # "Chicago store revenue" wants one number, not a breakdown
    if group:
        filters.pop(group, None)
        return limit, 'get_revenue_by', {'group': group, 'filters': filters}
    if any(w in q for w in ('revenue', 'sales', 'sold', 'earn', 'generate', 'make', 'profit')):
        return limit, 'get_total_revenue', {'filters': filters}
    return limit, None, None


# ------------------------------------------------------------- LLM router
def llm_answer(question: str, df, api_key: str, model: str, sidebar_filters: dict | None,
               log: list, survey=None) -> dict:
    """Option A: Gemini picks tools via function calling. Our code runs them.
    Raises on any API problem so the caller can fall back to rules."""
    from google import genai
    from google.genai import types

    allowed = allowed_values(df)
    filter_schema = {'type': 'OBJECT', 'properties': {
        col: ({'type': 'INTEGER', 'description': f'One of {vals}'} if col == C.YEAR else
              {'type': 'STRING', 'enum': vals}) for col, vals in allowed.items()}}
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
        resp = client.models.generate_content(model=model, contents=contents, config=cfg)
        calls = resp.function_calls or []
        if not calls:
            return {'text': resp.text or '', 'used_tools': bool(log)}
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
        if len(v) == 1:
            return f"{low[0]}: {low[1]['pct_change']:+.2f}% from first to last year."
        if low[1]['pct_change'] >= 0:
            return f"No group declined. Smallest growth: {low[0]} ({low[1]['pct_change']:+.2f}%)."
        return (f"Largest decline: {low[0]} ({low[1]['pct_change']:+.2f}%). "
                f"Largest growth: {high[0]} ({high[1]['pct_change']:+.2f}%).")
    if result.tool == 'get_revenue_by' and v:
        top = max(v.items(), key=lambda kv: kv[1]['revenue'])
        return f"Highest: {top[0]} (${top[1]['revenue']:,.2f}, {top[1]['share_pct']}% of revenue in scope)."
    if result.tool == 'get_satisfaction_vs_revenue':
        return f"Correlation r = {v['pearson_r']} across {v['store_years']} store-years."
    return ''


def _fmt_value(result: ToolResult) -> str:
    v = result.value
    if isinstance(v, float):
        return f'${v:,.2f}'
    return json.dumps(v, indent=1, default=str)


def answer_question(question: str, df, mode: str = 'rules', sidebar_filters: dict | None = None,
                    api_key: str | None = None, model: str = 'gemini-2.5-flash',
                    survey=None) -> dict:
    log: list = []
    note = ''
    if mode == 'llm':
        if not api_key:
            note = 'No API key is set, so the rules-based assistant answered instead.'
        else:
            try:
                out = llm_answer(question, df, api_key, model, sidebar_filters, log, survey)
                if not out['used_tools']:
                    out['text'] += ('\n\n_No analytical function was called, so this answer '
                                    'contains no calculated figures._')
                return {'mode': 'Language model (Gemini, function calling)',
                        'scope': scope_text(sidebar_filters or {}, sidebar_filters),
                        'findings': out['text'], 'interpretation': '', 'next_steps': '',
                        'tool_log': log}
            except Exception as exc:  # quota, network, bad key: never crash
                note = (f'The language model was unavailable ({type(exc).__name__}), '
                        'so the rules-based assistant answered instead.')
                log.clear()

    limit, name, args = rules_router(question, df)
    if name is None:
        findings = LIMITS[limit] if limit else f"I cannot answer that one. {CAPABILITIES}"
        return {'mode': 'Rules-based', 'scope': 'n/a', 'findings': findings,
                'interpretation': '', 'next_steps': 'No recommendation is supported by this data.',
                'tool_log': log, 'note': note}

    if 'filters' in args:
        args['filters'] = merge_filters(args['filters'], sidebar_filters)
    result = run_tool(name, args, df, log, survey)
    scope = scope_text(args.get('filters', {}) | ({C.YEAR: args['year']} if 'year' in args else {}),
                       sidebar_filters)
    if result.error:
        findings = f'Could not calculate that: {result.error}'
    else:
        head = _headline(result)
        if limit == 'profit':
            head = f"{LIMITS['profit']} Revenue is shown instead. {head}"
        findings = (f'{head}\n\n' if head else '') + f'{result.definition}:\n\n```\n{_fmt_value(result)}\n```\nRows used: {result.rows_used:,}'
    notes = ([LIMITS[limit]] if limit else []) + result.caveats
    interp = ' '.join(dict.fromkeys(notes))  # drop repeated caveats
    next_steps = ('No recommendation is supported by this data alone.' if limit
                  else 'Check this against the dashboard and the validation table.')
    return {'mode': 'Rules-based', 'scope': scope, 'findings': findings,
            'interpretation': interp, 'next_steps': next_steps, 'tool_log': log, 'note': note}
