# FreshFlow AI — Data Dictionary

> **Version:** 0.1.0 · **Status:** Living Document · **Last Updated:** 2026-07-16

---

## Overview

This document defines every column across all data layers in the FreshFlow AI platform: source (raw CSV), Bronze, Silver (daily + hourly), and Gold (dimensions + facts).

> [!NOTE]
> The source dataset is **FreshRetailNet-50K** — a synthetic retail dataset. All column descriptions below reflect the dataset's actual semantics, including important cautions about normalization and simulated fields.

---

## 1 · Source Columns (Raw CSV)

These are the columns present in the original FreshRetailNet-50K CSV files before any transformation.

| # | Column | Type | Description | Semantic Caution |
|---|--------|------|-------------|------------------|
| 1 | `city_id` | `int` | Numeric identifier for the city (1–18) | Anonymized — no real city names |
| 2 | `store_id` | `int` | Numeric identifier for the store (1–898) | Anonymized — no real store names |
| 3 | `product_id` | `int` | Numeric identifier for the product/SKU (1–865) | Anonymized — no real product names or categories |
| 4 | `dt` | `string` | Date of the observation in `YYYY-MM-DD` format | 90-day span; exact date range varies |
| 5 | `sale_amount` | `float` | Total daily sales quantity for this store × product × day | ⚠️ **Normalized** — not real retail units. Relative values only. |
| 6 | `sale_amount_by_hours` | `string` | JSON-encoded array of 24 floats — hourly sales breakdown | Each element corresponds to hour 0–23. Sum ≈ `sale_amount`. |
| 7 | `discount_by_hours` | `string` | JSON-encoded array of 24 floats — hourly discount factors | ⚠️ `1.0` = **no discount**; `0.9` = 10% off; `0.0` = 100% off (free). Inverse of typical "discount %" semantics. |
| 8 | `is_stockout_by_hours` | `string` | JSON-encoded array of 24 integers (0 or 1) — hourly stockout flags | `1` = stocked out in that hour; `0` = in stock. |
| 9 | `avg_receipt_amount` | `float` | Average transaction amount at this store on this day | Normalized. Serves as a proxy for store traffic / basket size. |
| 10 | `avg_discount_amount` | `float` | Average discount amount across all transactions at this store on this day | Normalized. |
| 11 | `weather_main` | `string` | Primary weather condition label (e.g., "Clear", "Rain", "Snow", "Clouds") | Daily-level only — same value for all 24 hours. |
| 12 | `avg_temperature` | `float` | Average daily temperature (°C) | Daily-level. |
| 13 | `avg_humidity` | `float` | Average daily humidity (%) | Daily-level. |
| 14 | `avg_wind_level` | `float` | Average daily wind level (normalized) | Daily-level. |

> [!WARNING]
> **`sale_amount` is normalized, not real units.** A value of `3.7` does not mean 3.7 items were sold — it is a relative, normalized quantity. All downstream KPIs that use sale_amount inherit this normalization. Never interpret these as real retail units or currency.

---

## 2 · Bronze Layer — Metadata Columns

The Bronze layer preserves all source columns **exactly as received** and adds the following metadata columns for lineage tracking:

| Column | Type | Description |
|--------|------|-------------|
| `_ingested_at` | `timestamp` | UTC timestamp when the row was written to Bronze |
| `_source_file` | `string` | Original filename or path of the ingested CSV |
| `_batch_id` | `string` | Unique identifier for the ingestion batch (UUID) |

> [!NOTE]
> Bronze is **immutable and append-only**. Data is never modified or deleted in this layer. Re-ingestion creates new rows with different `_batch_id` values.

---

## 3 · Silver Layer — Daily Grain

The Silver daily table (`silver_daily`) has one row per **store × product × day**, after cleaning, validation, and type casting.

