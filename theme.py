"""Look and feel only: green palette and a forest background. No data logic here."""
import plotly.express as px
import plotly.io as pio
import streamlit as st

# Greens for charts, dark to light, so categories stay easy to tell apart.
PALETTE = ['#1F5E3B', '#4E9A5B', '#A3C76D', '#2F7F79', '#7DB8A0', '#C9A66B', '#5C4B3B']


def _pine(x, base, h, w, color):
    """One pine tree as a stack of three triangles."""
    tiers = []
    for i, scale in enumerate((1.0, 0.78, 0.56)):
        top = base - h * (0.35 + 0.3 * i) - h * 0.35
        bottom = base - h * 0.3 * i
        half = w * scale / 2
        tiers.append(f'<polygon points="{x - half},{bottom} {x},{top} {x + half},{bottom}" fill="{color}"/>')
    trunk = f'<rect x="{x - w * 0.06}" y="{base}" width="{w * 0.12}" height="{h * 0.08}" fill="#4a3b2c"/>'
    return trunk + ''.join(tiers)


def _forest_svg() -> str:
    rows = [  # (count, base y, height, width, color, offset): far rows are lighter
        (16, 330, 150, 70, '#cfe3c4', 0), (13, 360, 200, 95, '#9cc591', 45),
        (10, 400, 260, 120, '#5f9b62', 20)]
    trees = []
    for count, base, h, w, color, offset in rows:
        step = 1600 / count
        for i in range(count):
            jitter = ((i * 37) % 23 - 11)  # fixed pseudo-random spacing, same every load
            trees.append(_pine(offset + i * step + jitter, base, h + jitter * 3, w, color))
    ground = '<rect x="0" y="395" width="1600" height="40" fill="#4f8a52"/>'
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1600 430" '
            'preserveAspectRatio="xMidYMax slice">' + ''.join(trees) + ground + '</svg>')


def apply():
    from urllib.parse import quote
    forest = quote(_forest_svg())
    st.markdown(f"""
<style>
.stApp {{
  background-color: #eef5ea;
  background-image: url("data:image/svg+xml,{forest}"),
                    linear-gradient(180deg, #e4f0f7 0%, #eef5ea 55%);
  background-repeat: no-repeat, no-repeat;
  background-position: bottom center, top;
  background-size: 100% 42vh, cover;
  background-attachment: fixed;
}}
[data-testid="stHeader"] {{ background: transparent; }}
.block-container {{
  background: rgba(255, 255, 255, 0.90);
  border-radius: 16px;
  padding: 2rem 2.5rem 3rem;
  margin-top: 1.5rem;
  box-shadow: 0 6px 24px rgba(31, 94, 59, 0.12);
}}
[data-testid="stSidebar"] {{ background: #1F5E3B; }}
[data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3,
[data-testid="stSidebar"] label, [data-testid="stSidebar"] p,
[data-testid="stSidebar"] [data-testid="stCaptionContainer"] {{ color: #f1f7ee !important; }}
h1 {{ color: #1F5E3B; letter-spacing: -0.5px; }}
h2, h3 {{ color: #2b6b45; }}
[data-testid="stMetric"] {{
  background: #f3f8f0; border: 1px solid #d3e6cc; border-radius: 12px; padding: 0.8rem 1rem;
}}
[data-testid="stMetricValue"] {{ color: #1F5E3B; }}
.stTabs [aria-selected="true"] {{ color: #1F5E3B; }}
</style>
""", unsafe_allow_html=True)

    template = pio.templates['plotly_white']
    template.layout.colorway = PALETTE
    template.layout.paper_bgcolor = 'rgba(0,0,0,0)'
    template.layout.plot_bgcolor = 'rgba(0,0,0,0)'
    template.layout.title.font.color = '#1F5E3B'
    pio.templates['forest'] = template
    px.defaults.template = 'forest'
    px.defaults.color_discrete_sequence = PALETTE
