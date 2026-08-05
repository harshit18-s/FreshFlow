-- =============================================================================
-- FreshFlow AI — Database Initialization
-- =============================================================================
-- This script runs automatically when the PostgreSQL container starts.
-- It creates schemas, roles, and the complete dimensional model.
-- =============================================================================

-- ─────────────────────────────────────────────────────────────────────────────
-- 1. Schemas
-- ─────────────────────────────────────────────────────────────────────────────
CREATE SCHEMA IF NOT EXISTS bronze;
CREATE SCHEMA IF NOT EXISTS silver;
CREATE SCHEMA IF NOT EXISTS gold;
CREATE SCHEMA IF NOT EXISTS ml;
CREATE SCHEMA IF NOT EXISTS ops;
CREATE SCHEMA IF NOT EXISTS simulation;

-- ─────────────────────────────────────────────────────────────────────────────
-- 2. Database Roles
-- ─────────────────────────────────────────────────────────────────────────────
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'freshflow_etl') THEN
        CREATE ROLE freshflow_etl LOGIN PASSWORD 'etl_dev_2026';
    END IF;
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'freshflow_dbt') THEN
        CREATE ROLE freshflow_dbt LOGIN PASSWORD 'dbt_dev_2026';
    END IF;
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'freshflow_api_read') THEN
        CREATE ROLE freshflow_api_read LOGIN PASSWORD 'api_read_2026';
    END IF;
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'freshflow_powerbi_read') THEN
        CREATE ROLE freshflow_powerbi_read LOGIN PASSWORD 'pbi_read_2026';
    END IF;
END
$$;

-- Grant schema permissions
GRANT ALL ON SCHEMA bronze, silver TO freshflow_etl;
GRANT ALL ON SCHEMA gold, silver TO freshflow_dbt;
GRANT USAGE ON SCHEMA gold TO freshflow_api_read, freshflow_powerbi_read;
GRANT ALL ON SCHEMA ml TO freshflow_etl, freshflow_dbt;
GRANT USAGE ON SCHEMA ml TO freshflow_api_read;
GRANT ALL ON SCHEMA ops TO freshflow_etl;
GRANT USAGE ON SCHEMA ops TO freshflow_api_read;
GRANT ALL ON SCHEMA simulation TO freshflow_etl, freshflow_dbt;

-- ─────────────────────────────────────────────────────────────────────────────
-- 3. DIMENSION TABLES (gold schema)
-- ─────────────────────────────────────────────────────────────────────────────

-- dim_date
CREATE TABLE IF NOT EXISTS gold.dim_date (
    date_key        INTEGER PRIMARY KEY,
    calendar_date   DATE NOT NULL UNIQUE,
    day_number      SMALLINT NOT NULL,
    day_name        VARCHAR(10) NOT NULL,
    week_number     SMALLINT NOT NULL,
    month_number    SMALLINT NOT NULL,
    month_name      VARCHAR(10) NOT NULL,
    quarter         SMALLINT NOT NULL,
    year            SMALLINT NOT NULL,
    is_weekend      BOOLEAN NOT NULL DEFAULT FALSE,
    is_holiday      BOOLEAN NOT NULL DEFAULT FALSE
);

-- dim_time
CREATE TABLE IF NOT EXISTS gold.dim_time (
    time_key            SMALLINT PRIMARY KEY,
    hour_of_day         SMALLINT NOT NULL UNIQUE,
    hour_label          VARCHAR(10) NOT NULL,
    part_of_day         VARCHAR(20) NOT NULL,
    is_operational_hour BOOLEAN NOT NULL DEFAULT TRUE
);

-- dim_city (SCD Type 2)
CREATE TABLE IF NOT EXISTS gold.dim_city (
    city_key        SERIAL PRIMARY KEY,
    city_id         INTEGER NOT NULL,
    city_label      VARCHAR(50) NOT NULL,
    region_label    VARCHAR(50),
    effective_from  DATE NOT NULL DEFAULT CURRENT_DATE,
    effective_to    DATE NOT NULL DEFAULT '9999-12-31',
    is_current      BOOLEAN NOT NULL DEFAULT TRUE
);

