"""
Zindabad PK — Cross-Border Supply Chain ETL & Audit Variance Pipeline
Author: Muhammad Adil
Repository: github.com/ZindabadPK/zindabad-pk-supply-chain-analytics

Description:
    Ingests raw supplier and Amazon FBA cost data (CSV or fallback records),
    normalizes multi-currency (PKR/USD) unit economics into a 4-table SQLite
    relational schema, and executes an automated audit variance query to flag
    cost understatements and margin risks prior to batch procurement.
"""

import os
import sqlite3
import pandas as pd


DB_PATH = "zindabad_pk_analytics.db"
CSV_PATH = "Amazon_Budget.csv"
DEFAULT_FX_RATE = 276.60  # PKR per $1.00 USD


def create_schema(conn: sqlite3.Connection) -> None:
    """Create the normalized 4-table relational schema."""
    schema_sql = """
    DROP TABLE IF EXISTS procurement_batches;
    DROP TABLE IF EXISTS amazon_fee_schedules;
    DROP TABLE IF EXISTS products;
    DROP TABLE IF EXISTS exchange_rates;

    CREATE TABLE exchange_rates (
        currency_pair VARCHAR(10) PRIMARY KEY,
        rate_to_usd DECIMAL(10, 4) NOT NULL,
        effective_date DATE NOT NULL
    );

    CREATE TABLE products (
        sku_id VARCHAR(20) PRIMARY KEY,
        product_name VARCHAR(100) NOT NULL,
        category VARCHAR(50) NOT NULL,
        unit_weight_kg DECIMAL(6, 2),
        unit_cogs_pkr DECIMAL(10, 2) NOT NULL,
        intl_shipping_pkr DECIMAL(10, 2) NOT NULL,
        target_price_usd DECIMAL(10, 2) NOT NULL
    );

    CREATE TABLE amazon_fee_schedules (
        fee_id INTEGER PRIMARY KEY,
        sku_id VARCHAR(20) REFERENCES products(sku_id),
        referral_fee_pct DECIMAL(5, 4) NOT NULL,
        fba_fulfillment_usd DECIMAL(10, 2) NOT NULL,
        monthly_storage_per_unit_usd DECIMAL(10, 4) NOT NULL,
        monthly_pro_sub_usd DECIMAL(10, 2) NOT NULL
    );

    CREATE TABLE procurement_batches (
        batch_id VARCHAR(20) PRIMARY KEY,
        sku_id VARCHAR(20) REFERENCES products(sku_id),
        batch_date DATE NOT NULL,
        order_qty DECIMAL(10, 2) NOT NULL,
        legacy_recorded_expense_usd DECIMAL(10, 2)
    );
    """
    conn.executescript(schema_sql)
    conn.commit()


