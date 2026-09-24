"""
Transform raw source data into clean, analysis-ready tables.

Reads the raw DummyJSON files written by extract.py and the manually
downloaded Kaggle CSVs, applies light cleaning (whitelisted columns,
snake_case names, correct data types, PII removal, business-meaning
null handling), validates the results and saves each table as Parquet
in data/processed/.

Business logic (KPIs, joins, star schema) is intentionally left to dbt.

Table naming:
    web_*  -> DummyJSON "web store API" source
    erp_*  -> Kaggle "main sales/ERP system" source

Usage:
    python src/transform.py
"""

import json
import logging
from pathlib import Path

import pandas as pd

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = PROJECT_ROOT / "data" / "raw"
KAGGLE_DIR = RAW_DIR / "kaggle"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Column whitelists: source column name -> clean snake_case name.
# Anything not listed here (including PII) is dropped.
# ---------------------------------------------------------------------------
WEB_USER_COLUMNS = {
    "id": "user_id",
    "firstName": "first_name",
    "lastName": "last_name",
    "age": "age",
    "gender": "gender",
    "role": "role",
    "address_city": "city",
    "address_state": "state",
    "address_stateCode": "state_code",
    "address_postalCode": "postal_code",
    "address_country": "country",
    "company_department": "company_department",
    "company_title": "job_title",
}

WEB_PRODUCT_COLUMNS = {
    "id": "product_id",
    "title": "product_name",
    "category": "category",
    "brand": "brand",
    "sku": "sku",
    "price": "price",
    "discountPercentage": "discount_percentage",
    "rating": "rating",
    "stock": "stock",
    "weight": "weight",
    "availabilityStatus": "availability_status",
    "minimumOrderQuantity": "minimum_order_quantity",
    "warrantyInformation": "warranty_information",
    "shippingInformation": "shipping_information",
    "returnPolicy": "return_policy",
    "meta_createdAt": "created_at",
}

# reviewerEmail is intentionally excluded (PII)
WEB_REVIEW_COLUMNS = {
    "id": "product_id",
    "rating": "review_rating",
    "comment": "review_comment",
    "date": "review_date",
    "reviewerName": "reviewer_name",
}

WEB_CART_COLUMNS = {
    "id": "cart_id",
    "userId": "user_id",
    "total": "total",
    "discountedTotal": "discounted_total",
    "totalProducts": "total_products",
    "totalQuantity": "total_quantity",
}

# title excluded (already in web_products), thumbnail excluded (not analytical)
WEB_CART_ITEM_COLUMNS = {
    "cart_id": "cart_id",
    "cart_userId": "user_id",
    "id": "product_id",
    "price": "price",
    "quantity": "quantity",
    "total": "total",
    "discountPercentage": "discount_percentage",
    "discountedTotal": "discounted_total",
}

# order_time is replaced by order_datetime
ERP_ORDER_COLUMNS = {
    "order_id": "order_id",
    "order_date": "order_date",
    "order_datetime": "order_datetime",
    "order_status": "order_status",
    "sales_channel": "sales_channel",
    "customer_id": "customer_id",
    "customer_name": "customer_name",
    "customer_age": "customer_age",
    "gender": "gender",
    "customer_segment": "customer_segment",
    "customer_type": "customer_type",
    "customer_city": "customer_city",
    "customer_state": "customer_state",
    "customer_country": "customer_country",
    "region": "region",
    "customer_postal_code": "customer_postal_code",
    "payment_method": "payment_method",
    "payment_status": "payment_status",
    "currency": "currency",
    "shipping_method": "shipping_method",
    "warehouse": "warehouse",
    "delivery_days": "delivery_days",
    "estimated_delivery_days": "estimated_delivery_days",
    "delivery_status": "delivery_status",
    "return_status": "return_status",
    "return_reason": "return_reason",
    "customer_rating": "customer_rating",
    "review_sentiment": "review_sentiment",
    "customer_review": "customer_review",
    "marketing_channel": "marketing_channel",
    "campaign_name": "campaign_name",
    "coupon_code": "coupon_code",
    "loyalty_points_earned": "loyalty_points_earned",
    "loyalty_points_redeemed": "loyalty_points_redeemed",
    "quantity": "quantity",
    "gross_sales": "gross_sales",
    "discount_amount": "discount_amount",
    "tax_amount": "tax_amount",
    "shipping_cost": "shipping_cost",
    "net_sales": "net_sales",
    "product_cost": "product_cost",
    "profit": "profit",
    "profit_margin_percentage": "profit_margin_percentage",
    "customer_lifetime_value": "customer_lifetime_value",
    "is_repeat_customer": "is_repeat_customer",
    "customer_order_count": "customer_order_count",
}

# Kaggle discount is a 0-1 fraction; renamed so it is never mixed up with
# DummyJSON's 0-100 discount_percentage
ERP_ORDER_ITEM_COLUMNS = {
    "order_id": "order_id",
    "product_id": "product_id",
    "quantity": "quantity",
    "unit_price": "unit_price",
    "discount_percentage": "discount_rate",
    "discount_amount": "discount_amount",
    "gross_sales": "gross_sales",
    "tax_amount": "tax_amount",
    "shipping_cost": "shipping_cost",
    "net_sales": "net_sales",
    "product_cost": "product_cost",
    "profit": "profit",
}

