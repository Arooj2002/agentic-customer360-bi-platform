"""Text-to-SQL agent for the Customer 360 marts (read-only, guarded)."""
import logging
import os
import re
import sys
import time
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, Engine

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MODEL_NAME = "openai/gpt-oss-20b"  # single place to switch models
MAX_ROWS = 200
STATEMENT_TIMEOUT_MS = 30_000

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("agent")

SCHEMA_TEXT = """
Database: PostgreSQL. Use only schema analytics_marts. Always prefix tables with analytics_marts.

fact_orders (one row per order; ALL revenue/profit/AOV/return/cancel KPIs come from here)
  order_id, customer_id -> dim_customers, order_date_key -> dim_date.date_key, order_date,
  order_status, sales_channel, payment_method, shipping_method, delivery_days,
  return_status, return_reason, customer_rating, marketing_channel, campaign_name,
  quantity, gross_sales, discount_amount, net_sales (= revenue), profit,
  profit_margin_percentage, customer_lifetime_value, is_repeat_customer, customer_order_count

fact_order_items (one row per product per order; use only for category/brand/product analysis)
  order_item_id, order_id -> fact_orders, product_id -> dim_products, quantity,
  unit_price, discount_amount, net_sales, profit, is_order_reconciled

dim_customers: customer_id, customer_name, customer_age, gender, customer_segment,
  customer_city, customer_state, customer_country, region, total_orders,
  first_order_date, last_order_date, is_never_purchased

dim_products: product_id, product_name, product_category, product_subcategory,
  brand, supplier, unit_price, product_cost, product_rating

dim_date: date_key, date_day, year, quarter, month, month_name, year_month, day_name, is_weekend

Rules:
- Revenue = SUM(fact_orders.net_sales). Profit = SUM(fact_orders.profit). Never use fact_order_items.net_sales for revenue.
- AOV = revenue / COUNT(DISTINCT order_id) from fact_orders.
- Return rate = orders with order_status = 'Returned' / all orders. Cancellation rate = order_status = 'Cancelled' / all orders.
- order_status values: Completed, Returned, Cancelled, Pending.
- Answer ONE question with ONE read-only SELECT query. Output only the SQL.
"""

FORBIDDEN = re.compile(
    r"\b(insert|update|delete|drop|alter|truncate|create|grant|revoke|copy|call|do)\b",
    re.IGNORECASE,
)


def check(condition: bool, message: str) -> None:
    """Fail loudly when a rule is violated."""
    if not condition:
        raise ValueError(message)


def get_engine() -> Engine:
    """Connect as the read-only agent role."""
    load_dotenv(PROJECT_ROOT / ".env")
    url = URL.create(
        drivername="postgresql+psycopg2",
        username=os.environ["AGENT_DB_USER"],
        password=os.environ["AGENT_DB_PASSWORD"],
        host=os.environ["SUPABASE_DB_HOST"],
        port=int(os.environ["SUPABASE_DB_PORT"]),
        database=os.environ["SUPABASE_DB_NAME"],
        query={"sslmode": "require"},
    )
    return create_engine(url)


def extract_sql(text_out: str) -> str:
    """Pull the SQL out of a markdown code fence if present."""
    match = re.search(r"```(?:sql)?\s*(.*?)```", text_out, re.DOTALL | re.IGNORECASE)
    return (match.group(1) if match else text_out).strip().rstrip(";").strip()


def validate_sql(sql: str) -> None:
    """Allow a single SELECT/WITH statement only (second line of defence after the DB role)."""
    check(sql != "", "The model returned no SQL.")
    check(";" not in sql, "Only one SQL statement is allowed.")
    check(sql.lower().startswith(("select", "with")), "Only SELECT queries are allowed.")
    check(not FORBIDDEN.search(sql), "Query contains a forbidden keyword.")


def generate_sql(llm: ChatGroq, question: str) -> tuple[str, int]:
    """Ask the LLM for SQL; retry a couple of times on rate limits."""
    for attempt in range(1, 4):
        try:
            response = llm.invoke([("system", SCHEMA_TEXT), ("human", question)])
            break
        except Exception as exc:  # noqa: BLE001
            is_rate_limit = "429" in str(exc) or "rate" in str(exc).lower()
            if is_rate_limit and attempt < 3:
                logger.warning("Rate limited, retrying in %s s", attempt * 10)
                time.sleep(attempt * 10)
                continue
            raise
    tokens = (response.usage_metadata or {}).get("total_tokens", 0)
    return extract_sql(response.content), tokens

def run_sql(engine: Engine, sql: str) -> pd.DataFrame:
    """Run validated SQL read-only with a timeout and a row cap."""
    validate_sql(sql)
    with engine.connect() as conn:
        conn.execute(text(f"SET statement_timeout = {STATEMENT_TIMEOUT_MS}"))
        df = pd.read_sql(text(sql), conn)
    return df.head(MAX_ROWS)


def ask(question: str, engine: Engine | None = None, llm: ChatGroq | None = None) -> dict:
    """Question in, dict out: sql, data, tokens, error (never raises to the caller)."""
    engine = engine or get_engine()
    llm = llm or ChatGroq(model=MODEL_NAME, temperature=0)
    result = {"question": question, "sql": None, "data": None, "tokens": 0, "error": None}
    try:
        result["sql"], result["tokens"] = generate_sql(llm, question)
        result["data"] = run_sql(engine, result["sql"])
        logger.info("OK | tokens=%s | rows=%s", result["tokens"], len(result["data"]))
    except Exception as exc:  # noqa: BLE001 - surface any failure as a friendly message
        result["error"] = f"{type(exc).__name__}: {str(exc).splitlines()[0]}"
        logger.warning("FAILED | %s", result["error"])
    return result


def main() -> None:
    question = " ".join(sys.argv[1:]) or "What is the total revenue and total profit?"
    out = ask(question)
    print("SQL:\n", out["sql"])
    print("Error:", out["error"])
    if out["data"] is not None:
        print(out["data"].to_string(index=False))


if __name__ == "__main__":
    main()