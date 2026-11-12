-- =============================================================================
-- ZINDABAD PK — CROSS-BORDER SUPPLY CHAIN & UNIT ECONOMICS ANALYTICS
-- Author: Muhammad Adil
-- Description: Normalized relational schema, multi-currency (PKR/USD) landed
--              cost calculations, margin filtering, category break-even
--              aggregations, and automated audit variance detection.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1. NORMALIZED RELATIONAL SCHEMA (DDL)
-- -----------------------------------------------------------------------------

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
    fee_id INT PRIMARY KEY,
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

-- -----------------------------------------------------------------------------
-- 2. SEED DATA (DML)
-- -----------------------------------------------------------------------------

INSERT INTO exchange_rates VALUES ('PKR/USD', 276.6000, '2026-11-01');

INSERT INTO products VALUES
('ZPK-APP-01', 'Base Apparel (50-Unit Batch)', 'Apparel', 0.70, 3000.00, 1500.00, 50.00),
('ZPK-DRS-02', 'Embroidered Dresses (35kg Batch)', 'Apparel', 0.70, 7000.00, 1500.00, 65.00),
('ZPK-MAT-03', 'Artisan Woven Mats', 'Home Goods', 1.50, 53000.00, 0.00, 668.00),
('ZPK-VAL-04', 'Value Tier Apparel ($30 Promo)', 'Apparel', 0.70, 3000.00, 1500.00, 30.00);

INSERT INTO amazon_fee_schedules VALUES
(1, 'ZPK-APP-01', 0.1700, 5.81, 0.0864, 39.99),
(2, 'ZPK-DRS-02', 0.1700, 5.81, 0.0864, 39.99),
(3, 'ZPK-MAT-03', 0.1700, 0.00, 0.0864, 39.99),
(4, 'ZPK-VAL-04', 0.1700, 5.81, 0.0864, 39.99);

INSERT INTO procurement_batches VALUES
('BATCH-001', 'ZPK-APP-01', '2026-10-15', 50.0, 1144.01),
('BATCH-002', 'ZPK-DRS-02', '2026-10-22', 50.0, NULL),
('BATCH-003', 'ZPK-MAT-03', '2026-10-28', 23.6, NULL),
('BATCH-004', 'ZPK-VAL-04', '2026-11-02', 53.0, 1590.00);

-- -----------------------------------------------------------------------------
-- 3. QUERY 1: MULTI-TABLE JOIN & LANDED UNIT ECONOMICS (CTE)
-- -----------------------------------------------------------------------------

WITH unit_economics AS (
    SELECT
        p.sku_id,
        p.product_name,
        b.order_qty,
        p.target_price_usd,
        ROUND(p.unit_cogs_pkr / fx.rate_to_usd, 2) AS unit_cogs_usd,
        ROUND(p.intl_shipping_pkr / fx.rate_to_usd, 2) AS unit_shipping_usd,
        ROUND(p.target_price_usd * f.referral_fee_pct, 2) AS referral_fee_usd,
        f.fba_fulfillment_usd,
        ROUND((f.monthly_pro_sub_usd + (f.monthly_storage_per_unit_usd * b.order_qty)) / b.order_qty, 2) AS overhead_per_unit_usd
    FROM products p
    INNER JOIN amazon_fee_schedules f ON p.sku_id = f.sku_id
    INNER JOIN procurement_batches b ON p.sku_id = b.sku_id
    INNER JOIN exchange_rates fx ON fx.currency_pair = 'PKR/USD'
)
SELECT
    sku_id,
    product_name,
    order_qty,
    target_price_usd,
    ROUND(unit_cogs_usd + unit_shipping_usd + referral_fee_usd + fba_fulfillment_usd + overhead_per_unit_usd, 2) AS total_unit_cost_usd,
    ROUND(target_price_usd - (unit_cogs_usd + unit_shipping_usd + referral_fee_usd + fba_fulfillment_usd + overhead_per_unit_usd), 2) AS net_profit_per_unit_usd,
    ROUND(((target_price_usd - (unit_cogs_usd + unit_shipping_usd + referral_fee_usd + fba_fulfillment_usd + overhead_per_unit_usd)) / target_price_usd) * 100, 1) AS net_margin_pct
FROM unit_economics
ORDER BY net_margin_pct DESC;

