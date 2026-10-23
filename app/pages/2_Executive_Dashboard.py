"""Executive Dashboard: BI charts without AI, with filters."""
import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="Executive Dashboard", page_icon="📈", layout="wide")

from shared import PALETTE, cached_engine, hero, inject_css  # noqa: E402

inject_css()

CUBE_SQL = """
SELECT d.year, d.year_month, COALESCE(c.region, 'Unknown') AS region,
       COALESCE(c.customer_segment, 'Unknown') AS segment, f.sales_channel,
       SUM(f.net_sales) AS revenue, SUM(f.profit) AS profit, COUNT(*) AS orders,
       SUM(f.customer_rating) AS rating_sum, COUNT(f.customer_rating) AS rating_n,
       SUM((f.order_status = 'Returned')::int) AS returned,
       SUM((f.order_status = 'Cancelled')::int) AS cancelled
FROM analytics_marts.fact_orders f
JOIN analytics_marts.dim_date d ON f.order_date_key = d.date_key
LEFT JOIN analytics_marts.dim_customers c ON f.customer_id = c.customer_id
GROUP BY 1, 2, 3, 4, 5
"""

BRANDS_SQL = """
SELECT p.brand, SUM(i.net_sales) AS item_net_sales
FROM analytics_marts.fact_order_items i
JOIN analytics_marts.dim_products p ON i.product_id = p.product_id
GROUP BY p.brand ORDER BY item_net_sales DESC LIMIT 10
"""


@st.cache_data(ttl=3600, show_spinner="Loading data...")
def load_cube() -> pd.DataFrame:
    """Pre-aggregated order data; filters are applied in pandas."""
    with cached_engine().connect() as conn:
        df = pd.read_sql(CUBE_SQL, conn)
    for col in ("revenue", "profit", "rating_sum"):
        df[col] = df[col].astype(float)
    df["year"] = df["year"].astype(int).astype(str)
    return df


@st.cache_data(ttl=3600, show_spinner=False)
def load_brands() -> pd.DataFrame:
    with cached_engine().connect() as conn:
        df = pd.read_sql(BRANDS_SQL, conn)
    df["item_net_sales"] = df["item_net_sales"].astype(float)
    return df


def style(fig, height: int = 340):
    """Apply the shared look to a Plotly figure."""
    fig.update_layout(
        height=height, margin=dict(l=10, r=10, t=40, b=10),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font_color="#12263F", legend_title_text="",
    )
    fig.update_xaxes(showgrid=False, title=None)
    fig.update_yaxes(gridcolor="#E3E8EF", title=None)
    return fig


def card(fig) -> None:
    with st.container(border=True):
        st.plotly_chart(fig, width="stretch")


hero("📈 Executive Dashboard", "Revenue, profit and service quality at a glance. "
     "No AI here: plain SQL on the star schema.",
     ["fact_orders", "fact_order_items", "dim_customers", "dim_products", "dim_date"])

cube = load_cube()

# ---------- Filters ----------
f1, f2, f3 = st.columns(3)
years = f1.multiselect("Year", sorted(cube["year"].unique()), default=sorted(cube["year"].unique()))
regions = f2.multiselect("Region", sorted(cube["region"].unique()), default=sorted(cube["region"].unique()))
segments = f3.multiselect("Segment", sorted(cube["segment"].unique()), default=sorted(cube["segment"].unique()))

data = cube[cube["year"].isin(years) & cube["region"].isin(regions) & cube["segment"].isin(segments)]
if data.empty:
    st.warning("No data for this filter combination.")
    st.stop()

# ---------- KPI cards (8, two rows of four) ----------
revenue, profit, orders = data["revenue"].sum(), data["profit"].sum(), int(data["orders"].sum())
rating = data["rating_sum"].sum() / max(data["rating_n"].sum(), 1)
cards = [
    ("Revenue", f"${revenue:,.0f}"),
    ("Profit", f"${profit:,.0f}"),
    ("Profit Margin", f"{profit / revenue * 100:.2f}%"),
    ("Orders", f"{orders:,}"),
    ("Avg Order Value", f"${revenue / orders:,.2f}"),
    ("Avg Rating", f"{rating:.2f}"),
    ("Return Rate", f"{data['returned'].sum() / orders * 100:.2f}%"),
    ("Cancellation Rate", f"{data['cancelled'].sum() / orders * 100:.2f}%"),
]
for row_cards in (cards[:4], cards[4:]):
    for col, (label, value) in zip(st.columns(4), row_cards):
        col.markdown(f'<div class="kpi"><div class="label">{label}</div>'
                     f'<div class="value">{value}</div></div>', unsafe_allow_html=True)
    st.write("")

st.markdown('<div class="section-title">Revenue trend</div>', unsafe_allow_html=True)
monthly = data.groupby("year_month", as_index=False)["revenue"].sum().sort_values("year_month")
fig = px.area(monthly, x="year_month", y="revenue", color_discrete_sequence=[PALETTE[0]])
card(style(fig, 320))

left, right = st.columns(2)
with left:
    st.markdown('<div class="section-title">Revenue by sales channel</div>', unsafe_allow_html=True)
    ch = data.groupby("sales_channel", as_index=False)["revenue"].sum().sort_values("revenue", ascending=False)
    card(style(px.bar(ch, x="sales_channel", y="revenue", color="sales_channel",
                      color_discrete_sequence=PALETTE).update_layout(showlegend=False)))
with right:
    st.markdown('<div class="section-title">Revenue by customer segment</div>', unsafe_allow_html=True)
    sg = data.groupby("segment", as_index=False)["revenue"].sum().sort_values("revenue", ascending=False)
    card(style(px.pie(sg, names="segment", values="revenue", hole=0.55,
                      color_discrete_sequence=PALETTE)))

left, right = st.columns(2)
yearly = data.groupby("year", as_index=False)[["revenue", "profit", "orders", "returned", "cancelled"]].sum()
yearly["Profit margin %"] = yearly["profit"] / yearly["revenue"] * 100
yearly["Return rate %"] = yearly["returned"] / yearly["orders"] * 100
yearly["Cancellation rate %"] = yearly["cancelled"] / yearly["orders"] * 100
with left:
    st.markdown('<div class="section-title">Profit margin by year</div>', unsafe_allow_html=True)
    fig = px.bar(yearly, x="year", y="Profit margin %", color_discrete_sequence=[PALETTE[1]])
    card(style(fig))
with right:
    st.markdown('<div class="section-title">Return vs cancellation rate by year</div>', unsafe_allow_html=True)
    rates = yearly.melt(id_vars="year", value_vars=["Return rate %", "Cancellation rate %"],
                        var_name="metric", value_name="percent")
    fig = px.line(rates, x="year", y="percent", color="metric", markers=True,
                  color_discrete_sequence=[PALETTE[3], PALETTE[0]])
    card(style(fig))

st.markdown('<div class="section-title">Top 10 brands by item net sales</div>', unsafe_allow_html=True)
brands = load_brands().sort_values("item_net_sales")
fig = px.bar(brands, x="item_net_sales", y="brand", orientation="h", color_discrete_sequence=[PALETTE[0]])
card(style(fig, 380))
st.caption("Brand chart uses fact_order_items and ignores the filters above. Item net sales "
           "(line level) is higher than order revenue because of a known header/line "
           "mismatch in the source data.")