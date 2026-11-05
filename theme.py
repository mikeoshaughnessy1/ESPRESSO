"""Design system: tokens, CSS, chart template, and small HTML building blocks.
Looks only. No data logic lives here; every number passed in is already calculated."""
from html import escape

import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

# ------------------------------------------------------------------ tokens
PAPER = '#F3F0E8'      # background
PAPER_2 = '#E9E5DC'    # secondary background
INK = '#242521'        # primary text
INK_2 = '#77766F'      # secondary text
RULE = '#D6D1C6'       # borders and dividers
ACCENT = '#B84A32'     # terracotta, used sparingly
WHITE = '#FFFFFF'
MUTED = '#B9B4A9'      # de-emphasized marks (context bars next to the one that matters)

SERIF = "'DM Serif Display', Georgia, serif"
SANS = "'Inter', system-ui, -apple-system, sans-serif"
MONO = "'JetBrains Mono', ui-monospace, Menlo, monospace"

# Categorical order for categories (fixed, never cycled). Validated against PAPER for
# lightness, chroma, adjacent colorblind separation, and contrast. Lines also carry
# direct end labels because terracotta/ochre are close for some colorblind readers.
CATEGORICAL = ['#B84A32', '#2B6CA3', '#987012', '#9A4D8E', '#2F8A5F']
# Terracotta has exactly one meaning across the app: the website channel.
def channel_color(name: str) -> str:
    return ACCENT if 'web' in str(name).lower() else INK


# Years: one hue, light to dark, so order reads as time. The latest year gets the accent.
YEAR_RAMP = ['#C9C4B8', '#ADA89C', '#8F8B80', '#5E5C55']

CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap');

:root {{ --paper:{PAPER}; --paper2:{PAPER_2}; --ink:{INK}; --ink2:{INK_2}; --rule:{RULE}; --accent:{ACCENT}; }}

html, body, .stApp, [class*="st-"]:not([data-testid="stIconMaterial"]), p, li, label, input, textarea, button {{ font-family:{SANS}; }}
[data-testid="stIconMaterial"] {{ font-family:'Material Symbols Rounded' !important; }}
code {{ color:var(--ink) !important; background:var(--paper2) !important; font-family:{MONO} !important; font-size:0.85em; }}
.stApp {{ background:var(--paper); color:var(--ink); }}
[data-testid="stHeader"] {{ background:transparent; }}
.block-container {{ max-width:1180px; padding:2.4rem 3rem 5rem; }}
p, li {{ color:var(--ink); line-height:1.55; }}
a {{ color:var(--accent); }}
h1, h2, h3, .ep-mast h1, .ep-fig h3 {{ font-family:{SERIF} !important; font-weight:400 !important; color:var(--ink); letter-spacing:-0.01em; }}
h1 *, h2 *, h3 * {{ font-family:inherit !important; font-weight:inherit !important; }}
.ep-mast [data-testid="stHeaderActionElements"], .ep-fig [data-testid="stHeaderActionElements"] {{ display:none; }}

/* ---------- micro-labels and metadata ---------- */
.ep-label {{ font-family:{MONO}; font-size:0.68rem; letter-spacing:0.14em; text-transform:uppercase; color:var(--ink2); }}
.ep-meta {{ font-family:{MONO}; font-size:0.74rem; color:var(--ink2); }}
.ep-accent {{ color:var(--accent); }}

/* ---------- masthead ---------- */
.ep-mast {{ border-bottom:1px solid var(--ink); padding-bottom:1.1rem; margin-bottom:0.4rem; }}
.ep-mast h1 {{ font-size:clamp(2.2rem, 5vw, 3.6rem); line-height:1.02; margin:0.5rem 0 0.6rem; padding:0; }}
.ep-mast .ep-deck {{ font-size:1.02rem; color:var(--ink2); max-width:46rem; margin:0; }}
.ep-scope {{ display:flex; gap:1.6rem; flex-wrap:wrap; padding:0.55rem 0; border-bottom:1px solid var(--rule); margin-bottom:1.6rem; }}