-- -----------------------------------------------------------------------------
-- 4. QUERY 2: MARGIN FILTERING & VIABILITY TIERING (>= 30% TARGET)
-- -----------------------------------------------------------------------------

WITH sku_margins AS (
    SELECT
        p.sku_id,
        p.product_name,
        p.target_price_usd,
        ROUND(
            (p.unit_cogs_pkr + p.intl_shipping_pkr) / fx.rate_to_usd
            + f.fba_fulfillment_usd
            + (p.target_price_usd * f.referral_fee_pct)
            + f.monthly_storage_per_unit_usd
            + (f.monthly_pro_sub_usd / b.order_qty), 2
        ) AS landed_unit_cost_usd
    FROM products p
    JOIN amazon_fee_schedules f ON p.sku_id = f.sku_id
    JOIN procurement_batches b ON p.sku_id = b.sku_id
    JOIN exchange_rates fx ON fx.currency_pair = 'PKR/USD'
)
SELECT
    sku_id,
    product_name,
    target_price_usd,
    landed_unit_cost_usd,
    ROUND(((target_price_usd - landed_unit_cost_usd) / target_price_usd) * 100, 1) AS net_margin_pct,
    CASE
        WHEN ((target_price_usd - landed_unit_cost_usd) / target_price_usd) >= 0.30 THEN 'APPROVED (>=30% Margin)'
        WHEN ((target_price_usd - landed_unit_cost_usd) / target_price_usd) > 0 THEN 'WATCHLIST (<30% Margin)'
        ELSE 'REJECTED (Net Loss)'
    END AS viability_tier
FROM sku_margins
WHERE ((target_price_usd - landed_unit_cost_usd) / target_price_usd) >= 0.30
ORDER BY net_margin_pct DESC;

-- -----------------------------------------------------------------------------
-- 5. QUERY 3: CATEGORY BREAK-EVEN & PORTFOLIO AGGREGATION
-- -----------------------------------------------------------------------------

SELECT
    p.category,
    COUNT(DISTINCT p.sku_id) AS sku_count,
    SUM(b.order_qty) AS total_batch_units,
    ROUND(SUM(b.order_qty * p.target_price_usd), 2) AS projected_gross_revenue_usd,
    ROUND(SUM(
        b.order_qty * (
            (p.unit_cogs_pkr + p.intl_shipping_pkr) / fx.rate_to_usd
            + f.fba_fulfillment_usd
            + (p.target_price_usd * f.referral_fee_pct)
            + f.monthly_storage_per_unit_usd
        ) + f.monthly_pro_sub_usd
    ), 2) AS total_reconciled_cost_usd,
    ROUND(SUM(
        (b.order_qty * p.target_price_usd) - (
            b.order_qty * (
                (p.unit_cogs_pkr + p.intl_shipping_pkr) / fx.rate_to_usd
                + f.fba_fulfillment_usd
                + (p.target_price_usd * f.referral_fee_pct)
                + f.monthly_storage_per_unit_usd
            ) + f.monthly_pro_sub_usd
        )
    ), 2) AS total_net_profit_usd,
    ROUND(AVG(
        ((p.unit_cogs_pkr + p.intl_shipping_pkr) / fx.rate_to_usd
        + f.fba_fulfillment_usd
        + f.monthly_storage_per_unit_usd
        + (f.monthly_pro_sub_usd / b.order_qty)) / (1 - f.referral_fee_pct)
    ), 2) AS avg_break_even_price_usd
FROM products p
JOIN amazon_fee_schedules f ON p.sku_id = f.sku_id
JOIN procurement_batches b ON p.sku_id = b.sku_id
JOIN exchange_rates fx ON fx.currency_pair = 'PKR/USD'
GROUP BY p.category
HAVING SUM(b.order_qty) > 0;

-- -----------------------------------------------------------------------------
-- 6. QUERY 4: AUTOMATED AUDIT VARIANCE DETECTION
-- -----------------------------------------------------------------------------

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
  AND ABS(
        (b.order_qty * (
            (p.unit_cogs_pkr + p.intl_shipping_pkr) / fx.rate_to_usd
            + f.fba_fulfillment_usd
            + (p.target_price_usd * f.referral_fee_pct)
            + f.monthly_storage_per_unit_usd
        ) + f.monthly_pro_sub_usd) - b.legacy_recorded_expense_usd
      ) > 10.00;
