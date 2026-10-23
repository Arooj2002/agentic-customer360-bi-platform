"""Data Explorer: star schema diagram plus an expander per mart table."""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from sqlalchemy import text

st.set_page_config(page_title="Data Explorer", page_icon="🗂️", layout="wide")

from shared import cached_engine, hero, inject_css  # noqa: E402

inject_css()

TABLES = {
    "fact_orders": "One row per order. Source of all revenue, profit and rate KPIs.",
    "fact_order_items": "One row per product per order. Used for category and brand analysis.",
    "dim_customers": "One row per customer: segment, region, order counts.",
    "dim_products": "One row per product: category, brand, price, cost.",
    "dim_date": "One row per calendar day, 2021-2025.",
}

# Short descriptions for the most important columns (others are left blank on purpose).
COLUMN_NOTES = {
    ("fact_orders", "order_id"): "Primary key, one row per order",
    ("fact_orders", "customer_id"): "Foreign key to dim_customers",
    ("fact_orders", "order_date_key"): "Foreign key to dim_date.date_key",
    ("fact_orders", "order_status"): "Completed, Returned, Cancelled or Pending",
    ("fact_orders", "net_sales"): "Order revenue, used for every revenue KPI",
    ("fact_orders", "profit"): "Order profit",
    ("fact_order_items", "order_item_id"): "Surrogate key (md5 over all source columns)",
    ("fact_order_items", "order_id"): "Foreign key to fact_orders",
    ("fact_order_items", "product_id"): "Foreign key to dim_products",
    ("fact_order_items", "net_sales"): "Line-level sales, can differ from the order header",
    ("fact_order_items", "is_order_reconciled"): "False when line totals do not match the order header",
    ("dim_customers", "customer_id"): "Primary key",
    ("dim_customers", "customer_segment"): "Customer segment",
    ("dim_customers", "is_never_purchased"): "True for customers with no orders",
    ("dim_products", "product_id"): "Primary key",
    ("dim_products", "product_category"): "Product category",
    ("dim_date", "date_key"): "Primary key, yyyymmdd integer",
    ("dim_date", "year_month"): "Month label used for trend charts",
}