/* ---------- hero figure + stat strip ---------- */
.ep-hero {{ display:grid; grid-template-columns:minmax(0,1.35fr) minmax(0,2fr); border-bottom:1px solid var(--rule); margin-bottom:2.2rem; }}
.ep-hero-main {{ padding:0.4rem 2rem 1.6rem 0; border-right:1px solid var(--rule); }}
.ep-hero-num {{ font-family:{SERIF}; font-size:clamp(2.6rem, 6vw, 4.4rem); line-height:1; margin:0.6rem 0 0.5rem; }}
.ep-stats {{ display:grid; grid-template-columns:repeat(auto-fit, minmax(130px,1fr)); }}
.ep-stat {{ padding:0.4rem 1.2rem 1.4rem; border-left:1px solid var(--rule); }}
.ep-stat:first-child {{ border-left:none; }}
.ep-stat-num {{ font-family:{SERIF}; font-size:1.75rem; line-height:1.1; margin:0.55rem 0 0.25rem; }}
@media (max-width: 760px) {{
  .block-container {{ padding:1.4rem 1.1rem 4rem; }}
  .ep-hero {{ grid-template-columns:1fr; }}
  .ep-hero-main {{ border-right:none; border-bottom:1px solid var(--rule); padding-right:0; }}
  .ep-stats {{ grid-template-columns:1fr 1fr; }}
  .ep-stat {{ border-left:none; border-top:1px solid var(--rule); padding-left:0; }}
  .ep-scope {{ gap:0.6rem; flex-direction:column; }}
}}

/* ---------- figures ---------- */
.ep-fig {{ border-top:1px solid var(--ink); padding-top:0.7rem; margin-top:0.6rem; }}
.ep-fig h3 {{ font-size:1.45rem; margin:0.35rem 0 0.15rem; padding:0; }}
.ep-fig .ep-cap {{ font-size:0.86rem; color:var(--ink2); margin:0 0 0.4rem; }}
.ep-note {{ border-left:2px solid var(--accent); padding:0.55rem 0.9rem; background:var(--paper2); margin:0 0 1.4rem; font-size:0.92rem; }}
.ep-section {{ font-family:{SERIF}; font-size:1.6rem; border-top:1px solid var(--ink); padding-top:0.7rem; margin:2rem 0 0.8rem; }}

/* ---------- legend keys, share rule, colophon ---------- */
.ep-key {{ display:inline-block; width:0.7rem; height:0.7rem; background:var(--ink); margin:0 0.35rem -0.05rem 0; }}
.ep-key-web {{ background:var(--accent); }}
.ep-share {{ margin:1.4rem 0 1.2rem; }}
.ep-share-bar {{ display:flex; height:10px; gap:2px; }}
.ep-share-bar > div {{ height:100%; }}
.ep-share-labels {{ display:flex; gap:2px; margin-top:0.55rem; }}
.ep-share-labels > div {{ min-width:0; }}
.ep-share-pct {{ font-family:{SERIF}; font-size:1.9rem; line-height:1; }}
.ep-colophon {{ display:grid; grid-template-columns:repeat(3, minmax(0,1fr)); gap:1.5rem; border-top:1px solid var(--ink);
  margin-top:3.5rem; padding-top:0.8rem; }}
.ep-colophon p {{ font-size:0.82rem; color:var(--ink2); margin:0.3rem 0 0; }}
@media (max-width: 760px) {{ .ep-colophon {{ grid-template-columns:1fr; gap:0.8rem; }} }}

/* ---------- tables ---------- */
table.ep-table, table.ep-table th, table.ep-table td {{ border-left:none !important; border-right:none !important; border-top:none; }}
table.ep-table {{ width:100%; border:none !important; border-collapse:collapse; font-size:0.9rem; margin:0.4rem 0 1.4rem; }}
table.ep-table th {{ background:transparent !important; font-family:{MONO}; font-size:0.66rem; letter-spacing:0.12em; text-transform:uppercase; color:var(--ink2); font-weight:500; text-align:left; border-bottom:1px solid var(--ink); padding:0.45rem 0.6rem 0.45rem 0; }}
table.ep-table td {{ border-bottom:1px solid var(--rule); padding:0.5rem 0.6rem 0.5rem 0; vertical-align:top; }}
table.ep-table td.num, table.ep-table th.num {{ text-align:right; font-variant-numeric:tabular-nums; font-family:{MONO}; font-size:0.84rem; }}
table.ep-table tr:hover td {{ background:var(--paper2); }}

/* ---------- assistant entries ---------- */
.ep-entry {{ border-top:1px solid var(--ink); padding:1rem 0 0.4rem; margin-top:1.4rem; }}
.ep-q {{ font-family:{SERIF}; font-style:italic; font-size:1.55rem; line-height:1.2; margin:0.5rem 0 0.9rem; }}
.ep-part {{ display:grid; grid-template-columns:8.5rem minmax(0,1fr); gap:1rem; border-top:1px solid var(--rule); padding:0.7rem 0; }}
.ep-part p {{ margin:0 0 0.4rem; }}
@media (max-width: 760px) {{ .ep-part {{ grid-template-columns:1fr; gap:0.2rem; }} }}