| # | Column | Type | Description | Derivation |
|---|--------|------|-------------|------------|
| 1 | `store_id` | `int` | Store identifier | Source: `store_id` |
| 2 | `product_id` | `int` | Product identifier | Source: `product_id` |
| 3 | `city_id` | `int` | City identifier | Source: `city_id` |
| 4 | `dt` | `date` | Observation date | Source: `dt`, cast to date type |
| 5 | `sale_amount` | `float` | Daily total sales (normalized) | Source: `sale_amount` |
| 6 | `sale_amount_by_hours` | `array<float>` | 24-element hourly sales array | Source: `sale_amount_by_hours`, parsed from JSON |
| 7 | `discount_by_hours` | `array<float>` | 24-element hourly discount array | Source: `discount_by_hours`, parsed from JSON |
| 8 | `is_stockout_by_hours` | `array<int>` | 24-element hourly stockout flag array | Source: `is_stockout_by_hours`, parsed from JSON |
| 9 | `avg_receipt_amount` | `float` | Store-level average receipt | Source: `avg_receipt_amount` |
| 10 | `avg_discount_amount` | `float` | Store-level average discount | Source: `avg_discount_amount` |
| 11 | `weather_main` | `string` | Weather condition | Source: `weather_main`, trimmed and standardized |
| 12 | `avg_temperature` | `float` | Daily average temperature (°C) | Source: `avg_temperature` |
| 13 | `avg_humidity` | `float` | Daily average humidity (%) | Source: `avg_humidity` |
| 14 | `avg_wind_level` | `float` | Daily average wind level | Source: `avg_wind_level` |
| 15 | `daily_stockout_hours` | `int` | Count of operational hours with stockout | Derived: `SUM(is_stockout_by_hours[6:22])` |
| 16 | `has_any_stockout` | `boolean` | Whether any operational hour had a stockout | Derived: `daily_stockout_hours > 0` |
| 17 | `day_of_week` | `int` | Day of week (0=Monday, 6=Sunday) | Derived from `dt` |
| 18 | `is_weekend` | `boolean` | Saturday or Sunday | Derived: `day_of_week >= 5` |
| 19 | `_ingested_at` | `timestamp` | Inherited from Bronze | Passthrough |
| 20 | `_batch_id` | `string` | Inherited from Bronze | Passthrough |

---

## 4 · Silver Layer — Hourly Grain

The Silver hourly table (`silver_hourly`) has one row per **store × product × hour**, created by exploding the 24-element arrays. Only **operational hours (06:00–22:00)** are retained, yielding 16 rows per source row.

| # | Column | Type | Description | Derivation |
|---|--------|------|-------------|------------|
| 1 | `store_id` | `int` | Store identifier | From daily row |
| 2 | `product_id` | `int` | Product identifier | From daily row |
| 3 | `city_id` | `int` | City identifier | From daily row |
| 4 | `dt` | `date` | Observation date | From daily row |
| 5 | `hour` | `int` | Hour of day (6–21) | Array index during explosion |
| 6 | `event_timestamp` | `timestamp` | Full datetime (`dt` + `hour`) | Derived: `dt` combined with `hour` |
| 7 | `sale_amount` | `float` | Sales in this hour (normalized) | `sale_amount_by_hours[hour]` |
| 8 | `discount_factor` | `float` | Discount factor for this hour | `discount_by_hours[hour]` (1.0 = no discount) |
| 9 | `is_stockout` | `boolean` | Whether product was stocked out this hour | `is_stockout_by_hours[hour] == 1` |
| 10 | `avg_receipt_amount` | `float` | Store-level average receipt (repeated) | From daily row |
| 11 | `avg_discount_amount` | `float` | Store-level average discount (repeated) | From daily row |
| 12 | `weather_main` | `string` | Weather condition (repeated) | From daily row |
| 13 | `avg_temperature` | `float` | Temperature (repeated) | From daily row |
| 14 | `avg_humidity` | `float` | Humidity (repeated) | From daily row |
| 15 | `avg_wind_level` | `float` | Wind level (repeated) | From daily row |
| 16 | `day_of_week` | `int` | Day of week | From daily row |
| 17 | `is_weekend` | `boolean` | Weekend flag | From daily row |
| 18 | `hour_sin` | `float` | Sine encoding of hour | `sin(2π × hour / 24)` |
| 19 | `hour_cos` | `float` | Cosine encoding of hour | `cos(2π × hour / 24)` |
| 20 | `_batch_id` | `string` | Inherited from Bronze | Passthrough |

> [!IMPORTANT]
> Weather fields (`weather_main`, `avg_temperature`, `avg_humidity`, `avg_wind_level`) are **daily-level** data repeated identically across all 16 hourly rows for a given day. They do not represent actual hourly weather variation.