ERP_CUSTOMER_COLUMNS = {
    "customer_id": "customer_id",
    "customer_name": "customer_name",
    "customer_age": "customer_age",
    "gender": "gender",
    "customer_segment": "customer_segment",
    "customer_city": "customer_city",
    "customer_state": "customer_state",
    "customer_country": "customer_country",
    "region": "region",
    "customer_postal_code": "customer_postal_code",
    "customer_acquisition_cost": "customer_acquisition_cost",
}

ERP_PRODUCT_COLUMNS = {
    "product_id": "product_id",
    "product_name": "product_name",
    "product_category": "product_category",
    "product_subcategory": "product_subcategory",
    "brand": "brand",
    "supplier": "supplier",
    "unit_price": "unit_price",
    "product_cost": "product_cost",
    "product_rating": "product_rating",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def load_json(file_name: str) -> list[dict]:
    """Load a raw JSON file written by extract.py."""
    with open(RAW_DIR / file_name, encoding="utf-8") as f:
        data = json.load(f)
    logger.info("Loaded %s: %d records", file_name, len(data))
    return data


def select_columns(df: pd.DataFrame, mapping: dict[str, str]) -> pd.DataFrame:
    """Keep only whitelisted columns and rename them to snake_case."""
    return df[list(mapping)].rename(columns=mapping)


def check(condition: bool, message: str) -> None:
    """Stop the pipeline if a data quality check fails."""
    if not condition:
        raise ValueError(f"Data quality check failed: {message}")
    logger.info("Check passed: %s", message)


# ---------------------------------------------------------------------------
# DummyJSON (web store) transforms
# ---------------------------------------------------------------------------
def transform_web_users(users_raw: list[dict]) -> pd.DataFrame:
    """Flatten nested user records and keep non-PII analytical columns."""
    users_df = pd.json_normalize(users_raw, sep="_")
    return select_columns(users_df, WEB_USER_COLUMNS)


def transform_web_products(products_raw: list[dict]) -> pd.DataFrame:
    """Flatten products, label missing brands and parse creation timestamps."""
    products_df = pd.json_normalize(products_raw, sep="_")
    products = select_columns(products_df, WEB_PRODUCT_COLUMNS)

    # Products without a brand are generic items, so label them explicitly
    products["brand"] = products["brand"].fillna("Unbranded")
    products["created_at"] = pd.to_datetime(products["created_at"])
    return products


def transform_web_reviews(products_raw: list[dict]) -> pd.DataFrame:
    """Explode the nested reviews list into one row per review."""
    reviews_df = pd.json_normalize(products_raw, record_path="reviews", meta=["id"])
    reviews = select_columns(reviews_df, WEB_REVIEW_COLUMNS)
    reviews["review_date"] = pd.to_datetime(reviews["review_date"])

    # Surrogate key: the source provides no review identifier
    reviews.insert(0, "review_id", range(1, len(reviews) + 1))
    return reviews


def transform_web_carts(carts_raw: list[dict]) -> pd.DataFrame:
    """Build the cart header table (one row per cart)."""
    carts_df = pd.json_normalize(carts_raw)
    return select_columns(carts_df, WEB_CART_COLUMNS)


def transform_web_cart_items(carts_raw: list[dict]) -> pd.DataFrame:
    """Explode each cart's products list into one row per product per cart."""
    items_df = pd.json_normalize(
        carts_raw,
        record_path="products",
        meta=["id", "userId"],
        meta_prefix="cart_",  # avoids clash between cart id and product id
    )
    items = select_columns(items_df, WEB_CART_ITEM_COLUMNS)

    # Meta columns can arrive as generic object type; align ID types for joins
    items[["cart_id", "user_id"]] = items[["cart_id", "user_id"]].astype("int64")

    # Surrogate key: the same product can appear on more than one line of a cart
    # (header totals count each line), so (cart_id, product_id) is not unique
    items.insert(0, "cart_item_id", range(1, len(items) + 1))
    return items

# ---------------------------------------------------------------------------
# Kaggle (ERP) transforms
# ---------------------------------------------------------------------------
def transform_erp_orders() -> pd.DataFrame:
    """Clean the orders table: timestamps, text postal codes, labelled nulls."""
    orders = pd.read_csv(
        KAGGLE_DIR / "ecommerce_sales_customer_analytics_150k.csv",
        dtype={"customer_postal_code": str},
    )

    # Combine date + time into one timestamp; keep a pure date for reporting
    orders["order_datetime"] = pd.to_datetime(
        orders["order_date"] + " " + orders["order_time"],
        format="%Y-%m-%d %H:%M:%S",
    )
    orders["order_date"] = pd.to_datetime(orders["order_date"], format="%Y-%m-%d")

    # campaign_name is NULL across all channels, including paid ones, so it
    # means "campaign not tracked" rather than "organic"
    orders["campaign_name"] = orders["campaign_name"].fillna("Unattributed")
    # coupon_code NULL simply means no coupon was used
    orders["coupon_code"] = orders["coupon_code"].fillna("No Coupon")

    # Delivery, review and return NULLs are kept on purpose: they belong to
    # orders that were never delivered, reviewed or returned
    return select_columns(orders, ERP_ORDER_COLUMNS)


def transform_erp_order_items() -> pd.DataFrame:
    """Clean order line items (product per order)."""
    order_items = pd.read_csv(KAGGLE_DIR / "order_items.csv")
    return select_columns(order_items, ERP_ORDER_ITEM_COLUMNS)


def transform_erp_customers() -> pd.DataFrame:
    """Clean the customer dimension and restore lost postal code zeros."""
    customers = pd.read_csv(
        KAGGLE_DIR / "customer_master.csv",
        dtype={"customer_postal_code": str},
    )
    # The source stored postal codes as numbers, dropping leading zeros
    customers["customer_postal_code"] = customers["customer_postal_code"].str.zfill(5)
    return select_columns(customers, ERP_CUSTOMER_COLUMNS)


def transform_erp_products() -> pd.DataFrame:
    """Clean the product dimension (already clean at source)."""
    products = pd.read_csv(KAGGLE_DIR / "product_catalog.csv")
    return select_columns(products, ERP_PRODUCT_COLUMNS)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
def validate_web_tables(tables: dict[str, pd.DataFrame]) -> None:
    """Integrity and reconciliation checks for the DummyJSON tables."""
    carts = tables["web_carts"]
    items = tables["web_cart_items"]

    check(
        items["cart_item_id"].is_unique,
        "web_cart_items has a unique cart_item_id",
    )
    check(
        items["product_id"].isin(tables["web_products"]["product_id"]).all(),
        "every web_cart_items.product_id exists in web_products",
    )
    check(
        items["user_id"].isin(tables["web_users"]["user_id"]).all(),
        "every web_cart_items.user_id exists in web_users",
    )

    # Cart header totals must equal the sum of their line items
    items_agg = items.groupby("cart_id").agg(
        items_total=("total", "sum"),
        items_discounted_total=("discounted_total", "sum"),
        items_count=("product_id", "count"),
        items_quantity=("quantity", "sum"),
    ).reset_index()
    recon = carts.merge(items_agg, on="cart_id", how="left")

    check(
        ((recon["total"] - recon["items_total"]).abs() <= 0.01).all()
        and ((recon["discounted_total"] - recon["items_discounted_total"]).abs() <= 0.01).all()
        and (recon["total_products"] == recon["items_count"]).all()
        and (recon["total_quantity"] == recon["items_quantity"]).all(),
        "web_carts totals reconcile with web_cart_items",
    )


def validate_erp_tables(tables: dict[str, pd.DataFrame]) -> None:
    """Type and value checks for the Kaggle tables."""
    orders = tables["erp_orders"]

    check(
        orders[["campaign_name", "coupon_code"]].notna().all().all(),
        "erp_orders campaign_name and coupon_code have no NULLs",
    )
    check(
        (orders["customer_postal_code"].str.len() == 5).all()
        and (tables["erp_customers"]["customer_postal_code"].str.len() == 5).all(),
        "all postal codes are 5 characters",
    )
    check(
        tables["erp_order_items"]["discount_rate"].between(0, 1).all(),
        "erp_order_items discount_rate is between 0 and 1",
    )
    logger.info(
        "erp_orders date range: %s to %s",
        orders["order_date"].min().date(),
        orders["order_date"].max().date(),
    )


# ---------------------------------------------------------------------------
# Save
# ---------------------------------------------------------------------------
def save_parquet(df: pd.DataFrame, table_name: str) -> None:
    """Save a table as Parquet so data types (text codes, dates) are preserved."""
    path = PROCESSED_DIR / f"{table_name}.parquet"
    df.to_parquet(path, index=False)
    logger.info("Saved %s: %d rows x %d cols", path.name, df.shape[0], df.shape[1])


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main() -> None:
    """Run all transforms, validate the results and save them to data/processed/."""
    logger.info("Transform started")

    users_raw = load_json("users_raw.json")
    products_raw = load_json("products_raw.json")
    carts_raw = load_json("carts_raw.json")

    tables = {
        "web_users": transform_web_users(users_raw),
        "web_products": transform_web_products(products_raw),
        "web_reviews": transform_web_reviews(products_raw),
        "web_carts": transform_web_carts(carts_raw),
        "web_cart_items": transform_web_cart_items(carts_raw),
        "erp_orders": transform_erp_orders(),
        "erp_order_items": transform_erp_order_items(),
        "erp_customers": transform_erp_customers(),
        "erp_products": transform_erp_products(),
    }

    # Validate everything before writing anything
    validate_web_tables(tables)
    validate_erp_tables(tables)

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    for table_name, df in tables.items():
        save_parquet(df, table_name)

    logger.info("Transform finished: %d tables saved to %s", len(tables), PROCESSED_DIR)


if __name__ == "__main__":
    main()