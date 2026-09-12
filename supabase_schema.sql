-- =========================================================
-- Retail Intelligence Platform - Supabase Database Schema
-- Run this SQL in your Supabase SQL Editor (Full Clean Migration)
-- =========================================================

-- Enable UUID extension if not enabled
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 1. Stores Table
CREATE TABLE IF NOT EXISTS stores (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    store_code VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    location VARCHAR(255),
    city VARCHAR(100),
    tier VARCHAR(20) DEFAULT 'Tier-2',
    total_counters INTEGER DEFAULT 3,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Insert default demo stores
INSERT INTO stores (store_code, name, location, city, tier, total_counters)
VALUES 
    ('STORE_001', 'SmartRetail Flagship', 'Indiranagar, 100ft Road', 'Bengaluru', 'Tier-1', 4),
    ('STORE_002', 'SmartRetail Express', 'Koramangala 5th Block', 'Bengaluru', 'Tier-1', 2),
    ('STORE_003', 'SmartRetail Hyper', 'Whitefield Main Road', 'Bengaluru', 'Tier-1', 6),
    ('STORE_004', 'SmartRetail Hub', 'HSR Layout Sector 2', 'Bengaluru', 'Tier-2', 3)
ON CONFLICT (store_code) DO UPDATE 
SET name = EXCLUDED.name, location = EXCLUDED.location, updated_at = NOW();

-- 2. Products / SKU Master Catalog Table (All 10 Edge Monitored SKUs)
CREATE TABLE IF NOT EXISTS products (
    id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    category VARCHAR(100) NOT NULL,
    price NUMERIC(10, 2) NOT NULL,
    minimum_stock INTEGER DEFAULT 2,
    target_shelf_zone VARCHAR(100),
    image_url TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Insert Complete 10 Product Catalog
INSERT INTO products (id, name, category, price, minimum_stock, target_shelf_zone)
VALUES 
    ('SKU001', 'Fanta Orange 600ml', 'Beverages', 35.00, 2, 'Beverages & Juices'),
    ('SKU002', 'Pringles Original 107g', 'Chips', 110.00, 2, 'Snacks & Biscuits'),
    ('SKU003', 'Oreo Chocolate 120g', 'Biscuits', 30.00, 2, 'Snacks & Biscuits'),
    ('SKU004', 'Amul Taaza 500ml', 'Milk', 30.00, 3, 'Dairy & Essentials'),
    ('SKU005', 'Real Orange Juice 1L', 'Juices', 40.00, 2, 'Beverages & Juices'),
    ('SKU006', 'Dove Soap Bar 75g', 'Soap', 40.00, 2, 'Dairy & Essentials'),
    ('SKU007', 'Coca Cola 600ml', 'Beverages', 40.00, 2, 'Beverages & Juices'),
    ('SKU008', 'Lays Classic 50g', 'Chips', 20.00, 2, 'Snacks & Biscuits'),
    ('SKU009', 'Cadbury Dairy Milk 50g', 'Chocolates', 50.00, 2, 'Snacks & Biscuits'),
    ('SKU010', 'Colgate Total 120g', 'Personal Care', 55.00, 2, 'Dairy & Essentials')
ON CONFLICT (id) DO UPDATE
SET name = EXCLUDED.name, category = EXCLUDED.category, price = EXCLUDED.price, target_shelf_zone = EXCLUDED.target_shelf_zone;

-- 3. Real-Time Inventory & Shelf Logs Table
CREATE TABLE IF NOT EXISTS inventory_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    store_code VARCHAR(50) REFERENCES stores(store_code) ON DELETE CASCADE,
    product_id VARCHAR(50) REFERENCES products(id) ON DELETE CASCADE,
    product_name VARCHAR(255) NOT NULL,
    detected_count INTEGER NOT NULL DEFAULT 0,
    minimum_stock INTEGER NOT NULL DEFAULT 2,
    status VARCHAR(50) NOT NULL, -- 'IN_STOCK', 'LOW_STOCK', 'OUT_OF_STOCK'
    shelf_zone VARCHAR(100),
    confidence NUMERIC(5, 2) DEFAULT 0.95,
    timestamp TIMESTAMPTZ DEFAULT NOW()
);

-- 4. Shopper Traffic & Footfall Analytics Table
CREATE TABLE IF NOT EXISTS shopper_traffic (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    store_code VARCHAR(50) REFERENCES stores(store_code) ON DELETE CASCADE,
    current_occupancy INTEGER NOT NULL DEFAULT 0,
    total_in INTEGER NOT NULL DEFAULT 0,
    total_out INTEGER NOT NULL DEFAULT 0,
    unique_visitors INTEGER NOT NULL DEFAULT 0,
    avg_dwell_time_seconds NUMERIC(10, 2) DEFAULT 0.00,
    zone_dwell_summary JSONB DEFAULT '{}'::jsonb,
    timestamp TIMESTAMPTZ DEFAULT NOW()
);

-- 5. Queue Intelligence & Checkout Analytics Table
CREATE TABLE IF NOT EXISTS queue_metrics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    store_code VARCHAR(50) REFERENCES stores(store_code) ON DELETE CASCADE,
    active_counters INTEGER DEFAULT 1,
    queue_length INTEGER NOT NULL DEFAULT 0,
    avg_wait_time_seconds NUMERIC(10, 2) DEFAULT 0.00,
    is_congested BOOLEAN DEFAULT FALSE,
    recommendation TEXT,
    timestamp TIMESTAMPTZ DEFAULT NOW()
);