---

## 5 · Gold Layer — Dimension Tables

### 5.1 `dim_date`

| Column | Type | Description |
|--------|------|-------------|
| `date_key` | `int` | Surrogate key (`YYYYMMDD` format) |
| `dt` | `date` | Calendar date |
| `year` | `int` | Year |
| `month` | `int` | Month (1–12) |
| `day` | `int` | Day of month (1–31) |
| `day_of_week` | `int` | Day of week (0=Mon, 6=Sun) |
| `day_name` | `string` | Day name ("Monday", etc.) |
| `is_weekend` | `boolean` | Saturday or Sunday |
| `week_of_year` | `int` | ISO week number |
| `quarter` | `int` | Quarter (1–4) |
| `is_train` | `boolean` | Whether date falls in training split |
| `is_test` | `boolean` | Whether date falls in test split |
| `split_label` | `string` | "train", "validation", or "test" |

### 5.2 `dim_time`

| Column | Type | Description |
|--------|------|-------------|
| `time_key` | `int` | Surrogate key (hour: 6–21) |
| `hour` | `int` | Hour of day (6–21) |
| `hour_label` | `string` | Display label ("06:00", "07:00", etc.) |
| `period` | `string` | "morning" (6–11), "afternoon" (12–17), "evening" (18–21) |
| `is_peak` | `boolean` | Whether hour falls in typical peak traffic window |
| `hour_sin` | `float` | Sine encoding |
| `hour_cos` | `float` | Cosine encoding |

### 5.3 `dim_city`

| Column | Type | Description |
|--------|------|-------------|
| `city_key` | `int` | Surrogate key |
| `city_id` | `int` | Source city identifier (1–18) |
| `city_label` | `string` | Display label ("City 01", etc.) |
| `store_count` | `int` | Number of stores in this city |

### 5.4 `dim_store`

| Column | Type | Description |
|--------|------|-------------|
| `store_key` | `int` | Surrogate key |
| `store_id` | `int` | Source store identifier (1–898) |
| `city_id` | `int` | Foreign key to `dim_city` |
| `store_label` | `string` | Display label ("Store 0001", etc.) |

### 5.5 `dim_product`

| Column | Type | Description |
|--------|------|-------------|
| `product_key` | `int` | Surrogate key |
| `product_id` | `int` | Source product identifier (1–865) |
| `product_label` | `string` | Display label ("Product 0001", etc.) |
| `simulated_category` | `string` | ⚠️ SIMULATED — Category assignment ("highly_perishable", "moderately_perishable", "longer_life") |
| `simulated_unit_price` | `float` | ⚠️ SIMULATED — Generated unit retail price |
| `simulated_unit_cost` | `float` | ⚠️ SIMULATED — Generated unit cost |
| `simulated_shelf_life_hours` | `int` | ⚠️ SIMULATED — Product shelf life in hours |
| `simulated_margin` | `float` | ⚠️ SIMULATED — `unit_price − unit_cost` |

### 5.6 `dim_model`

| Column | Type | Description |
|--------|------|-------------|
| `model_key` | `int` | Surrogate key |
| `model_name` | `string` | Registered model name (e.g., "demand_forecaster_v1") |
| `model_type` | `string` | "demand_recovery", "demand_forecast", "stockout_classifier", "recommendation_engine" |
| `framework` | `string` | ML framework ("lightgbm", "xgboost", "pytorch", etc.) |
| `mlflow_run_id` | `string` | MLflow experiment run ID |
| `registered_at` | `timestamp` | When the model was registered |

### 5.7 `dim_policy`

| Column | Type | Description |
|--------|------|-------------|
| `policy_key` | `int` | Surrogate key |
| `policy_name` | `string` | Human-readable name (e.g., "conservative_95", "aggressive_99") |
| `target_service_level` | `float` | Target service level (e.g., 0.95, 0.98) |
| `quantile_used` | `float` | Forecast quantile used for ordering (e.g., 0.90, 0.95) |
| `safety_stock_method` | `string` | Method for safety stock calculation |

### 5.8 `dim_weather_band`

