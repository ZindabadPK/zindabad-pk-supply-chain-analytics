![Zindabad PK Brand Header](images/zindabad_pk_banner.jpg)
# Zindabad PK: Cross-Border Supply Chain & Unit Economics Analytics

**Tech Stack:** `SQL (PostgreSQL / SQLite)` · `Python (pandas / sqlite3)` · `Microsoft Excel (Financial Modeling)` · `Cross-Border Logistics (PKR / USD)`

## 1. Business Overview
**Zindabad PK** is a New Jersey-registered e-commerce and cross-border trading operation sourcing regional apparel and home goods from Lahore, Pakistan for distribution via **Amazon FBA** in the United States.

To eliminate pricing guesswork and protect margins against international freight and marketplace fees, I designed a **normalized 4-table relational SQL database**, an **automated Python ETL pipeline**, and a **dynamic multi-currency Excel unit-economics model**.

> **Note:** The SQL file and ETL pipeline ship with sample seed data so every result below can be reproduced by running the code.

---

## 2. Database Architecture
The relational schema separates volatile currency exchange rates and Amazon fee schedules from supplier costs (`PKR`) to prevent update anomalies:

* `exchange_rates` : Tracks dated `USD/PKR` conversion rates (`rate_date`, `usd_to_pkr`).
* `products` : Stores the SKU catalog (`sku`, `product_name`, `category`) and target retail price (`USD`).
* `amazon_fee_schedules` : Models per-SKU referral fee percentage, FBA fulfillment fee, and monthly storage cost per unit.
* `procurement_batches` : Logs batch quantities, supplier COGS (`PKR`), freight (`PKR`), customs duty (`USD`), and the landed cost reported in the legacy spreadsheet, for automated audit reconciliation.

---

## 3. Key Analytical Findings (Sample Seed Data)
* **Automated Audit Variance Detection:** A SQL reconciliation query flagged `BATCH-2026-01` (100 leather satchels): the legacy sheet reported **$1,565.00** landed cost against a recalculated **$1,994.19**, a **$429.19 understatement**. `BATCH-2026-02` reconciled within tolerance (a $0.19 difference against the $10 threshold).
* **Break-Even Pricing:** The unit-economics query solves for the break-even retail price after marketplace referral fees: **$30.69** for the leather satchel and **$32.89** for the pashmina shawl.
* **SKU Viability Filtering:** A margin-threshold `CASE` rule (30% net margin or more is Approved) classified the pashmina shawl at **42.0%** net margin and the leather satchel at **32.8%**.

---

## 4. Reconciled SKU Performance Summary (Query 2 Output)

| SKU ID | Product | Target Price (USD) | Total Unit Cost (USD) | Break-Even (USD) | Net Profit / Unit | Net Margin | Status |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| `ZPK-LHR-002` | Embroidered Pashmina Shawl | $65.00 | $37.71 | $32.89 | $27.29 | **42.0%** | Approved |
| `ZPK-LHR-001` | Handcrafted Artisanal Leather Satchel | $50.00 | $33.59 | $30.69 | $16.41 | **32.8%** | Approved |

---

## 5. Featured SQL Audit Query (Variance Detection)
```sql
WITH batch_calculations AS (
    SELECT
        pb.batch_id,
        p.sku,
        p.product_name,
        pb.units_ordered,
        pb.reported_landed_cost_usd,
        ROUND(
            ((pb.unit_cogs_pkr + pb.freight_per_unit_pkr) / er.usd_to_pkr) * pb.units_ordered
            + pb.customs_duty_usd,
            2
        ) AS calculated_landed_cost_usd
    FROM procurement_batches pb
    JOIN products p ON pb.sku = p.sku
    JOIN exchange_rates er ON pb.rate_date = er.rate_date
),
variance_audit AS (
    SELECT
        batch_id, sku, product_name, units_ordered,
        reported_landed_cost_usd, calculated_landed_cost_usd,
        ROUND(calculated_landed_cost_usd - reported_landed_cost_usd, 2) AS cost_variance_usd
    FROM batch_calculations
)
SELECT *
FROM variance_audit
WHERE ABS(cost_variance_usd) > 10.00
ORDER BY ABS(cost_variance_usd) DESC;
```

---

## 6. Excel Unit-Economics Model
The Excel workbooks extend the SQL analysis with a reconciled P&L, SKU comparisons, and a price-versus-volume sensitivity matrix.

![Batch Cost and Margin Chart](images/unit_economics_chart.png)
![Pricing Sensitivity Matrix](images/pricing_sensitivity_matrix.png)

---

## 7. Repository Structure
* `README.md` : Executive summary, database architecture, and analytical findings.
* `sql/zindabad_pk_analytics.sql` : Full DDL (`CREATE TABLE`), sample seed data, the variance audit query, and the unit economics, break-even, and margin query.
* `python/etl_pipeline.py` : Automated `pandas` and `sqlite3` ETL pipeline for PKR-to-USD conversion and variance reporting.
* `Zindabad_PK_Amazon_Unit_Economics_Model_v2.xlsx` : 3-tab dynamic Excel workbook with reconciled P&L, SKU comparisons, and a price-versus-volume sensitivity matrix.
* `Zindabad_PK_Live_FX_Google_Sheets_Model.xlsx` : Google Sheets-compatible workbook using `GOOGLEFINANCE("CURRENCY:USDPKR")` for live exchange rates and margin recalculation.
