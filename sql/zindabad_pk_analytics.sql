-- ============================================================================
-- Zindabad PK — Cross-Border Supply Chain & Unit Economics Schema & Audit
-- Compatible with: PostgreSQL 14+ & SQLite 3.35+ (Strict ANSI-SQL)
-- ============================================================================

DROP TABLE IF EXISTS procurement_batches;
DROP TABLE IF EXISTS amazon_fee_schedules;
DROP TABLE IF EXISTS products;
DROP TABLE IF EXISTS exchange_rates;

-- 1. Exchange Rates Table (USD to PKR)
CREATE TABLE exchange_rates (
    rate_date DATE PRIMARY KEY,
    usd_to_pkr DECIMAL(10, 4) NOT NULL CHECK (usd_to_pkr > 0)
);

-- 2. Product Catalog Table
CREATE TABLE products (
    sku VARCHAR(50) PRIMARY KEY,
    product_name VARCHAR(150) NOT NULL,
    category VARCHAR(100),
    target_retail_price_usd DECIMAL(10, 2) NOT NULL CHECK (target_retail_price_usd > 0)
);

-- 3. Amazon FBA Fee Schedules
CREATE TABLE amazon_fee_schedules (
    sku VARCHAR(50) PRIMARY KEY,
    referral_fee_pct DECIMAL(5, 4) NOT NULL,
    fba_fulfillment_fee_usd DECIMAL(10, 2) NOT NULL,
    monthly_storage_per_unit_usd DECIMAL(10, 2) NOT NULL,
    FOREIGN KEY (sku) REFERENCES products(sku)
);

-- 4. Procurement Batches (Lahore Sourcing -> US FBA)
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

-- ============================================================================
-- Sample Seed Data
-- ============================================================================

INSERT INTO exchange_rates (rate_date, usd_to_pkr) VALUES
('2026-09-15', 278.5000),
('2026-10-01', 279.1000);

INSERT INTO products (sku, product_name, category, target_retail_price_usd) VALUES
('ZPK-LHR-001', 'Handcrafted Artisanal Leather Satchel', 'Accessories', 50.00),
('ZPK-LHR-002', 'Embroidered Pashmina Shawl', 'Apparel', 65.00);

INSERT INTO amazon_fee_schedules (sku, referral_fee_pct, fba_fulfillment_fee_usd, monthly_storage_per_unit_usd) VALUES
('ZPK-LHR-001', 0.1500, 6.15, 0.45),
('ZPK-LHR-002', 0.1500, 5.40, 0.35);

INSERT INTO procurement_batches (
    batch_id, sku, rate_date, units_ordered,
    unit_cogs_pkr, freight_per_unit_pkr, customs_duty_usd, reported_landed_cost_usd
) VALUES
('BATCH-2026-01', 'ZPK-LHR-001', '2026-09-15', 100, 4200.00, 950.00, 145.00, 1565.00),
('BATCH-2026-02', 'ZPK-LHR-002', '2026-10-01', 150, 5100.00, 820.00, 210.00, 3391.85);

-- ============================================================================
-- Query 1: Landed Batch Cost Variance Audit (ANSI-SQL / PostgreSQL Safe)
-- Flags