| Column | Type | Description |
|--------|------|-------------|
| `weather_band_key` | `int` | Surrogate key |
| `weather_main` | `string` | Weather condition label |
| `temperature_band` | `string` | Temperature bucket ("cold", "mild", "warm", "hot") |
| `humidity_band` | `string` | Humidity bucket ("dry", "moderate", "humid") |

### 5.9 `dim_reason_code`

| Column | Type | Description |
|--------|------|-------------|
| `reason_key` | `int` | Surrogate key |
| `reason_code` | `string` | Machine-readable code ("stockout_high_risk", "approaching_expiry", "excess_inventory") |
| `reason_label` | `string` | Human-readable label |
| `action_type` | `string` | "replenish", "markdown", "monitor", "escalate" |

---

## 6 · Gold Layer — Fact Tables

### 6.1 `fact_sales_hourly`

The central fact table — one row per **store × product × hour**.

| Column | Type | Description |
|--------|------|-------------|
| `sales_hourly_key` | `bigint` | Surrogate key |
| `date_key` | `int` | FK → `dim_date` |
| `time_key` | `int` | FK → `dim_time` |
| `store_key` | `int` | FK → `dim_store` |
| `product_key` | `int` | FK → `dim_product` |
| `weather_band_key` | `int` | FK → `dim_weather_band` |
| `sale_amount` | `float` | Observed sales (normalized) |
| `discount_factor` | `float` | Discount factor (1.0 = no discount) |
| `is_stockout` | `boolean` | Stockout flag |
| `recovered_sale_amount` | `float` | Model-estimated sales (filled during stockout hours) |
| `estimated_lost_demand` | `float` | `recovered_sale_amount − sale_amount` (zero if not stocked out) |
| `avg_receipt_amount` | `float` | Store-level receipt average |

### 6.2 `fact_stockout_incident`

One row per **contiguous stockout incident** (a block of consecutive stockout hours).

| Column | Type | Description |
|--------|------|-------------|
| `incident_key` | `bigint` | Surrogate key |
| `date_key` | `int` | FK → `dim_date` |
| `store_key` | `int` | FK → `dim_store` |
| `product_key` | `int` | FK → `dim_product` |
| `incident_start_hour` | `int` | Hour when stockout began |
| `incident_end_hour` | `int` | Hour when stockout ended (inclusive) |
| `duration_hours` | `int` | Length of incident in hours |
| `total_lost_demand` | `float` | Sum of estimated lost demand across incident hours |
| `simulated_lost_sales_cost` | `float` | ⚠️ SIMULATED — Estimated revenue impact |

### 6.3 `fact_forecast`

One row per **store × product × hour × forecast horizon**.

| Column | Type | Description |
|--------|------|-------------|
| `forecast_key` | `bigint` | Surrogate key |
| `date_key` | `int` | FK → `dim_date` |
| `time_key` | `int` | FK → `dim_time` |
| `store_key` | `int` | FK → `dim_store` |
| `product_key` | `int` | FK → `dim_product` |
| `model_key` | `int` | FK → `dim_model` |
| `horizon_hours` | `int` | Forecast horizon (1, 4, 8, 12, 24, etc.) |
| `forecast_median` | `float` | Point forecast (50th percentile) |
| `forecast_q10` | `float` | 10th percentile |
| `forecast_q25` | `float` | 25th percentile |
| `forecast_q75` | `float` | 75th percentile |
| `forecast_q90` | `float` | 90th percentile |
| `actual` | `float` | Actual observed/recovered demand (for evaluation) |
| `absolute_error` | `float` | `|actual − forecast_median|` |

### 6.4 `fact_stockout_risk`

One row per **store × product × hour** — stockout probability predictions.

| Column | Type | Description |
|--------|------|-------------|
| `risk_key` | `bigint` | Surrogate key |
| `date_key` | `int` | FK → `dim_date` |
| `time_key` | `int` | FK → `dim_time` |
| `store_key` | `int` | FK → `dim_store` |
| `product_key` | `int` | FK → `dim_product` |
| `model_key` | `int` | FK → `dim_model` |
| `stockout_probability` | `float` | Predicted probability of stockout (0.0–1.0) |
| `risk_tier` | `string` | "low", "medium", "high", "critical" |
| `is_alert` | `boolean` | Whether probability exceeds alert threshold |
| `actual_stockout` | `boolean` | Ground truth (for evaluation) |

