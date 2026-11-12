"""
Zindabad PK — Automated Supply Chain & Unit Economics ETL Pipeline
Fetches live USD/PKR exchange rates (with offline fallback), ingests raw
procurement batch CSVs, loads a normalized SQLite database, and runs an
ANSI-SQL / PostgreSQL-compatible nested CTE audit to flag cost variances > $10.
"""

import json
import os
import sqlite3
import urllib.request
from datetime import date
import pandas as pd

# Configuration
DB_PATH = "zindabad_pk_supply_chain.db"
CSV_DIR = "data"
EXCHANGE_RATE_API = "https://open.er-api.com/v6/latest/USD"
FALLBACK_USD_TO_PKR = 278.5000


def fetch_live_usd_to_pkr() -> float:
    """Fetch live USD -> PKR exchange rate via REST API with offline fallback."""
    try:
        req = urllib.request.Request(
            EXCHANGE_RATE_API, headers={"User-Agent": "ZindabadPK-ETL/1.0"}
        )
        with urllib.request.urlopen(req, timeout=8) as response:
            payload = json.loads(response.read().decode("utf-8"))
            rate = float(payload["rates"]["PKR"])
            print(f"[INFO] Live USD/PKR rate fetched: {rate:.4f}")
            return round(rate, 4)
    except Exception as exc:
        print(f"[WARN] Live FX fetch failed ({exc}). Using fallback rate: {FALLBACK_USD_TO_PKR:.4f}")
        return FALLBACK_USD_TO_PKR


def initialize_database(conn: sqlite3.Connection) -> None:
    """Create normalized 4-table relational schema (ANSI-SQL / PostgreSQL compatible)."""
    cursor = conn.cursor()
    cursor.executescript(
        """
        DROP TABLE IF EXISTS procurement_batches;
        DROP TABLE IF EXISTS amazon_fee_schedules;
        DROP TABLE IF EXISTS products;
        DROP TABLE IF EXISTS exchange_rates;

        CREATE TABLE exchange_rates (
            rate_date DATE PRIMARY KEY,
            usd_to_pkr DECIMAL(10, 4) NOT NULL CHECK (usd_to_pkr > 0)
        );

        CREATE TABLE products (
            sku VARCHAR(50) PRIMARY KEY,
            product_name VARCHAR(150) NOT NULL,
            category VARCHAR(100),
            target_retail_price_usd DECIMAL(10, 2) NOT NULL CHECK (target_retail_price_usd > 0)
        );

        CREATE TABLE amazon_fee_schedules (
            sku VARCHAR(50) PRIMARY KEY,
            referral_fee_pct DECIMAL(5, 4) NOT NULL,
            fba_fulfillment_fee_usd DECIMAL(10, 2) NOT NULL,
            monthly_storage_per_unit_usd DECIMAL(10, 2) NOT NULL,
            FOREIGN KEY (sku) REFERENCES products(sku)
        );

        CREATE TABLE procurement_batches (
            batch_id VARCHAR(50) PRIMARY KEY,
            sku VARCHAR(50) NOT NULL,
            rate_date DATE NOT NULL,
            units_ordered INT NOT NULL CHECK (units_ordered > 0),
            unit_cogs_pkr DECIMAL(12, 2) NOT NULL,
            freight_per_unit_pkr DECIMAL(12, 2) NOT NULL,
            customs_duty_usd DECIMAL(10, 2) NOT NULL DEFAULT 0.00,
            reported_landed_cost_usd DECIMAL(12, 2) NOT NULL,
            FOREIGN KEY (sku) REFERENCES products(sku),
            FOREIGN KEY (rate_date) REFERENCES exchange_rates(rate_date)
        );
        """
    )
    conn.commit()


def load_data(conn: sqlite3.Connection, live_rate: float) -> None:
    """Load CSV files from data/ if available, otherwise seed default batch records."""
    today_str = date.today().isoformat()

    rates_df = pd.DataFrame(
        [
            {"rate_date": "2026-09-15", "usd_to_pkr": 278.5000},
            {"rate_date": "2026-10-01", "usd_to_pkr": 279.1000},
            {"rate_date": today_str, "usd_to_pkr": live_rate},
        ]
    ).drop_duplicates(subset=["rate_date"])

    products_path = os.path.join(CSV_DIR, "products.csv")
    fees_path = os.path.join(CSV_DIR, "amazon_fee_schedules.csv")
    batches_path = os.path.join(CSV_DIR, "procurement_batches.csv")

    if all(os.path.exists(p) for p in [products_path, fees_path, batches_path]):
        products_df = pd.read_csv(products_path)
        fees_df = pd.read_csv(fees_path)
        batches_
