"""Shared helpers for every page of the Customer 360 Streamlit app."""
import os
import sys
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# On Streamlit Cloud, secrets are exposed via st.secrets; bridge them to env vars.
try:
    for _key, _value in st.secrets.items():
        if isinstance(_value, str):
            os.environ.setdefault(_key, _value)
except Exception:  # noqa: BLE001 - no secrets file locally, .env is used instead
    pass

from src.agent import get_engine  # noqa: E402

PALETTE = ["#0F9D9A", "#12263F", "#F2A541", "#E4572E", "#6C8EAD", "#7BC8A4"]

KPI_SQL = """
SELECT
    SUM(net_sales)                                              AS revenue,
    SUM(profit)                                                 AS profit,
    COUNT(DISTINCT order_id)                                    AS orders,
    SUM(net_sales) / COUNT(DISTINCT order_id)                   AS aov,
    100.0 * SUM((order_status = 'Returned')::int) / COUNT(*)    AS return_rate,
    100.0 * SUM((order_status = 'Cancelled')::int) / COUNT(*)   AS cancel_rate
FROM analytics_marts.fact_orders
"""

CSS = """
<style>
#MainMenu, footer {visibility: hidden;}
.block-container {padding-top: 1.5rem; max-width: 1400px;}
.hero {
    background: linear-gradient(120deg, #12263F 0%, #0F9D9A 100%);
    padding: 2rem 2.2rem; border-radius: 18px; color: #fff; margin-bottom: 1.4rem;
    box-shadow: 0 8px 24px rgba(18,38,63,.18);
}
.hero h1 {margin: 0; font-size: 2rem; color: #fff;}
.hero p {margin: .4rem 0 0; opacity: .9; font-size: 1.02rem;}
.badge {
    display: inline-block; background: rgba(255,255,255,.18); padding: .2rem .7rem;
    border-radius: 999px; font-size: .78rem; margin-right: .4rem; margin-top: .8rem;
}
.kpi {
    background: #fff; border-radius: 14px; padding: 1rem 1.1rem;
    border-left: 5px solid #0F9D9A; box-shadow: 0 2px 10px rgba(18,38,63,.08);
}
.kpi .label {font-size: .78rem; color: #6B7A90; text-transform: uppercase; letter-spacing: .05em;}
.kpi .value {font-size: 1.3rem; font-weight: 700; color: #12263F; margin-top: .15rem; white-space: nowrap;}
.section-title {font-size: 1.1rem; font-weight: 600; color: #12263F; margin: 1.4rem 0 .6rem;}
[data-testid="stChatMessage"] {background: #fff; border-radius: 16px; border-left: 4px solid #0F9D9A; box-shadow: 0 2px 10px rgba(18,38,63,.08); padding: 1rem 1.2rem; margin-bottom: .8rem;}
div.stButton > button {
    border-radius: 999px; border: 1px solid #0F9D9A; color: #0F9D9A; background: #fff;
    padding: .35rem 1rem; font-size: .85rem; transition: all .15s;
}
div.stButton > button:hover {background: #0F9D9A; color: #fff; border-color: #0F9D9A;}
.flow {display: flex; flex-wrap: wrap; gap: .5rem; align-items: stretch;}
.node {
    flex: 1; min-width: 130px; background: #fff; border-radius: 14px; padding: .9rem .6rem;
    border-top: 4px solid #0F9D9A; text-align: center; box-shadow: 0 2px 10px rgba(18,38,63,.08);
}
.node .icon {font-size: 1.6rem;}
.node .title {font-weight: 700; color: #12263F; margin-top: .2rem;}
.node .sub {font-size: .76rem; color: #6B7A90; margin-top: .15rem;}
.arrow {align-self: center; color: #0F9D9A; font-size: 1.5rem; font-weight: 700;}
</style>
"""


def inject_css() -> None:
    """Apply the shared navy/teal theme (call right after st.set_page_config)."""
    st.markdown(CSS, unsafe_allow_html=True)