-- 6. Real-Time Operational Alerts Table
CREATE TABLE IF NOT EXISTS alerts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    store_code VARCHAR(50) REFERENCES stores(store_code) ON DELETE CASCADE,
    alert_type VARCHAR(100) NOT NULL, -- 'OUT_OF_STOCK', 'LOW_STOCK', 'QUEUE_CONGESTION', 'PLANOGRAM_MISMATCH'
    severity VARCHAR(20) NOT NULL, -- 'critical', 'warning', 'info'
    title VARCHAR(255) NOT NULL,
    message TEXT NOT NULL,
    zone VARCHAR(100),
    is_acknowledged BOOLEAN DEFAULT FALSE,
    acknowledged_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 7. Planogram Compliance & Shelf Audit Table
CREATE TABLE IF NOT EXISTS shelf_compliance (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    store_code VARCHAR(50) REFERENCES stores(store_code) ON DELETE CASCADE,
    zone_name VARCHAR(100) NOT NULL,
    expected_sku VARCHAR(50) REFERENCES products(id),
    detected_items INTEGER DEFAULT 0,
    compliance_score NUMERIC(5, 2) DEFAULT 100.00,
    status VARCHAR(50) DEFAULT 'COMPLIANT', -- 'COMPLIANT', 'EMPTY_SLOT', 'MISPLACED_SKU'
    timestamp TIMESTAMPTZ DEFAULT NOW()
);

-- 8. Inventory Ledger Table (Audit Trail of All Stock Adjustments, Restocks & Sales)
CREATE TABLE IF NOT EXISTS inventory_ledger (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    store_code VARCHAR(50) REFERENCES stores(store_code) ON DELETE CASCADE,
    sku_id VARCHAR(50) REFERENCES products(id) ON DELETE CASCADE,
    change_qty INTEGER NOT NULL,
    reason VARCHAR(100) NOT NULL, -- 'sale', 'restock', 'audit_correction', 'shrinkage'
    reference_id VARCHAR(100),
    note TEXT,
    actor VARCHAR(100) DEFAULT 'system',
    timestamp TIMESTAMPTZ DEFAULT NOW()
);

-- 9. POS Sales Transactions Table
CREATE TABLE IF NOT EXISTS sales_transactions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    store_code VARCHAR(50) REFERENCES stores(store_code) ON DELETE CASCADE,
    transaction_id VARCHAR(100) UNIQUE NOT NULL,
    total_amount NUMERIC(10, 2) NOT NULL,
    payment_method VARCHAR(50) DEFAULT 'UPI',
    cashier VARCHAR(100) DEFAULT 'Self Checkout 01',
    timestamp TIMESTAMPTZ DEFAULT NOW()
);

-- 10. POS Sale Line Items Table
CREATE TABLE IF NOT EXISTS sale_items (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    transaction_id VARCHAR(100) REFERENCES sales_transactions(transaction_id) ON DELETE CASCADE,
    sku_id VARCHAR(50) REFERENCES products(id) ON DELETE CASCADE,
    quantity INTEGER NOT NULL DEFAULT 1,
    unit_price NUMERIC(10, 2) NOT NULL,
    line_total NUMERIC(10, 2) NOT NULL
);