-- dim_store (SCD Type 2)
CREATE TABLE IF NOT EXISTS gold.dim_store (
    store_key       SERIAL PRIMARY KEY,
    store_id        INTEGER NOT NULL,
    city_key        INTEGER REFERENCES gold.dim_city(city_key),
    store_label     VARCHAR(50) NOT NULL,
    store_cluster   VARCHAR(20),
    volume_band     VARCHAR(10),
    effective_from  DATE NOT NULL DEFAULT CURRENT_DATE,
    effective_to    DATE NOT NULL DEFAULT '9999-12-31',
    is_current      BOOLEAN NOT NULL DEFAULT TRUE
);

-- dim_product (SCD Type 2)
CREATE TABLE IF NOT EXISTS gold.dim_product (
    product_key             SERIAL PRIMARY KEY,
    product_id              INTEGER NOT NULL,
    management_group_id     INTEGER,
    first_category_id       INTEGER,
    second_category_id      INTEGER,
    third_category_id       INTEGER,
    product_label           VARCHAR(100) NOT NULL,
    abc_class               CHAR(1),
    xyz_class               CHAR(1),
    perishability_class     VARCHAR(20),
    effective_from          DATE NOT NULL DEFAULT CURRENT_DATE,
    effective_to            DATE NOT NULL DEFAULT '9999-12-31',
    is_current              BOOLEAN NOT NULL DEFAULT TRUE
);

-- dim_model
CREATE TABLE IF NOT EXISTS gold.dim_model (
    model_key               SERIAL PRIMARY KEY,
    registered_model_name   VARCHAR(100) NOT NULL,
    model_version           INTEGER NOT NULL,
    model_alias             VARCHAR(20),
    algorithm               VARCHAR(50),
    feature_version         VARCHAR(20),
    training_start          DATE,
    training_end            DATE,
    registered_at           TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(registered_model_name, model_version)
);