def extract_and_transform(csv_path: str) -> dict[str, pd.DataFrame]:
    """
    Extract raw supplier figures from Amazon_Budget.csv (if present) and
    structure them into clean, normalized DataFrames for database loading.
    """
    fx_rate = DEFAULT_FX_RATE
    base_cogs_pkr = 3000.00
    base_ship_pkr = 1500.00
    base_qty = 50.0
    base_price_usd = 50.00
    legacy_expense_usd = 1144.01
    fba_fee_usd = 5.81
    storage_fee_usd = 0.0864
    pro_sub_usd = 39.99

    # Parse legacy CSV if available in working directory to verify raw inputs
    if os.path.exists(csv_path):
        raw_df = pd.read_csv(csv_path, header=None, names=["item", "pkr", "usd", "extra"])
        raw_df["item"] = raw_df["item"].astype(str).str.strip()
        raw_df["pkr_num"] = pd.to_numeric(raw_df["pkr"], errors="coerce")
        raw_df["usd_num"] = pd.to_numeric(raw_df["usd"], errors="coerce")

        # Keep only rows with valid numeric currency figures
        numeric_rows = raw_df.dropna(subset=["pkr_num", "usd_num"]).set_index("item")

        if "Cost of Good" in numeric_rows.index:
            base_cogs_pkr = float(numeric_rows.loc["Cost of Good", "pkr_num"])
            implied_usd = float(numeric_rows.loc["Cost of Good", "usd_num"])
            if implied_usd > 0:
                fx_rate = round(base_cogs_pkr / implied_usd, 2)
        if "Cost of Shipping per Unit" in numeric_rows.index:
            base_ship_pkr = float(numeric_rows.loc["Cost of Shipping per Unit", "pkr_num"])
        if "Total Expenses" in numeric_rows.index:
            legacy_expense_usd = float(numeric_rows.loc["Total Expenses", "usd_num"])

    df_fx = pd.DataFrame([
        {"currency_pair": "PKR/USD", "rate_to_usd": fx_rate, "effective_date": "2026-11-01"}
    ])

    df_products = pd.DataFrame([
        {
            "sku_id": "ZPK-APP-01",
            "product_name": "Base Apparel (50-Unit Batch)",
            "category": "Apparel",
            "unit_weight_kg": 0.70,
            "unit_cogs_pkr": base_cogs_pkr,
            "intl_shipping_pkr": base_ship_pkr,
            "target_price_usd": base_price_usd,
        },
        {
            "sku_id": "ZPK-DRS-02",
            "product_name": "Embroidered Dresses (35kg Batch)",
            "category": "Apparel",
            "unit_weight_kg": 0.70,
            "unit_cogs_pkr": 7000.00,
            "intl_shipping_pkr": base_ship_pkr,
            "target_price_usd": 65.00,
        },
        {
            "sku_id": "ZPK-MAT-03",
            "product_name": "Artisan Woven Mats",
            "category": "Home Goods",
            "unit_weight_kg": 1.50,
            "unit_cogs_pkr": 53000.00,
            "intl_shipping_pkr": 0.00,
            "target_price_usd": 668.00,
        },
        {
            "sku_id": "ZPK-VAL-04",
            "product_name": "Value Tier Apparel ($30 Promo)",
            "category": "Apparel",
            "unit_weight_kg": 0.70,
            "unit_cogs_pkr": base_cogs_pkr,
            "intl_shipping_pkr": base_ship_pkr,
            "target_price_usd": 30.00,
        },
    ])

    # Pre-compute USD landed equivalents in pandas for verification
    df_products["unit_cogs_usd"] = (df_products["unit_cogs_pkr"] / fx_rate).round(2)
    df_products["intl_shipping_usd"] = (df_products["intl_shipping_pkr"] / fx_rate).round(2)

    df_fees = pd.DataFrame([
        {"fee_id": 1, "sku_id": "ZPK-APP-01", "referral_fee_pct": 0.1700, "fba_fulfillment_usd": fba_fee_usd, "monthly_storage_per_unit_usd": storage_fee_usd, "monthly_pro_sub_usd": pro_sub_usd},
        {"fee_id": 2, "sku_id": "ZPK-DRS-02", "referral_fee_pct": 0.1700, "fba_fulfillment_usd": fba_fee_usd, "monthly_storage_per_unit_usd": storage_fee_usd, "monthly_pro_sub_usd": pro_sub_usd},
        {"fee_id": 3, "sku_id": "ZPK-MAT-03", "referral_fee_pct": 0.1700, "fba_fulfillment_usd": 0.00,        "monthly_storage_per_unit_usd": storage_fee_usd, "monthly_pro_sub_usd": pro_sub_usd},
        {"fee_id": 4, "sku_id": "ZPK-VAL-04", "referral_fee_pct": 0.1700, "fba_fulfillment_usd": fba_fee_usd, "monthly_storage_per_unit_usd": storage_fee_usd, "monthly_pro_sub_usd": pro_sub_usd},
    ])

    df_batches = pd.DataFrame([
        {"batch_id": "BATCH-001", "sku_id": "ZPK-APP-01", "batch_date": "2026-10-15", "order_qty": base_qty, "legacy_recorded_expense_usd": legacy_expense_usd},
        {"batch_id": "BATCH-002", "sku_id": "ZPK-DRS-02", "batch_date": "2026-10-22", "order_qty": 50.0,     "legacy_recorded_expense_usd": None},
        {"batch_id": "BATCH-003", "sku_id": "ZPK-MAT-03", "batch_date": "2026-10-28", "order_qty": 23.6,     "legacy_recorded_expense_usd": None},
        {"batch_id": "BATCH-004", "sku_id": "ZPK-VAL-04", "batch_date": "2026-11-02", "order_qty": 53.0,     "legacy_recorded_expense_usd": 1590.00},
    ])

    # Drop helper columns before loading into normalized SQL schema
    db_products = df_products.drop(columns=["unit_cogs_usd", "intl_shipping_usd"])

    return {
        "exchange_rates": df_fx,
        "products": db_products,
        "amazon_fee_schedules": df_fees,
        "procurement_batches": df_batches,
    }