-- Performance Indexes
CREATE INDEX IF NOT EXISTS idx_inventory_timestamp ON inventory_logs(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_traffic_timestamp ON shopper_traffic(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_queue_timestamp ON queue_metrics(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_alerts_status ON alerts(is_acknowledged, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_shelf_timestamp ON shelf_compliance(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_ledger_timestamp ON inventory_ledger(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_sales_timestamp ON sales_transactions(timestamp DESC);

-- Enable Row Level Security (RLS)
ALTER TABLE stores ENABLE ROW LEVEL SECURITY;
ALTER TABLE products ENABLE ROW LEVEL SECURITY;
ALTER TABLE inventory_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE shopper_traffic ENABLE ROW LEVEL SECURITY;
ALTER TABLE queue_metrics ENABLE ROW LEVEL SECURITY;
ALTER TABLE alerts ENABLE ROW LEVEL SECURITY;
ALTER TABLE shelf_compliance ENABLE ROW LEVEL SECURITY;
ALTER TABLE inventory_ledger ENABLE ROW LEVEL SECURITY;
ALTER TABLE sales_transactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE sale_items ENABLE ROW LEVEL SECURITY;

-- Allow public read-write for anon and service keys (Drops previous policies if needed)
DROP POLICY IF EXISTS "Allow public read-write for stores" ON stores;
CREATE POLICY "Allow public read-write for stores" ON stores FOR ALL USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS "Allow public read-write for products" ON products;
CREATE POLICY "Allow public read-write for products" ON products FOR ALL USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS "Allow public read-write for inventory_logs" ON inventory_logs;
CREATE POLICY "Allow public read-write for inventory_logs" ON inventory_logs FOR ALL USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS "Allow public read-write for shopper_traffic" ON shopper_traffic;
CREATE POLICY "Allow public read-write for shopper_traffic" ON shopper_traffic FOR ALL USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS "Allow public read-write for queue_metrics" ON queue_metrics;
CREATE POLICY "Allow public read-write for queue_metrics" ON queue_metrics FOR ALL USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS "Allow public read-write for alerts" ON alerts;
CREATE POLICY "Allow public read-write for alerts" ON alerts FOR ALL USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS "Allow public read-write for shelf_compliance" ON shelf_compliance;
CREATE POLICY "Allow public read-write for shelf_compliance" ON shelf_compliance FOR ALL USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS "Allow public read-write for inventory_ledger" ON inventory_ledger;
CREATE POLICY "Allow public read-write for inventory_ledger" ON inventory_ledger FOR ALL USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS "Allow public read-write for sales_transactions" ON sales_transactions;
CREATE POLICY "Allow public read-write for sales_transactions" ON sales_transactions FOR ALL USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS "Allow public read-write for sale_items" ON sale_items;
CREATE POLICY "Allow public read-write for sale_items" ON sale_items FOR ALL USING (true) WITH CHECK (true);

-- 11. Theft & Suspicious Product Removal Events Table
CREATE TABLE IF NOT EXISTS theft_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    event_id VARCHAR(100) UNIQUE,
    camera_id VARCHAR(50) NOT NULL,
    person_id INTEGER,
    product_id VARCHAR(50),
    product_name VARCHAR(255),
    shelf_id VARCHAR(50),
    risk_score INTEGER NOT NULL,
    risk_level VARCHAR(20) NOT NULL, -- 'NORMAL', 'LOW', 'SUSPICIOUS', 'HIGH'
    event_type VARCHAR(100) NOT NULL, -- 'POTENTIAL_PRODUCT_REMOVAL'
    current_zone VARCHAR(100),
    checkout_detected BOOLEAN DEFAULT FALSE,
    snapshot_url TEXT,
    status VARCHAR(50) DEFAULT 'ACTIVE', -- 'ACTIVE', 'UNDER_REVIEW', 'RESOLVED', 'FALSE_POSITIVE'
    timeline JSONB DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    resolved_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_theft_events_status ON theft_events(status, risk_score DESC);
CREATE INDEX IF NOT EXISTS idx_theft_events_timestamp ON theft_events(created_at DESC);

ALTER TABLE theft_events ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Allow public read-write for theft_events" ON theft_events;
CREATE POLICY "Allow public read-write for theft_events" ON theft_events FOR ALL USING (true) WITH CHECK (true);

