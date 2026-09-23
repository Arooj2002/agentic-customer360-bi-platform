"""
extract.py
----------
Customer 360 BI Platform ka EXTRACT stage.
1) DummyJSON API se products, users, carts nikal kar data/raw/ mein save karta hai
2) Check karta hai ke Kaggle CSV files data/raw/kaggle/ mein maujood hain
"""

import json
import logging
from pathlib import Path

import requests

# ---------- Settings ----------
# Project ka root folder (src ka parent). Is se script kahin se bhi chalao, paths sahi rahenge
PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = PROJECT_ROOT / "data" / "raw"
KAGGLE_DIR = RAW_DIR / "kaggle"

BASE_URL = "https://dummyjson.com"
ENDPOINTS = ["products", "users", "carts"]   # API ke 3 resources

KAGGLE_FILES = [
    "customer_master.csv",
    "product_catalog.csv",
    "order_items.csv",
    "ecommerce_sales_customer_analytics_150k.csv",
    "dataset_statistics.csv",
]

# Logging: print() ki jagah professional tareeqa, har message ke sath time aata hai
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)


def fetch_dummyjson(endpoint: str) -> list:
    """DummyJSON se ek endpoint ka poora data laata hai (limit=0 = saare records)."""
    url = f"{BASE_URL}/{endpoint}?limit=0"
    logger.info(f"Fetching {url}")
    response = requests.get(url, timeout=30)   # 30 sec mein jawab na aaye to error
    response.raise_for_status()                # 404/500 jaisa error ho to script ruk jaye
    records = response.json()[endpoint]        # e.g. data["products"]
    logger.info(f"{endpoint}: {len(records)} records fetched")
    return records


def save_json(records: list, filename: str) -> None:
    """Records ko data/raw/ mein JSON file ki shakal mein save karta hai."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    file_path = RAW_DIR / filename
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2)
    logger.info(f"Saved -> {file_path}")


def check_kaggle_files() -> None:
    """Kaggle files manually download hoti hain, is liye sirf check karte hain ke maujood hain."""
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