### 6.5 `fact_recommendation`

One row per **recommended action** for an at-risk product.

| Column | Type | Description |
|--------|------|-------------|
| `recommendation_key` | `bigint` | Surrogate key |
| `date_key` | `int` | FK → `dim_date` |
| `store_key` | `int` | FK → `dim_store` |
| `product_key` | `int` | FK → `dim_product` |
| `reason_key` | `int` | FK → `dim_reason_code` |
| `policy_key` | `int` | FK → `dim_policy` |
| `action_type` | `string` | "replenish", "markdown", "monitor", "escalate" |
| `urgency` | `string` | "routine", "elevated", "urgent" |
| `suggested_order_qty` | `float` | Recommended order quantity (for replenish actions) |
| `suggested_markdown_pct` | `float` | Recommended markdown percentage (for markdown actions) |
| `confidence_score` | `float` | Model confidence in this recommendation |
| `estimated_impact` | `float` | ⚠️ SIMULATED — Estimated cost avoidance if recommendation is followed |

### 6.6 `fact_policy_simulation`

One row per **store × product × day × policy** — what-if analysis results.

| Column | Type | Description |
|--------|------|-------------|
| `simulation_key` | `bigint` | Surrogate key |
| `date_key` | `int` | FK → `dim_date` |
| `store_key` | `int` | FK → `dim_store` |
| `product_key` | `int` | FK → `dim_product` |
| `policy_key` | `int` | FK → `dim_policy` |
| `simulated_order_qty` | `float` | Order quantity under this policy |
| `simulated_stockout_hours` | `int` | Estimated stockout hours under this policy |
| `simulated_expired_qty` | `float` | ⚠️ SIMULATED — Estimated units expired |
| `simulated_lost_sales_cost` | `float` | ⚠️ SIMULATED |
| `simulated_waste_cost` | `float` | ⚠️ SIMULATED |
| `simulated_holding_cost` | `float` | ⚠️ SIMULATED |
| `simulated_emergency_cost` | `float` | ⚠️ SIMULATED |
| `simulated_total_cost` | `float` | ⚠️ SIMULATED — Sum of all cost components |

### 6.7 `fact_pipeline_run`

One row per **pipeline execution step**.

| Column | Type | Description |
|--------|------|-------------|
| `run_key` | `bigint` | Surrogate key |
| `dag_id` | `string` | Airflow DAG identifier |
| `task_id` | `string` | Airflow task identifier |
| `run_id` | `string` | Unique run identifier |
| `started_at` | `timestamp` | Execution start time |
| `completed_at` | `timestamp` | Execution end time |
| `status` | `string` | "success", "failed", "running" |
| `rows_processed` | `bigint` | Number of rows processed |
| `rows_rejected` | `bigint` | Number of rows that failed validation |
| `rejection_rate` | `float` | `rows_rejected / rows_processed` |
| `error_message` | `string` | Error details (if failed) |

### 6.8 `fact_model_monitoring`

One row per **model × evaluation date** — tracks model health over time.

| Column | Type | Description |
|--------|------|-------------|
| `monitoring_key` | `bigint` | Surrogate key |
| `date_key` | `int` | FK → `dim_date` |
| `model_key` | `int` | FK → `dim_model` |
| `metric_name` | `string` | Metric being tracked ("wape", "bias", "pr_auc", etc.) |
| `metric_value` | `float` | Current metric value |
| `baseline_value` | `float` | Training-time baseline |
| `threshold` | `float` | Acceptable threshold |
| `is_breached` | `boolean` | Whether metric exceeds threshold |
| `drift_status` | `string` | "stable", "warning", "drifted" |

---

## Column Count Summary

| Layer | Table | Approximate Column Count |
|-------|-------|--------------------------|
| Source | CSV | 14 |
| Bronze | Bronze + metadata | 17 |
| Silver | `silver_daily` | 20 |
| Silver | `silver_hourly` | 20 |
| Gold | 9 dimension tables | ~60 total |
| Gold | 8 fact tables | ~100 total |

---

*For KPI formulas built on these tables, see [kpi_dictionary.md](kpi_dictionary.md). For assumptions about simulated columns, see [assumptions.md](assumptions.md).*