def hero(title: str, subtitle: str, badges: list[str] | None = None) -> None:
    """Gradient header banner."""
    badge_html = "".join(f'<span class="badge">{b}</span>' for b in (badges or []))
    st.markdown(
        f'<div class="hero"><h1>{title}</h1><p>{subtitle}</p>{badge_html}</div>',
        unsafe_allow_html=True,
    )


@st.cache_resource
def cached_engine():
    """One read-only engine per app process."""
    return get_engine()


@st.cache_data(ttl=3600, show_spinner=False)
def load_kpis() -> dict:
    """Headline KPIs from fact_orders (cached for one hour)."""
    with cached_engine().connect() as conn:
        return pd.read_sql(KPI_SQL, conn).iloc[0].to_dict()


def render_kpis() -> None:
    """Six headline KPI cards."""
    try:
        kpi = load_kpis()
    except Exception as exc:  # noqa: BLE001
        st.error(f"Could not load KPIs: {type(exc).__name__}")
        return
    cards = [
        ("Revenue", f"${kpi['revenue']:,.0f}"),
        ("Profit", f"${kpi['profit']:,.0f}"),
        ("Orders", f"{int(kpi['orders']):,}"),
        ("Avg Order Value", f"${kpi['aov']:,.2f}"),
        ("Return Rate", f"{kpi['return_rate']:.2f}%"),
        ("Cancellation Rate", f"{kpi['cancel_rate']:.2f}%"),
    ]
    for col, (label, value) in zip(st.columns(6), cards):
        col.markdown(
            f'<div class="kpi"><div class="label">{label}</div>'
            f'<div class="value">{value}</div></div>',
            unsafe_allow_html=True,
        )


def friendly_error(error: str) -> str:
    """Translate technical errors into messages a business user can act on."""
    if "Only SELECT" in error or "forbidden" in error:
        return ("I can only answer read-only analytics questions about the "
                "Customer 360 data. Try rephrasing your question.")
    if "429" in error or "rate" in error.lower():
        return "The AI service is busy right now. Please wait a minute and try again."
    return f"Sorry, I could not answer that. ({error})"


def show_chart(df: pd.DataFrame) -> None:
    """Draw a styled line (time) or bar (category) chart for label + number results."""
    if len(df) < 2 or df.shape[1] < 2:
        return
    first = df.columns[0]
    numeric = [c for c in df.select_dtypes("number").columns if c != first]
    if not numeric:
        return
    value = numeric[0]
    data = df.copy()
    data[first] = data[first].astype(str)  # avoids "2,021" style year labels
    is_time = any(word in first.lower() for word in ("year", "month", "date"))
    base = alt.Chart(data).encode(
        x=alt.X(f"{first}:N", sort=None, title=None,
                axis=alt.Axis(labelAngle=0 if is_time else -30)),
        y=alt.Y(f"{value}:Q", title=None, scale=alt.Scale(zero=not is_time)),
        tooltip=list(data.columns),
    )
    if is_time:
        chart = base.mark_line(color="#0F9D9A", strokeWidth=3,
                               point=alt.OverlayMarkDef(color="#12263F", size=90))
    else:
        chart = base.mark_bar(cornerRadiusTopLeft=6, cornerRadiusTopRight=6).encode(
            color=alt.Color(f"{first}:N", scale=alt.Scale(range=PALETTE), legend=None)
        )
    st.altair_chart(chart.properties(height=320), use_container_width=True)


def render_result(item: dict) -> None:
    """Render one assistant answer: message, chart, table and SQL."""
    if item["error"]:
        st.warning(friendly_error(item["error"]))
        return
    df = item["data"]
    st.write(f"Found **{len(df)}** row(s).")
    show_chart(df)
    st.dataframe(df, use_container_width=True, hide_index=True)
    with st.expander("View generated SQL"):
        st.code(item["sql"], language="sql")