-- dim_policy
CREATE TABLE IF NOT EXISTS gold.dim_policy (
    policy_key          SERIAL PRIMARY KEY,
    policy_version      VARCHAR(20) NOT NULL UNIQUE,
    service_level       NUMERIC(4,3) NOT NULL,
    safety_stock_method VARCHAR(50),
    cost_version        VARCHAR(20),
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- dim_weather_band
CREATE TABLE IF NOT EXISTS gold.dim_weather_band (
    weather_band_key    SERIAL PRIMARY KEY,
    temperature_band    VARCHAR(20) NOT NULL,
    humidity_band       VARCHAR(20),
    precipitation_band  VARCHAR(20),
    wind_band           VARCHAR(20),
    UNIQUE(temperature_band, humidity_band, precipitation_band, wind_band)
);

-- dim_reason_code
CREATE TABLE IF NOT EXISTS gold.dim_reason_code (
    reason_key          SERIAL PRIMARY KEY,
    reason_code         VARCHAR(50) NOT NULL UNIQUE,
    reason_group        VARCHAR(50),
    business_description TEXT
);

-- ─────────────────────────────────────────────────────────────────────────────
-- 4. FACT TABLES (gold schema)
-- ─────────────────────────────────────────────────────────────────────────────

-- fact_sales_hourly — grain: one store-product-hour
CREATE TABLE IF NOT EXISTS gold.fact_sales_hourly (
    date_key                INTEGER NOT NULL REFERENCES gold.dim_date(date_key),
    time_key                SMALLINT NOT NULL REFERENCES gold.dim_time(time_key),
    store_key               INTEGER NOT NULL REFERENCES gold.dim_store(store_key),
    product_key             INTEGER NOT NULL REFERENCES gold.dim_product(product_key),
    weather_band_key        INTEGER REFERENCES gold.dim_weather_band(weather_band_key),
    event_timestamp         TIMESTAMP WITH TIME ZONE NOT NULL,
    observed_sales          NUMERIC(12,4) NOT NULL DEFAULT 0,
    stockout_flag           SMALLINT NOT NULL DEFAULT 0,
    discount_factor         NUMERIC(5,3) DEFAULT 1.000,
    activity_flag           SMALLINT DEFAULT 0,
    holiday_flag            SMALLINT DEFAULT 0,
    estimated_hidden_demand NUMERIC(12,4) DEFAULT 0,
    recovered_demand        NUMERIC(12,4) DEFAULT 0,
    estimated_lost_demand   NUMERIC(12,4) DEFAULT 0,
    estimated_lost_revenue  NUMERIC(14,2) DEFAULT 0,
    source_batch_id         VARCHAR(50),
    PRIMARY KEY (store_key, product_key, event_timestamp)
) PARTITION BY RANGE (event_timestamp);

-- Create partitions for expected date range (3 months)
-- Partitions will be created dynamically by the ETL pipeline

-- fact_stockout_incident — grain: one continuous stockout per store-product
CREATE TABLE IF NOT EXISTS gold.fact_stockout_incident (
    incident_id                 SERIAL PRIMARY KEY,
    store_key                   INTEGER NOT NULL REFERENCES gold.dim_store(store_key),
    product_key                 INTEGER NOT NULL REFERENCES gold.dim_product(product_key),
    start_timestamp             TIMESTAMP WITH TIME ZONE NOT NULL,
    end_timestamp               TIMESTAMP WITH TIME ZONE NOT NULL,
    duration_hours              INTEGER NOT NULL,
    operational_duration_hours  INTEGER,
    pre_incident_sales          NUMERIC(12,4),
    post_incident_sales         NUMERIC(12,4),
    estimated_lost_demand       NUMERIC(12,4),
    estimated_lost_revenue      NUMERIC(14,2),
    severity_score              NUMERIC(5,3),
    incident_class              VARCHAR(20)
);

-- fact_forecast — grain: one model-run + store + product + target + horizon
CREATE TABLE IF NOT EXISTS gold.fact_forecast (
    forecast_run_id         VARCHAR(50) NOT NULL,
    model_key               INTEGER REFERENCES gold.dim_model(model_key),
    store_key               INTEGER NOT NULL REFERENCES gold.dim_store(store_key),
    product_key             INTEGER NOT NULL REFERENCES gold.dim_product(product_key),
    generated_date_key      INTEGER REFERENCES gold.dim_date(date_key),
    target_date_key         INTEGER REFERENCES gold.dim_date(date_key),
    target_time_key         SMALLINT REFERENCES gold.dim_time(time_key),
    generated_at            TIMESTAMP WITH TIME ZONE NOT NULL,
    target_timestamp        TIMESTAMP WITH TIME ZONE NOT NULL,
    horizon_hours           SMALLINT NOT NULL,
    forecast_p10            NUMERIC(12,4),
    forecast_p50            NUMERIC(12,4),
    forecast_p90            NUMERIC(12,4),
    actual_recovered_demand NUMERIC(12,4),
    absolute_error          NUMERIC(12,4),
    squared_error           NUMERIC(14,4),
    pinball_loss_p10        NUMERIC(10,6),
    pinball_loss_p50        NUMERIC(10,6),
    pinball_loss_p90        NUMERIC(10,6),
    PRIMARY KEY (forecast_run_id, store_key, product_key, target_timestamp, horizon_hours)
);

-- fact_stockout_risk
CREATE TABLE IF NOT EXISTS gold.fact_stockout_risk (
    risk_run_id         VARCHAR(50) NOT NULL,
    model_key           INTEGER REFERENCES gold.dim_model(model_key),
    store_key           INTEGER NOT NULL REFERENCES gold.dim_store(store_key),
    product_key         INTEGER NOT NULL REFERENCES gold.dim_product(product_key),
    scored_at           TIMESTAMP WITH TIME ZONE NOT NULL,
    horizon_hours       SMALLINT NOT NULL,
    stockout_probability NUMERIC(5,4) NOT NULL,
    risk_band           VARCHAR(10),
    actual_stockout     SMALLINT,
    PRIMARY KEY (risk_run_id, store_key, product_key, horizon_hours)
);

-- fact_recommendation
CREATE TABLE IF NOT EXISTS gold.fact_recommendation (
    recommendation_id       SERIAL PRIMARY KEY,
    policy_key              INTEGER REFERENCES gold.dim_policy(policy_key),
    model_key               INTEGER REFERENCES gold.dim_model(model_key),
    store_key               INTEGER NOT NULL REFERENCES gold.dim_store(store_key),
    product_key             INTEGER NOT NULL REFERENCES gold.dim_product(product_key),
    generated_at            TIMESTAMP WITH TIME ZONE NOT NULL,
    recommended_action      VARCHAR(30) NOT NULL,
    recommended_quantity    NUMERIC(10,2) DEFAULT 0,
    recommended_markdown    NUMERIC(5,3) DEFAULT 0,
    urgency_score           NUMERIC(5,3) NOT NULL,
    stockout_probability    NUMERIC(5,4),
    waste_probability       NUMERIC(5,4),
    expected_lost_sales_cost NUMERIC(14,2),
    expected_waste_cost     NUMERIC(14,2),
    expected_total_cost     NUMERIC(14,2),
    reason_key              INTEGER REFERENCES gold.dim_reason_code(reason_key),
    recommendation_status   VARCHAR(20) DEFAULT 'OPEN'
);

-- fact_policy_simulation
CREATE TABLE IF NOT EXISTS gold.fact_policy_simulation (
    scenario_id                 VARCHAR(50) NOT NULL,
    policy_key                  INTEGER REFERENCES gold.dim_policy(policy_key),
    store_key                   INTEGER NOT NULL REFERENCES gold.dim_store(store_key),
    product_key                 INTEGER NOT NULL REFERENCES gold.dim_product(product_key),
    simulation_date             DATE NOT NULL,
    simulated_demand            NUMERIC(12,4),
    simulated_fulfilled_demand  NUMERIC(12,4),
    simulated_lost_demand       NUMERIC(12,4),
    simulated_expired_quantity  NUMERIC(12,4),
    simulated_revenue           NUMERIC(14,2),
    simulated_gross_margin      NUMERIC(14,2),
    simulated_stockout_cost     NUMERIC(14,2),
    simulated_waste_cost        NUMERIC(14,2),
    simulated_holding_cost      NUMERIC(14,2),
    simulated_total_cost        NUMERIC(14,2),
    PRIMARY KEY (scenario_id, store_key, product_key, simulation_date)
);

-- fact_pipeline_run (ops schema)
CREATE TABLE IF NOT EXISTS ops.fact_pipeline_run (
    pipeline_run_id     VARCHAR(50) PRIMARY KEY,
    pipeline_name       VARCHAR(100) NOT NULL,
    started_at          TIMESTAMP WITH TIME ZONE NOT NULL,
    ended_at            TIMESTAMP WITH TIME ZONE,
    status              VARCHAR(20) NOT NULL DEFAULT 'RUNNING',
    source_rows         BIGINT DEFAULT 0,
    accepted_rows       BIGINT DEFAULT 0,
    rejected_rows       BIGINT DEFAULT 0,
    output_rows         BIGINT DEFAULT 0,
    duration_seconds    NUMERIC(10,2),
    error_type          VARCHAR(100)
);

-- fact_model_monitoring (ml schema)
CREATE TABLE IF NOT EXISTS ml.fact_model_monitoring (
    monitoring_run_id   VARCHAR(50) NOT NULL,
    model_key           INTEGER REFERENCES gold.dim_model(model_key),
    monitoring_date     DATE NOT NULL,
    metric_name         VARCHAR(50) NOT NULL,
    metric_value        NUMERIC(12,6) NOT NULL,
    threshold           NUMERIC(12,6),
    status              VARCHAR(20),
    segment_type        VARCHAR(30),
    segment_value       VARCHAR(50),
    PRIMARY KEY (monitoring_run_id, metric_name, COALESCE(segment_type, ''), COALESCE(segment_value, ''))
);

-- ─────────────────────────────────────────────────────────────────────────────
-- 5. SILVER LAYER TABLES
-- ─────────────────────────────────────────────────────────────────────────────

-- Silver daily (cleaned source records)
CREATE TABLE IF NOT EXISTS silver.daily_sales (
    store_id                INTEGER NOT NULL,
    product_id              INTEGER NOT NULL,
    dt                      DATE NOT NULL,
    city_id                 INTEGER,
    management_group_id     INTEGER,
    first_category_id       INTEGER,
    second_category_id      INTEGER,
    third_category_id       INTEGER,
    sale_amount             NUMERIC(12,4),
    hours_sale              JSONB,
    stock_hour6_22_cnt      SMALLINT,
    hours_stock_status      JSONB,
    discount                NUMERIC(5,3),
    holiday_flag            SMALLINT,
    activity_flag           SMALLINT,
    precpt                  NUMERIC(8,2),
    avg_temperature         NUMERIC(6,2),
    avg_humidity             NUMERIC(6,2),
    avg_wind_level          NUMERIC(6,2),
    source_file             VARCHAR(100),
    source_split            VARCHAR(10),
    ingestion_batch_id      VARCHAR(50),
    ingested_at             TIMESTAMP WITH TIME ZONE,
    schema_version          VARCHAR(10),
    record_hash             VARCHAR(32),
    PRIMARY KEY (store_id, product_id, dt)
);

-- Silver hourly (exploded from daily arrays)
CREATE TABLE IF NOT EXISTS silver.hourly_sales (
    store_id                INTEGER NOT NULL,
    product_id              INTEGER NOT NULL,
    event_timestamp         TIMESTAMP WITH TIME ZONE NOT NULL,
    event_date              DATE NOT NULL,
    hour_of_day             SMALLINT NOT NULL,
    city_id                 INTEGER,
    observed_sales          NUMERIC(12,4) NOT NULL DEFAULT 0,
    stockout_flag           SMALLINT NOT NULL DEFAULT 0,
    is_operational_hour     BOOLEAN NOT NULL,
    day_of_week             SMALLINT,
    is_weekend              BOOLEAN,
    week_of_year            SMALLINT,
    month                   SMALLINT,
    part_of_day             VARCHAR(20),
    discount                NUMERIC(5,3),
    discount_depth          NUMERIC(5,3),
    holiday_flag            SMALLINT,
    activity_flag           SMALLINT,
    precpt                  NUMERIC(8,2),
    avg_temperature         NUMERIC(6,2),
    avg_humidity             NUMERIC(6,2),
    avg_wind_level          NUMERIC(6,2),
    weather_band            VARCHAR(20),
    source_split            VARCHAR(10),
    source_file             VARCHAR(100),
    ingestion_batch_id      VARCHAR(50),
    ingested_at             TIMESTAMP WITH TIME ZONE,
    PRIMARY KEY (store_id, product_id, event_timestamp)
);

-- Quarantine table
CREATE TABLE IF NOT EXISTS silver.quarantine (
    quarantine_id       SERIAL PRIMARY KEY,
    source_record       JSONB NOT NULL,
    error_code          VARCHAR(50) NOT NULL,
    error_message       TEXT,
    batch_id            VARCHAR(50),
    detected_at         TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    resolution_status   VARCHAR(20) DEFAULT 'OPEN'
);

-- ─────────────────────────────────────────────────────────────────────────────
-- 6. SIMULATION TABLES
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS simulation.product_economics (
    product_id                      INTEGER NOT NULL,
    economics_version               VARCHAR(10) NOT NULL,
    effective_from                  DATE NOT NULL,
    effective_to                    DATE NOT NULL DEFAULT '9999-12-31',
    assumed_base_price              NUMERIC(10,2),
    assumed_unit_cost               NUMERIC(10,2),
    assumed_spoilage_cost           NUMERIC(10,2),
    assumed_holding_cost_per_hour   NUMERIC(8,4),
    assumed_shelf_life_hours        INTEGER,
    assumed_supplier_lead_time_hours INTEGER,
    minimum_order_quantity          INTEGER DEFAULT 1,
    case_pack_size                  INTEGER DEFAULT 1,
    target_service_level            NUMERIC(4,3) DEFAULT 0.950,
    criticality_class               VARCHAR(10),
    source_method                   VARCHAR(50) DEFAULT 'category_rule_based',
    assumption_notes                TEXT,
    PRIMARY KEY (product_id, economics_version, effective_from)
);

CREATE TABLE IF NOT EXISTS simulation.inventory_snapshot (
    snapshot_timestamp          TIMESTAMP WITH TIME ZONE NOT NULL,
    store_id                    INTEGER NOT NULL,
    product_id                  INTEGER NOT NULL,
    simulated_on_hand           NUMERIC(10,2) DEFAULT 0,
    simulated_inbound           NUMERIC(10,2) DEFAULT 0,
    simulated_reserved          NUMERIC(10,2) DEFAULT 0,
    simulated_expiring_within_24h NUMERIC(10,2) DEFAULT 0,
    policy_version              VARCHAR(20),
    simulation_seed             INTEGER DEFAULT 42,
    PRIMARY KEY (snapshot_timestamp, store_id, product_id)
);

CREATE TABLE IF NOT EXISTS simulation.supplier_policy (
    supplier_group_id           INTEGER PRIMARY KEY,
    lead_time_hours             INTEGER NOT NULL,
    lead_time_variability       NUMERIC(5,2) DEFAULT 0,
    minimum_order_value         NUMERIC(10,2),
    delivery_days               VARCHAR(50),
    capacity_limit              INTEGER,
    emergency_replenishment_cost NUMERIC(10,2)
);

-- ─────────────────────────────────────────────────────────────────────────────
-- 7. INDEXES
-- ─────────────────────────────────────────────────────────────────────────────

-- Silver indexes
CREATE INDEX IF NOT EXISTS idx_silver_hourly_date
    ON silver.hourly_sales (event_date, store_id, product_id);
CREATE INDEX IF NOT EXISTS idx_silver_hourly_stockout
    ON silver.hourly_sales (stockout_flag)
    WHERE stockout_flag = 1;
CREATE INDEX IF NOT EXISTS idx_silver_daily_store_product
    ON silver.daily_sales (store_id, product_id, dt);

-- Gold fact indexes
CREATE INDEX IF NOT EXISTS idx_incident_store_product
    ON gold.fact_stockout_incident (store_key, product_key, start_timestamp);
CREATE INDEX IF NOT EXISTS idx_incident_severity
    ON gold.fact_stockout_incident (severity_score DESC);

CREATE INDEX IF NOT EXISTS idx_forecast_target_model
    ON gold.fact_forecast (target_timestamp, model_key);
CREATE INDEX IF NOT EXISTS idx_forecast_store_product
    ON gold.fact_forecast (store_key, product_key, target_timestamp);

CREATE INDEX IF NOT EXISTS idx_risk_store_product
    ON gold.fact_stockout_risk (store_key, product_key, scored_at);

CREATE INDEX IF NOT EXISTS idx_recommendation_action_queue
    ON gold.fact_recommendation (generated_at, urgency_score DESC)
    WHERE recommendation_status = 'OPEN';
CREATE INDEX IF NOT EXISTS idx_recommendation_store
    ON gold.fact_recommendation (store_key, product_key, generated_at DESC);

-- Dimension indexes
CREATE INDEX IF NOT EXISTS idx_store_current ON gold.dim_store (store_id) WHERE is_current = TRUE;
CREATE INDEX IF NOT EXISTS idx_product_current ON gold.dim_product (product_id) WHERE is_current = TRUE;
CREATE INDEX IF NOT EXISTS idx_city_current ON gold.dim_city (city_id) WHERE is_current = TRUE;

-- Pipeline run indexes
CREATE INDEX IF NOT EXISTS idx_pipeline_run_status
    ON ops.fact_pipeline_run (pipeline_name, status, started_at DESC);

-- ─────────────────────────────────────────────────────────────────────────────
-- 8. SEED DATA — dim_time (static 24-hour dimension)
-- ─────────────────────────────────────────────────────────────────────────────

INSERT INTO gold.dim_time (time_key, hour_of_day, hour_label, part_of_day, is_operational_hour)
VALUES
    (0,  0,  '00:00', 'Night',     FALSE),
    (1,  1,  '01:00', 'Night',     FALSE),
    (2,  2,  '02:00', 'Night',     FALSE),
    (3,  3,  '03:00', 'Night',     FALSE),
    (4,  4,  '04:00', 'Night',     FALSE),
    (5,  5,  '05:00', 'Night',     FALSE),
    (6,  6,  '06:00', 'Morning',   TRUE),
    (7,  7,  '07:00', 'Morning',   TRUE),
    (8,  8,  '08:00', 'Morning',   TRUE),
    (9,  9,  '09:00', 'Morning',   TRUE),
    (10, 10, '10:00', 'Morning',   TRUE),
    (11, 11, '11:00', 'Morning',   TRUE),
    (12, 12, '12:00', 'Afternoon', TRUE),
    (13, 13, '13:00', 'Afternoon', TRUE),
    (14, 14, '14:00', 'Afternoon', TRUE),
    (15, 15, '15:00', 'Afternoon', TRUE),
    (16, 16, '16:00', 'Afternoon', TRUE),
    (17, 17, '17:00', 'Afternoon', TRUE),
    (18, 18, '18:00', 'Evening',   TRUE),
    (19, 19, '19:00', 'Evening',   TRUE),
    (20, 20, '20:00', 'Evening',   TRUE),
    (21, 21, '21:00', 'Evening',   TRUE),
    (22, 22, '22:00', 'Night',     FALSE),
    (23, 23, '23:00', 'Night',     FALSE)
ON CONFLICT (time_key) DO NOTHING;

-- ─────────────────────────────────────────────────────────────────────────────
-- 9. SEED DATA — dim_reason_code
-- ─────────────────────────────────────────────────────────────────────────────

INSERT INTO gold.dim_reason_code (reason_code, reason_group, business_description) VALUES
    ('HIGH_STOCKOUT_RISK',      'Replenish',  'Stockout probability exceeds threshold; replenishment recommended'),
    ('LEAD_TIME_DEMAND',        'Replenish',  'Forecast lead-time demand exceeds available inventory'),
    ('SAFETY_STOCK_BREACH',     'Replenish',  'Inventory below safety stock level'),
    ('REPEATED_STOCKOUT',       'Replenish',  'Product experienced repeated stockouts within 7 days'),
    ('HIGH_WASTE_RISK',         'Markdown',   'Projected residual exceeds waste threshold before expiry'),
    ('APPROACHING_EXPIRY',      'Markdown',   'Significant inventory approaching shelf-life expiry'),
    ('LOW_DEMAND_FORECAST',     'Markdown',   'Forecasted demand too low to clear existing stock'),
    ('EXCESS_INVENTORY',        'Markdown',   'Inventory exceeds forecast demand by significant margin'),
    ('EMERGENCY_REPLENISH',     'Emergency',  'Critical stockout with high-demand product'),
    ('SEASONAL_ADJUSTMENT',     'Adjust',     'Seasonal pattern requires inventory level adjustment'),
    ('PROMOTION_PREPARATION',   'Adjust',     'Upcoming activity requires increased inventory'),
    ('WEATHER_SENSITIVE',       'Adjust',     'Weather forecast suggests demand change for this category'),
    ('NO_ACTION_NEEDED',        'None',       'Inventory levels adequate for forecasted demand'),
    ('MONITOR_ONLY',            'Monitor',    'Metrics near threshold; monitoring recommended')
ON CONFLICT (reason_code) DO NOTHING;

-- ─────────────────────────────────────────────────────────────────────────────
-- 10. GRANT PERMISSIONS ON ALL TABLES
-- ─────────────────────────────────────────────────────────────────────────────

-- Grant read access on gold schema to read-only roles
DO $$
DECLARE
    r RECORD;
BEGIN
    FOR r IN SELECT tablename FROM pg_tables WHERE schemaname = 'gold'
    LOOP
        EXECUTE 'GRANT SELECT ON gold.' || quote_ident(r.tablename) || ' TO freshflow_api_read, freshflow_powerbi_read';
    END LOOP;
END
$$;

-- Grant full access on silver/gold to ETL and dbt roles
DO $$
DECLARE
    r RECORD;
BEGIN
    FOR r IN SELECT schemaname, tablename FROM pg_tables WHERE schemaname IN ('silver', 'gold', 'ml', 'ops', 'simulation')
    LOOP
        EXECUTE 'GRANT ALL ON ' || quote_ident(r.schemaname) || '.' || quote_ident(r.tablename) || ' TO freshflow_etl';
        IF r.schemaname IN ('gold', 'silver') THEN
            EXECUTE 'GRANT ALL ON ' || quote_ident(r.schemaname) || '.' || quote_ident(r.tablename) || ' TO freshflow_dbt';
        END IF;
    END LOOP;
END
$$;

-- Grant sequence usage
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA gold TO freshflow_etl, freshflow_dbt;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA silver TO freshflow_etl;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA ops TO freshflow_etl;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA ml TO freshflow_etl;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA simulation TO freshflow_etl;

-- ─────────────────────────────────────────────────────────────────────────────
-- 11. VERIFICATION
-- ─────────────────────────────────────────────────────────────────────────────

DO $$
DECLARE
    table_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO table_count
    FROM pg_tables
    WHERE schemaname IN ('gold', 'silver', 'ops', 'ml', 'simulation');

    RAISE NOTICE '✅ FreshFlow AI database initialized: % tables created', table_count;
END
$$;
