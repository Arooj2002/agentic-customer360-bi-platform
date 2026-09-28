"""
Load processed tables into Supabase (PostgreSQL).

Reads the validated Parquet files written by transform.py and loads each
one into the `raw` schema of the Supabase database using PostgreSQL COPY.
Every table is replaced inside its own transaction, so a failed load
leaves the previous version of that table untouched.

The raw schema keeps data in source shape. Type refinement (e.g. NUMERIC
money columns) and business logic are intentionally left to dbt.

Connection settings are read from the .env file in the project root:
    SUPABASE_DB_HOST, SUPABASE_DB_PORT, SUPABASE_DB_NAME,
    SUPABASE_DB_USER, SUPABASE_DB_PASSWORD

Usage:
    python src/load.py
"""

import io
import logging
import os
import time
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, Engine

# ---------------------------------------------------------------------------
# Paths and settings
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
ENV_FILE = PROJECT_ROOT / ".env"

# Source-shaped data lives in its own schema, which Supabase does not
# expose through its auto-generated REST API (unlike `public`)
TARGET_SCHEMA = "raw"

# Supabase's default statement_timeout (2 min) is too short for large COPY
# loads over a home internet connection; raised per transaction only
LOAD_TIMEOUT = "10min"

TABLES = [
    "web_users",
    "web_products",
    "web_reviews",
    "web_carts",
    "web_cart_items",
    "erp_orders",
    "erp_order_items",
    "erp_customers",
    "erp_products",
]

REQUIRED_ENV_VARS = [
    "SUPABASE_DB_HOST",
    "SUPABASE_DB_PORT",
    "SUPABASE_DB_NAME",
    "SUPABASE_DB_USER",
    "SUPABASE_DB_PASSWORD",
]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def check(condition: bool, message: str) -> None:
    """Stop the pipeline if a data quality check fails."""
    if not condition:
        raise ValueError(f"Data quality check failed: {message}")
    logger.info("Check passed: %s", message)


def get_engine() -> Engine:
    """Build a SQLAlchemy engine for Supabase from the .env settings."""
    load_dotenv(ENV_FILE)

    missing = [name for name in REQUIRED_ENV_VARS if not os.getenv(name)]
    if missing:
        raise ValueError(f"Missing connection settings in .env: {', '.join(missing)}")

    # Built from parts so special characters in the password are encoded safely
    db_url = URL.create(
        drivername="postgresql+psycopg2",
        username=os.getenv("SUPABASE_DB_USER"),
        password=os.getenv("SUPABASE_DB_PASSWORD"),
        host=os.getenv("SUPABASE_DB_HOST"),
        port=int(os.getenv("SUPABASE_DB_PORT")),
        database=os.getenv("SUPABASE_DB_NAME"),
    )
    # sslmode=require encrypts traffic between this machine and Supabase
    return create_engine(db_url, connect_args={"sslmode": "require"})


def read_table(table_name: str) -> pd.DataFrame:
    """Read one processed Parquet table written by transform.py."""
    df = pd.read_parquet(PROCESSED_DIR / f"{table_name}.parquet")
    logger.info("Read %s: %d rows x %d cols", table_name, df.shape[0], df.shape[1])
    return df


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
def validate_before_load(df: pd.DataFrame, table_name: str) -> None:
    """Checks that must pass before a table is sent to the database."""
    check(len(df) > 0, f"{table_name} is not empty")

    # COPY in CSV format reads empty values as NULL, so a real empty string
    # would silently turn into NULL in the database
    text_cols = df.select_dtypes(include="str").columns
    empty_strings = int((df[text_cols] == "").sum().sum())
    check(
        empty_strings == 0,
        f"{table_name} has no empty strings that COPY would turn into NULL",
    )


def verify_row_count(engine: Engine, df: pd.DataFrame, table_name: str) -> None:
    """Confirm the database holds exactly as many rows as the Parquet file."""
    with engine.connect() as conn:
        db_rows = conn.execute(
            text(f"SELECT COUNT(*) FROM {TARGET_SCHEMA}.{table_name}")
        ).scalar()
    check(
        db_rows == len(df),
        f"{TARGET_SCHEMA}.{table_name} row count matches Parquet ({db_rows:,} rows)",
    )


# ---------------------------------------------------------------------------
# Load
# ---------------------------------------------------------------------------
def copy_table(engine: Engine, df: pd.DataFrame, table_name: str) -> None:
    """Replace raw.<table_name> with df using PostgreSQL COPY (fast bulk load)."""
    columns = ", ".join(f'"{col}"' for col in df.columns)

    # Serialise the table to an in-memory CSV stream (no temporary file on disk)
    buffer = io.StringIO()
    df.to_csv(buffer, index=False, header=False)
    buffer.seek(0)

    # One transaction per table: if COPY fails, the drop/create is rolled back
    # and the previous version of the table stays in place
    with engine.begin() as conn:
        conn.execute(text(f"SET LOCAL statement_timeout = '{LOAD_TIMEOUT}'"))
        # Create the empty table with column types inferred from the DataFrame
        df.head(0).to_sql(
            table_name, conn, schema=TARGET_SCHEMA, if_exists="replace", index=False
        )
        with conn.connection.cursor() as cur:
            cur.copy_expert(
                f"COPY {TARGET_SCHEMA}.{table_name} ({columns}) FROM STDIN WITH (FORMAT csv)",
                buffer,
            )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main() -> None:
    """Validate all processed tables, then load them into the raw schema."""
    logger.info("Load started")
    run_start = time.perf_counter()

    engine = get_engine()

    tables = {name: read_table(name) for name in TABLES}

    # Validate everything before writing anything
    for table_name, df in tables.items():
        validate_before_load(df, table_name)

    try:
        with engine.begin() as conn:
            conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {TARGET_SCHEMA}"))

        for table_name, df in tables.items():
            table_start = time.perf_counter()
            copy_table(engine, df, table_name)
            verify_row_count(engine, df, table_name)
            logger.info(
                "Loaded %s.%s in %.1f s",
                TARGET_SCHEMA,
                table_name,
                time.perf_counter() - table_start,
            )
    finally:
        # Release pooled connections (free tier allows a limited number)
        engine.dispose()

    logger.info(
        "Load finished: %d tables loaded into schema '%s' in %.1f s",
        len(tables),
        TARGET_SCHEMA,
        time.perf_counter() - run_start,
    )


if __name__ == "__main__":
    main()