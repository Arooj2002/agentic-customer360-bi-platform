"""
extract.py
----------
EXTRACT stage of the Customer 360 BI Platform.
1) Fetches products, users, and carts from the DummyJSON API and saves them to data/raw/
2) Verifies that the Kaggle CSV files exist in data/raw/kaggle/
"""

import json
import logging
from pathlib import Path

import requests

# ---------- Configuration ----------
# Project root (parent of src/), so paths resolve correctly from any working directory
PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = PROJECT_ROOT / "data" / "raw"
KAGGLE_DIR = RAW_DIR / "kaggle"

BASE_URL = "https://dummyjson.com"
ENDPOINTS = ["products", "users", "carts"]   # API resources to extract

KAGGLE_FILES = [
    "customer_master.csv",
    "product_catalog.csv",
    "order_items.csv",
    "ecommerce_sales_customer_analytics_150k.csv",
    "dataset_statistics.csv",
]

# Structured logging with timestamps (also shows up in Airflow task logs)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)


def fetch_dummyjson(endpoint: str) -> list:
    """Fetch all records for a DummyJSON endpoint (limit=0 returns every record)."""
    url = f"{BASE_URL}/{endpoint}?limit=0"
    logger.info(f"Fetching {url}")
    response = requests.get(url, timeout=30)   # Fail if no response within 30 seconds
    response.raise_for_status()                # Raise an error on HTTP 4xx/5xx
    records = response.json()[endpoint]        # e.g. data["products"]
    logger.info(f"{endpoint}: {len(records)} records fetched")
    return records


def save_json(records: list, filename: str) -> None:
    """Save records as a JSON file in data/raw/."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    file_path = RAW_DIR / filename
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2)
    logger.info(f"Saved -> {file_path}")


def check_kaggle_files() -> None:
    """Kaggle files are downloaded manually, so only verify that they exist."""
    missing = [f for f in KAGGLE_FILES if not (KAGGLE_DIR / f).exists()]
    if missing:
        raise FileNotFoundError(f"Kaggle files missing in {KAGGLE_DIR}: {missing}")
    logger.info(f"All {len(KAGGLE_FILES)} Kaggle files found")


def main() -> None:
    logger.info("===== EXTRACT STAGE STARTED =====")
    for endpoint in ENDPOINTS:
        records = fetch_dummyjson(endpoint)
        save_json(records, f"{endpoint}_raw.json")
    check_kaggle_files()
    logger.info("===== EXTRACT STAGE COMPLETED =====")


if __name__ == "__main__":
    main()