def build_erd() -> go.Figure:
    """Star-shaped diagram: fact_orders in the centre, dimensions around it."""
    # name -> (x, y, columns, is_fact)
    boxes = {
        "fact_orders": (5.0, 6.4, ["order_id", "customer_id", "order_date_key",
                                   "order_status", "net_sales", "profit"], True),
        "dim_customers": (1.5, 6.4, ["customer_id", "customer_segment", "region",
                                     "customer_country", "total_orders"], False),
        "dim_date": (8.5, 6.4, ["date_key", "year", "quarter", "month", "year_month"], False),
        "fact_order_items": (5.0, 3.6, ["order_item_id", "order_id", "product_id",
                                        "quantity", "net_sales", "is_order_reconciled"], True),
        "dim_products": (5.0, 0.95, ["product_id", "product_category", "brand",
                                     "unit_price", "product_cost"], False),
    }
    half_w, half_h = 1.35, 0.95
    links = [
        ("fact_orders", "dim_customers", "customer_id", "h"),
        ("fact_orders", "dim_date", "order_date_key", "h"),
        ("fact_order_items", "fact_orders", "order_id", "v"),
        ("fact_order_items", "dim_products", "product_id", "v"),
    ]
    fig = go.Figure()
    for src, dst, label, kind in links:
        sx, sy = boxes[src][:2]
        dx, dy = boxes[dst][:2]
        if kind == "h":
            start = (sx + (half_w if dx > sx else -half_w), sy)
            end = (dx + (-half_w if dx > sx else half_w), dy)
        else:
            start = (sx, sy + (half_h if dy > sy else -half_h))
            end = (dx, dy + (-half_h if dy > sy else half_h))
        fig.add_annotation(x=end[0], y=end[1], ax=start[0], ay=start[1],
                           xref="x", yref="y", axref="x", ayref="y",
                           showarrow=True, arrowhead=2, arrowwidth=2, arrowcolor="#12263F")
        mx, my = (start[0] + end[0]) / 2, (start[1] + end[1]) / 2
        fig.add_annotation(x=mx + (0 if kind == "h" else 0.6), y=my + (0.25 if kind == "h" else 0),
                           text=label, showarrow=False, font=dict(size=12, color="#6B7A90"))
    for name, (x, y, cols, is_fact) in boxes.items():
        fig.add_shape(type="rect", x0=x - half_w, x1=x + half_w, y0=y - half_h, y1=y + half_h,
                      fillcolor="#0F9D9A" if is_fact else "#FFFFFF",
                      line=dict(color="#0F9D9A", width=2), layer="below")
        color = "#FFFFFF" if is_fact else "#12263F"
        sub = "#DDF1F0" if is_fact else "#6B7A90"
        body = "<br>".join(f"<span style='font-size:11px;color:{sub}'>{c}</span>" for c in cols)
        fig.add_annotation(x=x, y=y, showarrow=False, align="center",
                           text=f"<b>{name}</b><br>{body}",
                           font=dict(size=14, color=color))
    fig.add_annotation(x=0.1, y=0.1, xanchor="left", showarrow=False,
                       text="Arrow = foreign key reference (child → parent)",
                       font=dict(size=12, color="#6B7A90"))
    fig.update_xaxes(range=[0, 10], visible=False, fixedrange=True)
    fig.update_yaxes(range=[0, 7.5], visible=False, fixedrange=True)
    fig.update_layout(height=640, margin=dict(l=0, r=0, t=10, b=0),
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    return fig


@st.cache_data(ttl=3600, show_spinner=False)
def table_info(name: str):
    """Columns, row count and 5 sample rows for one mart table (name is whitelisted)."""
    assert name in TABLES
    with cached_engine().connect() as conn:
        cols = pd.read_sql(
            text("SELECT column_name, data_type FROM information_schema.columns "
                 "WHERE table_schema = 'analytics_marts' AND table_name = :t "
                 "ORDER BY ordinal_position"), conn, params={"t": name})
        count = conn.execute(text(f"SELECT COUNT(*) FROM analytics_marts.{name}")).scalar()
        sample = pd.read_sql(text(f"SELECT * FROM analytics_marts.{name} LIMIT 5"), conn)
    return cols, count, sample


hero("🗂️ Data Explorer", "The governed star schema built by dbt on Supabase PostgreSQL.",
     ["analytics_marts", "5 tables", "dbt tests"])

st.markdown('<div class="section-title">Star schema</div>', unsafe_allow_html=True)
with st.container(border=True):
    st.plotly_chart(build_erd(), width="stretch", config={"displayModeBar": False})
st.caption("Dark boxes are fact tables, white boxes are dimensions (each box shows key columns only). "
           "Order items connect to customers and dates through fact_orders, not directly. "
           "Two fact tables share the dimensions (a constellation schema).")

st.markdown('<div class="section-title">Tables</div>', unsafe_allow_html=True)
for name, description in TABLES.items():
    cols, count, sample = table_info(name)
    with st.expander(f"{name}  |  {count:,} rows  |  {len(cols)} columns"):
        st.caption(description)
        cols["description"] = [COLUMN_NOTES.get((name, c), "") for c in cols["column_name"]]
        left, right = st.columns([1, 1])
        with left:
            st.markdown("**Columns**")
            st.dataframe(cols, hide_index=True, width="stretch")
        with right:
            st.markdown("**Sample rows (first 5)**")
            st.dataframe(sample.drop(columns=["customer_name"], errors="ignore"),
                         hide_index=True, width="stretch")

st.caption("Customer names are hidden in the samples. The dataset is synthetic.")