/* ---------- sidebar: narrow editorial rail ---------- */
[data-testid="stSidebar"] {{ background:var(--paper2); border-right:1px solid var(--rule); }}
[data-testid="stSidebar"] > div:first-child {{ padding-top:1.2rem; }}
[data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3, [data-testid="stSidebar"] h2 *, [data-testid="stSidebar"] h3 * {{ font-family:{MONO} !important; font-size:0.68rem; letter-spacing:0.14em; text-transform:uppercase; color:var(--ink2); border-top:1px solid var(--rule); padding-top:0.9rem; margin-top:0.8rem; }}
.ep-mark {{ font-family:{SERIF}; font-size:1.9rem; line-height:1; color:var(--ink); }}
.ep-mark span {{ color:var(--accent); }}
/* section nav: radio styled as a numbered list with a terracotta active rule */
[data-testid="stSidebar"] [data-testid="stRadio"] div[role="radiogroup"] {{ gap:0; }}
[data-testid="stSidebar"] [data-testid="stRadioOption"] {{ padding:0.5rem 0 0.5rem 0.75rem; border-left:2px solid transparent; margin:0; width:100%; transition:border-color .15s, background .15s; cursor:pointer; }}
[data-testid="stSidebar"] [data-testid="stRadioOption"] > div > div:first-child {{ display:none; }}
[data-testid="stSidebar"] [data-testid="stRadioOption"] p {{ font-size:0.95rem; color:var(--ink2); white-space:pre; }}
[data-testid="stSidebar"] [data-testid="stRadioOption"]:hover {{ background:var(--paper); }}
[data-testid="stSidebar"] [data-testid="stRadioOption"][data-selected="true"] {{ border-left-color:var(--accent); }}
[data-testid="stSidebar"] [data-testid="stRadioOption"][data-selected="true"] p {{ color:var(--ink); font-weight:600; }}
[data-testid="stSidebar"] [data-testid="stRadioOption"]:has(input:focus-visible) {{ outline:1px dotted var(--accent); outline-offset:-1px; }}

/* ---------- controls ---------- */
.stButton button:not([kind="tertiary"]) {{ border-radius:2px; border:1px solid var(--ink); background:transparent; color:var(--ink); transition:background .15s, color .15s; }}
.stButton button:not([kind="tertiary"]):hover {{ background:var(--ink); color:var(--paper); border-color:var(--ink); }}
[data-testid="stBaseButton-tertiary"] {{ border:none !important; background:transparent !important; padding:0; min-height:0; }}
[data-testid="stBaseButton-tertiary"] p {{ font-family:{MONO}; font-size:0.74rem; color:var(--accent); }}
[data-testid="stBaseButton-tertiary"]:hover {{ text-decoration:underline; background:transparent; color:var(--accent); }}
div[data-baseweb="select"] > div, [data-testid="stChatInput"] > div {{ border-radius:2px !important; border-color:var(--rule) !important; background:var(--paper) !important; }}
div[data-baseweb="select"] > div:hover {{ border-color:var(--ink2) !important; }}
[data-testid="stFileUploaderDropzone"] {{ background:transparent !important; border:1px dashed var(--ink2) !important; border-radius:2px !important; padding:0.7rem !important; transition:border-color .15s, background .15s; }}
[data-testid="stFileUploaderDropzone"]:hover {{ border-color:var(--accent) !important; background:var(--paper) !important; }}
[data-testid="stFileUploaderDropzoneInstructions"] {{ display:none; }}
[data-testid="stFileUploaderDropzone"] button {{ width:100%; border-radius:2px; border:1px solid var(--ink); background:transparent; color:var(--ink); font-family:{MONO}; font-size:0.72rem; letter-spacing:0.1em; text-transform:uppercase; }}
[data-testid="stFileUploaderDropzone"] button:hover {{ background:var(--ink); color:var(--paper); }}
[data-testid="stFileUploaderFile"] {{ font-family:{MONO}; font-size:0.74rem; }}
[data-testid="stChatInput"] textarea {{ font-family:{SANS}; }}
.stPlotlyChart {{ margin-top:-0.4rem; }}
[data-testid="stExpander"] details {{ border:none; border-top:1px solid var(--rule); border-radius:0; }}
[data-testid="stExpander"] summary p {{ font-family:{MONO}; font-size:0.74rem; letter-spacing:0.08em; text-transform:uppercase; color:var(--ink2); }}
[data-testid="stCheckbox"] p {{ font-size:0.86rem; color:var(--ink2); }}
[data-testid="stToast"] {{ border-radius:2px; border-left:3px solid var(--accent); background:{WHITE}; }}
</style>
"""


def apply():
    st.markdown(CSS, unsafe_allow_html=True)
    t = go.layout.Template()
    t.layout = go.Layout(
        font=dict(family='Inter, system-ui, sans-serif', size=12, color=INK),
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        margin=dict(l=8, r=8, t=12, b=8), showlegend=False,
        hoverlabel=dict(bgcolor=WHITE, bordercolor=RULE, font=dict(family='Inter', size=12, color=INK)),
        xaxis=dict(showgrid=False, linecolor=INK, linewidth=1, ticks='outside', tickcolor=RULE,
                   tickfont=dict(color=INK_2, size=11), title=dict(font=dict(color=INK_2, size=11))),
        yaxis=dict(gridcolor=RULE, gridwidth=1, zeroline=False, showline=False,
                   tickfont=dict(color=INK_2, size=11), title=dict(font=dict(color=INK_2, size=11))),
        colorway=CATEGORICAL, bargap=0.35)
    pio.templates['editorial'] = t
    pio.templates.default = 'editorial'


# --------------------------------------------------------- html building blocks
def html(markup: str):
    # '$...$' would render as a math formula, so dollar signs go in as an HTML entity
    st.markdown(markup.replace('$', '&#36;'), unsafe_allow_html=True)


def masthead(label: str, title: str, deck: str):
    html(f'<div class="ep-mast"><div class="ep-label">{label}</div><h1>{escape(title)}</h1>'
         f'<p class="ep-deck">{deck}</p></div>')


def scope_bar(items: list[tuple[str, str]]):
    cells = ''.join(f'<span class="ep-meta"><span class="ep-label">{escape(k)}</span>&nbsp; {escape(v)}</span>'
                    for k, v in items)
    html(f'<div class="ep-scope">{cells}</div>')


def hero(label: str, value: str, caption: str, stats: list[tuple[str, str, str]]):
    """One big number, then compact stats separated by thin vertical rules."""
    cells = ''.join(f'<div class="ep-stat"><div class="ep-label">{escape(l)}</div>'
                    f'<div class="ep-stat-num">{escape(v)}</div><div class="ep-meta">{escape(c)}</div></div>'
                    for l, v, c in stats)
    html(f'<div class="ep-hero"><div class="ep-hero-main"><div class="ep-label">{escape(label)}</div>'
         f'<div class="ep-hero-num">{escape(value)}</div><div class="ep-meta">{escape(caption)}</div></div>'
         f'<div class="ep-stats">{cells}</div></div>')


def figure_head(number: int, title: str, caption: str = ''):
    html(f'<div class="ep-fig"><div class="ep-label">Fig. {number:02d}</div><h3>{escape(title)}</h3>'
         + (f'<p class="ep-cap">{caption}</p>' if caption else '') + '</div>')


def section(title: str):
    html(f'<div class="ep-section">{escape(title)}</div>')


def note(markup: str):
    html(f'<div class="ep-note">{markup}</div>')


def table(rows: list[dict], numeric: tuple = ()):
    """Ruled table. Columns named in `numeric` are right-aligned in mono."""
    if not rows:
        return
    cols = list(rows[0].keys())
    head = ''.join(f'<th class="{"num" if c in numeric else ""}">{escape(str(c))}</th>' for c in cols)
    body = ''.join('<tr>' + ''.join(f'<td class="{"num" if c in numeric else ""}">{escape(str(r[c]))}</td>'
                                    for c in cols) + '</tr>' for r in rows)
    html(f'<table class="ep-table"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>')


def share_rule(parts: list[tuple[str, float, str]]):
    """A thin typeset share bar: one 10px rule split by share, big numbers set underneath."""
    bar = ''.join(f'<div style="width:{p}%;background:{c}"></div>' for _, p, c in parts)
    labels = ''.join(f'<div style="width:{p}%"><div class="ep-share-pct" style="color:{c}">{p:.1f}%</div>'
                     f'<div class="ep-label" style="margin-top:0.3rem">{escape(n)}</div></div>' for n, p, c in parts)
    html(f'<div class="ep-share"><div class="ep-share-bar">{bar}</div><div class="ep-share-labels">{labels}</div></div>')


def colophon(items: list[tuple[str, str]]):
    cells = ''.join(f'<div><div class="ep-label">{escape(k)}</div><p>{escape(v)}</p></div>' for k, v in items)
    html(f'<div class="ep-colophon">{cells}</div>')


def money(x: float) -> str:
    return f'${x:,.0f}'


def money_short(x: float) -> str:
    return f'${x / 1e6:,.2f}M' if abs(x) >= 1e6 else f'${x / 1e3:,.0f}K'
