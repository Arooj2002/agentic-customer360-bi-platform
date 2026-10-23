"""Home page: project overview, headline KPIs and architecture."""
import streamlit as st

st.set_page_config(page_title="Customer 360 Platform", page_icon="📊", layout="wide")

from shared import hero, inject_css, render_kpis  # noqa: E402

inject_css()

hero(
    "📊 Customer 360 BI Platform",
    "An end-to-end analytics stack: from raw data to a governed star schema "
    "and an AI analyst that answers questions.",
    ["Supabase PostgreSQL", "dbt star schema", "Airflow", "Power BI", "LangChain + Groq"],
)

render_kpis()

# ---------- Architecture ----------
st.markdown('<div class="section-title">How the data flows</div>', unsafe_allow_html=True)


def node(icon: str, title: str, sub: str, accent: str = "#0F9D9A") -> str:
    """One architecture box."""
    return (f'<div class="node" style="border-top-color:{accent}">'
            f'<div class="icon">{icon}</div>'
            f'<div class="title">{title}</div><div class="sub">{sub}</div></div>')


def flow_row(nodes: list[str], arrow: str = "→", top_margin: str = "0") -> None:
    """Render nodes in one row, joined by arrows."""
    joined = f'<div class="arrow">{arrow}</div>'.join(nodes)
    st.markdown(f'<div class="flow" style="margin-top:{top_margin}">{joined}</div>',
                unsafe_allow_html=True)


def down_arrow(label: str) -> None:
    """Small centered connector between rows."""
    st.markdown(
        f'<div style="text-align:center;color:#0F9D9A;font-weight:700;margin:.5rem 0">'
        f'↓ <span style="font-weight:400;color:#6B7A90;font-size:.82rem">{label}</span></div>',
        unsafe_allow_html=True,
    )


# Row 1: data pipeline
flow_row([
    node("📥", "Sources", "Kaggle CSVs + DummyJSON API"),
    node("🐍", "Python / Pandas", "Clean, PII removed, Parquet"),
    node("🗄️", "Supabase", "PostgreSQL raw schema"),
    node("🧱", "dbt Core", "Staging views + star schema marts, 25 tests"),
])

# Orchestration banner
down_arrow("scheduled and monitored by")
st.markdown(
    '<div class="node" style="border-top-color:#F2A541;flex:none">'
    '<div class="icon">⏰</div><div class="title">Apache Airflow</div>'
    '<div class="sub">Daily 11:00 PKT: extract → transform → load → dbt run → dbt test</div>'
    "</div>",
    unsafe_allow_html=True,
)

# Row 2: consumers of the marts
down_arrow("marts are read by")
flow_row([
    node("📊", "Power BI", "4-page dashboard on the marts", "#12263F"),
    node("🤖", "LangChain + Groq", "Text-to-SQL through a read-only role", "#12263F"),
    node("🖥️", "Streamlit", "This app", "#12263F"),
], arrow="•")

# ---------- What's inside ----------
st.markdown('<div class="section-title">Explore the app</div>', unsafe_allow_html=True)
cols = st.columns(4)
cols[0].page_link("pages/1_AI_Analyst.py", label="🤖 AI Analyst")
cols[1].page_link("pages/2_Executive_Dashboard.py", label="📈 Executive Dashboard")
cols[2].page_link("pages/3_Data_Explorer.py", label="🗂️ Data Explorer")
cols[3].page_link("pages/4_Query_Log.py", label="🧾 Query Log")

st.caption("Synthetic dataset. Revenue, profit and rates come from fact_orders "
           "and reconcile with the Power BI report.")