def load_to_sqlite(conn: sqlite3.Connection, tables: dict[str, pd.DataFrame]) -> None:
    """Load transformed DataFrames into the SQLite relational database."""
    for table_name, df in tables.items():
        df.to_sql(table_name, conn, if_exists="append", index=False)


def run_audit_reports(conn: sqlite3.Connection) -> None:
    """Execute SQL unit-economics and audit variance queries and print reports."""
    unit_econ_query = """
    WITH unit_economics AS (
        SELECT
            p.sku_id,
            p.product_name,
            b.order_qty,
            p.target_price_usd,
            ROUND((p.unit_cogs_pkr + p.intl_shipping_pkr) / fx.rate_to_usd, 2) AS landed_supplier_usd,
            ROUND(p.target_price_usd * f.referral_fee_pct, 2) AS referral_fee_usd,
            f.fba_fulfillment_usd,
            ROUND((f.monthly_pro_sub_usd + (f.monthly_storage_per_unit_usd * b.order_qty)) / b.order_qty, 2) AS overhead_per_unit_usd
        FROM products p
        JOIN amazon_fee_schedules f ON p.sku_id = f.sku_id
        JOIN procurement_batches b ON p.sku_id = b.sku_id
        JOIN exchange_rates fx ON fx.currency_pair = 'PKR/USD'
    )
    SELECT
        sku_id,
        product_name,
        order_qty,
        target_price_usd,
        ROUND(landed_supplier_usd + referral_fee_usd + fba_fulfillment_usd + overhead_per_unit_usd, 2) AS break_even_unit_cost_usd,
        ROUND(target_price_usd - (landed_supplier_usd + referral_fee_usd + fba_fulfillment_usd + overhead_per_unit_usd), 2) AS net_profit_per_unit_usd,
        ROUND(((target_price_usd - (landed_supplier_usd + referral_fee_usd + fba_fulfillment_usd + overhead_per_unit_usd)) / target_price_usd) * 100, 1) AS net_margin_pct
    FROM unit_economics
    ORDER BY net_margin_pct DESC;
    """

    audit_variance_query = """
    SELECT
        b.batch_id,
        p.sku_id,
        b.order_qty,
        b.legacy_recorded_expense_usd,
        ROUND(
            b.order_qty * (
                (p.unit_cogs_pkr + p.intl_shipping_pkr) / fx.rate_to_usd
                + f.fba_fulfillment_usd
                + (p.target_price_usd * f.referral_fee_pct)
                + f.monthly_storage_per_unit_usd
            ) + f.monthly_pro_sub_usd, 2
        ) AS reconciled_total_usd,
        ROUND(
            (b.order_qty * (
                (p.unit_cogs_pkr + p.intl_shipping_pkr) / fx.rate_to_usd
                + f.fba_fulfillment_usd
                + (p.target_price_usd * f.referral_fee_pct)
                + f.monthly_storage_per_unit_usd
            ) + f.monthly_pro_sub_usd) - b.legacy_recorded_expense_usd, 2
        ) AS variance_gap_usd
    FROM procurement_batches b
    JOIN products p ON b.sku_id = p.sku_id
    JOIN amazon_fee_schedules f ON p.sku_id = f.sku_id
    JOIN exchange_rates fx ON fx.currency_pair = 'PKR/USD'
    WHERE b.legacy_recorded_expense_usd IS NOT NULL
      AND ABS(reconciled_total_usd - b.legacy_recorded_expense_usd) > 10.00;
    """

    df_margins = pd.read_sql_query(unit_econ_query, conn)
    df_audit = pd.read_sql_query(audit_variance_query, conn)

    print("=" * 78)
    print("ZINDABAD PK — RECONCILED SKU UNIT ECONOMICS & MARGIN REPORT")
    print("=" * 78)
    print(df_margins.to_string(index=False))

    print("\n" + "=" * 78)
    print("AUTOMATED AUDIT VARIANCE REPORT (FLAGGED DISCREPANCIES > $10.00)")
    print("=" * 78)
    print(df_audit.to_string(index=False))


def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    try:
        create_schema(conn)
        tables = extract_and_transform(CSV_PATH)
        load_to_sqlite(conn, tables)
        run_audit_reports(conn)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
