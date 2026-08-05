# FreshFlow AI — KPI Dictionary

> **Version:** 0.1.0 · **Status:** Living Document · **Last Updated:** 2026-07-16

---

## Overview

This document defines every Key Performance Indicator (KPI) used in FreshFlow AI. Each KPI has a single, authoritative definition. All dashboards, reports, and alerts **must** reference this dictionary — no ad-hoc metric definitions are permitted.

> [!IMPORTANT]
> KPIs marked with ⚠️ **SIMULATED** use commercially simulated fields (prices, costs, shelf-life). These are scenario-based estimates, not real financial figures. See [assumptions.md](assumptions.md) for simulation rules.

---

## KPI Index

| # | KPI Name | Category | Simulated? |
|---|----------|----------|------------|
| 1 | [Availability %](#1--availability-) | Availability | No |
| 2 | [Stockout Operational Hours](#2--stockout-operational-hours) | Availability | No |
| 3 | [Stockout Incident Count](#3--stockout-incident-count) | Availability | No |
| 4 | [Average Incident Duration](#4--average-incident-duration) | Availability | No |
| 5 | [Observed Demand](#5--observed-demand) | Demand | No |
| 6 | [Recovered Demand](#6--recovered-demand) | Demand | No |
| 7 | [Estimated Lost Demand](#7--estimated-lost-demand) | Demand | No |
| 8 | [Scenario Lost-Sales Cost](#8--scenario-lost-sales-cost) | Financial Impact | ⚠️ Yes |
| 9 | [Scenario Waste Cost](#9--scenario-waste-cost) | Financial Impact | ⚠️ Yes |
| 10 | [Service Level](#10--service-level) | Supply Chain | No |
| 11 | [Fill Rate](#11--fill-rate) | Supply Chain | No |
| 12 | [Forecast WAPE](#12--forecast-wape) | Model Quality | No |
| 13 | [Forecast Bias](#13--forecast-bias) | Model Quality | No |
| 14 | [P90 Coverage](#14--p90-coverage) | Model Quality | No |
| 15 | [Forecast Value Added (FVA)](#15--forecast-value-added-fva) | Model Quality | No |
| 16 | [Stockout PR-AUC](#16--stockout-pr-auc) | Model Quality | No |
| 17 | [Alert Precision](#17--alert-precision) | Model Quality | No |
| 18 | [Recommendation Coverage](#18--recommendation-coverage) | Recommendations | No |
| 19 | [Urgent Recommendation Count](#19--urgent-recommendation-count) | Recommendations | No |
| 20 | [Simulated Expired Quantity](#20--simulated-expired-quantity) | Waste | ⚠️ Yes |
| 21 | [Simulated Total Cost](#21--simulated-total-cost) | Financial Impact | ⚠️ Yes |
| 22 | [Pipeline Freshness](#22--pipeline-freshness) | Data Quality | No |
| 23 | [Data Rejection Rate](#23--data-rejection-rate) | Data Quality | No |
| 24 | [Model Drift Status](#24--model-drift-status) | Data Quality | No |

---

## KPI Definitions

---

### 1 · Availability %

| Attribute | Value |
|-----------|-------|
| **Business Definition** | Percentage of operational hours in which a product was available for sale (not stocked out) at a given store. |
| **Formula** | `(operational_hours − stockout_hours) / operational_hours × 100` |
| **Grain** | Store × Product × Day |
| **Aggregation** | Average across products (store-level); weighted average by demand (network-level) |
| **Filters** | Operational hours only (06:00–22:00). Exclude planned non-sale hours. |
| **Owner** | Store Manager / COO |
| **Source Table** | `gold.fact_stockout_incident`, `gold.dim_date` |
| **Refresh** | Daily |
| **Target** | ≥ 95% (configurable per category) |
| **Limitations** | Stockout detection is inferred from zero-sales signals, not from actual inventory counts. Brief stockouts within an hour may be missed if a sale still occurs in that hour. |

---

### 2 · Stockout Operational Hours

| Attribute | Value |
|-----------|-------|
| **Business Definition** | Total number of operational hours during which a product was detected as stocked out. |
| **Formula** | `COUNT(hours WHERE is_stockout = TRUE AND hour BETWEEN 6 AND 21)` |
| **Grain** | Store × Product × Day |
| **Aggregation** | SUM across products, stores, or dates |
| **Filters** | Operational hours only (06:00–22:00) |
| **Owner** | Store Manager |
| **Source Table** | `gold.fact_sales_hourly` |
| **Refresh** | Daily |
| **Target** | Minimize — no fixed threshold |
| **Limitations** | Based on inferred stockout flags; does not distinguish between true stockouts and genuine zero-demand hours for slow-moving items. |

---

### 3 · Stockout Incident Count

| Attribute | Value |
|-----------|-------|
| **Business Definition** | Number of distinct stockout incidents (contiguous blocks of stockout hours) for a product at a store on a given day. |
| **Formula** | `COUNT(DISTINCT incident_id) WHERE is_stockout = TRUE` |
| **Grain** | Store × Product × Day |
| **Aggregation** | SUM across products or stores |
| **Filters** | Operational hours only |
| **Owner** | Store Manager |
| **Source Table** | `gold.fact_stockout_incident` |
| **Refresh** | Daily |
| **Target** | Minimize — trending down week-over-week |
| **Limitations** | Incident boundaries depend on the stockout detection algorithm. A product that flickers between in-stock and out-of-stock within an hour may generate multiple short incidents. |

---

### 4 · Average Incident Duration

| Attribute | Value |
|-----------|-------|
| **Business Definition** | Mean duration (in hours) of a stockout incident. Indicates whether stockouts are brief or persistent. |
| **Formula** | `SUM(stockout_hours) / COUNT(DISTINCT incident_id)` |
| **Grain** | Store × Product × Day (or aggregated) |
| **Aggregation** | Weighted average by incident count |
| **Filters** | Operational hours only |
| **Owner** | Store Manager / Supply Planner |
| **Source Table** | `gold.fact_stockout_incident` |
| **Refresh** | Daily |
| **Target** | < 2 hours average |
| **Limitations** | An incident that starts before 06:00 or ends after 22:00 is truncated to operational hours, which may understate true duration. |

---

### 5 · Observed Demand

| Attribute | Value |
|-----------|-------|
| **Business Definition** | The demand actually recorded at the point of sale — i.e., units sold. This is the raw, potentially censored signal. |
| **Formula** | `SUM(sale_amount)` |
| **Grain** | Store × Product × Hour |
| **Aggregation** | SUM across any dimension |
| **Filters** | None (includes zero-sale hours) |
| **Owner** | Category Manager |
| **Source Table** | `gold.fact_sales_hourly` |
| **Refresh** | Daily |
| **Target** | N/A — descriptive metric |
| **Limitations** | `sale_amount` is **normalized** (not real retail units). Values are relative, not absolute. Censored during stockout hours — does not represent true demand. |

---

### 6 · Recovered Demand

| Attribute | Value |
|-----------|-------|
| **Business Definition** | The model's estimate of what sales *would have been* during stockout hours, had the product remained in stock. This is the censored demand restored by the demand recovery module. |
| **Formula** | `SUM(recovered_sale_amount)` — output of the demand recovery model for stockout hours |
| **Grain** | Store × Product × Hour |
| **Aggregation** | SUM across any dimension |
| **Filters** | Only applies to hours where `is_stockout = TRUE` |
| **Owner** | Data Scientist / Category Manager |
| **Source Table** | `gold.fact_sales_hourly` (recovered_sale_amount column) |
| **Refresh** | Daily (after model scoring) |
| **Target** | N/A — descriptive metric |
| **Limitations** | Model-estimated, not observed. Accuracy depends on the demand recovery model's quality. Uses normalized sale_amount units. |

---

### 7 · Estimated Lost Demand

| Attribute | Value |
|-----------|-------|
| **Business Definition** | The difference between recovered demand and observed demand during stockout hours. Represents the demand that was lost due to stockouts. |
| **Formula** | `SUM(recovered_sale_amount − sale_amount) WHERE is_stockout = TRUE` |
| **Grain** | Store × Product × Hour |
| **Aggregation** | SUM across any dimension |
| **Filters** | Stockout hours only |
| **Owner** | Category Manager / COO |
| **Source Table** | `gold.fact_sales_hourly` |
| **Refresh** | Daily |
| **Target** | Minimize — trending down |
| **Limitations** | Derived from a model estimate; inherits all limitations of the demand recovery module. Normalized units, not real currency. |

---

### 8 · Scenario Lost-Sales Cost

| Attribute | Value |
|-----------|-------|
| **Business Definition** | ⚠️ **SIMULATED** — The estimated monetary value of demand lost due to stockouts, calculated using simulated unit prices and margins. |
| **Formula** | `SUM(estimated_lost_demand × simulated_unit_margin)` |
| **Grain** | Store × Product × Day |
| **Aggregation** | SUM across any dimension |
| **Filters** | Stockout hours only |
| **Owner** | COO / Category Manager |
| **Source Table** | `gold.fact_stockout_incident`, `gold.dim_product` |
| **Refresh** | Daily |
| **Target** | Minimize |
| **Limitations** | **All monetary values are simulated.** Unit price, cost, and margin are generated from category-based rules — not real commercial data. Use for relative comparisons and scenario analysis only. |

---

### 9 · Scenario Waste Cost

| Attribute | Value |
|-----------|-------|
| **Business Definition** | ⚠️ **SIMULATED** — The estimated cost of products that expired unsold, based on simulated shelf-life and unit costs. |
| **Formula** | `SUM(simulated_expired_qty × simulated_unit_cost)` |
| **Grain** | Store × Product × Day |
| **Aggregation** | SUM across any dimension |
| **Filters** | Perishable categories only (where `simulated_shelf_life_hours < 336`) |
| **Owner** | COO / Category Manager |
| **Source Table** | `gold.fact_policy_simulation`, `gold.dim_product` |
| **Refresh** | Daily |
| **Target** | Minimize |
| **Limitations** | **Simulated.** No real expiry tracking exists in the dataset. Shelf-life, cost, and spoilage are modeled using category-based assumptions. |

---

### 10 · Service Level

| Attribute | Value |
|-----------|-------|
| **Business Definition** | Proportion of demand periods (hours) in which the product was available. Measures the probability that a customer arriving in any given hour finds the product in stock. |
| **Formula** | `COUNT(hours WHERE is_stockout = FALSE) / COUNT(operational_hours) × 100` |
| **Grain** | Store × Product × Day |
| **Aggregation** | Weighted average by demand volume |
| **Filters** | Operational hours only |
| **Owner** | Supply Planner / COO |
| **Source Table** | `gold.fact_sales_hourly` |
| **Refresh** | Daily |
| **Target** | ≥ 95% (default); configurable per category |
| **Limitations** | Measures time-based availability, not fill-rate (quantity-based). A product could be "available" with only 1 unit on shelf. |

---

### 11 · Fill Rate

| Attribute | Value |
|-----------|-------|
| **Business Definition** | Proportion of total demand that was fulfilled from available stock. Measures quantity-based service. |
| **Formula** | `SUM(observed_demand) / SUM(recovered_demand) × 100` |
| **Grain** | Store × Product × Day |
| **Aggregation** | Weighted average |
| **Filters** | All operational hours |
| **Owner** | Supply Planner |
| **Source Table** | `gold.fact_sales_hourly` |
| **Refresh** | Daily |
| **Target** | ≥ 97% |
| **Limitations** | Recovered demand is model-estimated. Fill rate accuracy is bounded by demand recovery model quality. |

---

### 12 · Forecast WAPE

| Attribute | Value |
|-----------|-------|
| **Business Definition** | Weighted Absolute Percentage Error of the demand forecast. Measures overall forecast accuracy, weighted by actual demand volume. |
| **Formula** | `SUM(|actual − forecast|) / SUM(actual) × 100` |
| **Grain** | Store × Product × Forecast Horizon |
| **Aggregation** | Weighted across products/stores |
| **Filters** | Evaluation set only (test period). Exclude zero-demand hours unless product is expected to sell. |
| **Owner** | Data Scientist / Supply Planner |
| **Source Table** | `gold.fact_forecast` |
| **Refresh** | Per model training cycle |
| **Target** | < 25% for daily aggregates; < 40% for hourly |
| **Limitations** | WAPE is volume-weighted — high-volume products dominate the metric. Does not penalize bias direction. |

---

### 13 · Forecast Bias

| Attribute | Value |
|-----------|-------|
| **Business Definition** | Systematic directional error in the forecast. Positive bias = over-forecasting; negative bias = under-forecasting. |
| **Formula** | `SUM(forecast − actual) / SUM(actual) × 100` |
| **Grain** | Store × Product × Forecast Horizon |
| **Aggregation** | Averaged across products/stores |
| **Filters** | Evaluation set only |
| **Owner** | Data Scientist / Supply Planner |
| **Source Table** | `gold.fact_forecast` |
| **Refresh** | Per model training cycle |
| **Target** | Between −5% and +5% |
| **Limitations** | A forecast can have low bias but high error (equally wrong in both directions). Must be interpreted alongside WAPE. |

---

### 14 · P90 Coverage

| Attribute | Value |
|-----------|-------|
| **Business Definition** | Proportion of actual demand observations that fall at or below the model's 90th-percentile forecast quantile. Measures whether the upper forecast bound is appropriately calibrated. |
| **Formula** | `COUNT(actual ≤ forecast_q90) / COUNT(observations) × 100` |
| **Grain** | Store × Product × Forecast Horizon |
| **Aggregation** | Average across products/stores |
| **Filters** | Evaluation set only |
| **Owner** | Data Scientist |
| **Source Table** | `gold.fact_forecast` |
| **Refresh** | Per model training cycle |
| **Target** | 88%–92% (should approximate 90%) |
| **Limitations** | Requires probabilistic (quantile) forecasts. A well-calibrated P90 should cover ~90% of actuals — significantly higher suggests the model is too conservative. |

---

### 15 · Forecast Value Added (FVA)

| Attribute | Value |
|-----------|-------|
| **Business Definition** | The improvement (or degradation) in forecast accuracy that the ML model provides over a naïve baseline (e.g., seasonal naïve or simple moving average). |
| **Formula** | `(WAPE_baseline − WAPE_model) / WAPE_baseline × 100` |
| **Grain** | Store × Product × Forecast Horizon |
| **Aggregation** | Weighted average by demand volume |
| **Filters** | Evaluation set only |
| **Owner** | Data Scientist |
| **Source Table** | `gold.fact_forecast`, `gold.fact_model_monitoring` |
| **Refresh** | Per model training cycle |
| **Target** | > 0% (model must beat baseline) |
| **Limitations** | Baseline choice affects FVA magnitude. A weak baseline inflates FVA. Always report which baseline is used. |

---

### 16 · Stockout PR-AUC

| Attribute | Value |
|-----------|-------|
| **Business Definition** | Area Under the Precision-Recall Curve for the stockout risk classifier. Measures how well the model discriminates between hours that will and will not experience a stockout. |
| **Formula** | Standard PR-AUC computation on `(y_true=is_stockout, y_score=stockout_probability)` |
| **Grain** | Model-level (evaluated on test set) |
| **Aggregation** | Micro-average across all store × product × hour observations |
| **Filters** | Evaluation set only |
| **Owner** | Data Scientist |
| **Source Table** | `gold.fact_stockout_risk`, `gold.fact_model_monitoring` |
| **Refresh** | Per model training cycle |
| **Target** | > 0.40 (given class imbalance) |
| **Limitations** | PR-AUC is preferred over ROC-AUC for imbalanced classes. Threshold for alerts is set independently of PR-AUC. |

---

### 17 · Alert Precision

| Attribute | Value |
|-----------|-------|
| **Business Definition** | Among all stockout alerts fired (predictions above the alert threshold), the proportion that corresponded to actual stockouts. Measures false-alarm rate. |
| **Formula** | `TRUE_POSITIVES / (TRUE_POSITIVES + FALSE_POSITIVES) × 100` |
| **Grain** | Model-level at chosen operating threshold |
| **Aggregation** | Across all alerted hours |
| **Filters** | Only hours where `stockout_probability ≥ alert_threshold` |
| **Owner** | Data Scientist / Store Manager |
| **Source Table** | `gold.fact_stockout_risk` |
| **Refresh** | Per model training cycle |
| **Target** | ≥ 60% (balance between catching stockouts and avoiding alert fatigue) |
| **Limitations** | Precision and recall trade off — increasing threshold raises precision but lowers recall. Must be tuned per use case. |

---

### 18 · Recommendation Coverage

| Attribute | Value |
|-----------|-------|
| **Business Definition** | Percentage of at-risk store × product combinations for which the recommendation engine produced an actionable recommendation (replenish, markdown, or monitor). |
| **Formula** | `COUNT(DISTINCT recommendations) / COUNT(DISTINCT at_risk_combinations) × 100` |
| **Grain** | Day × Store |
| **Aggregation** | Average across stores |
| **Filters** | Only products flagged as at-risk by the stockout classifier |
| **Owner** | Supply Planner |
| **Source Table** | `gold.fact_recommendation`, `gold.fact_stockout_risk` |
| **Refresh** | Daily |
| **Target** | ≥ 95% of at-risk items receive a recommendation |
| **Limitations** | Coverage does not measure recommendation quality — only that a recommendation was generated. |

---

### 19 · Urgent Recommendation Count

| Attribute | Value |
|-----------|-------|
| **Business Definition** | Number of recommendations classified as "urgent" (high stockout probability + high impact product) that require immediate action. |
| **Formula** | `COUNT(*) WHERE recommendation_urgency = 'urgent'` |
| **Grain** | Day × Store |
| **Aggregation** | SUM across stores |
| **Filters** | Only urgent-tier recommendations |
| **Owner** | Store Manager |
| **Source Table** | `gold.fact_recommendation` |
| **Refresh** | Daily (or intra-day if streaming is active) |
| **Target** | Context-dependent — a spike indicates supply chain stress |
| **Limitations** | Urgency classification depends on the threshold calibration of the stockout risk model. |

---

### 20 · Simulated Expired Quantity

| Attribute | Value |
|-----------|-------|
| **Business Definition** | ⚠️ **SIMULATED** — Estimated number of units that expired unsold, calculated using simulated shelf-life durations applied to excess inventory estimates. |
| **Formula** | `SUM(units_on_hand − units_sold) WHERE simulated_days_since_receipt ≥ simulated_shelf_life_days AND excess > 0` |
| **Grain** | Store × Product × Day |
| **Aggregation** | SUM across any dimension |
| **Filters** | Perishable categories only |
| **Owner** | Category Manager |
| **Source Table** | `gold.fact_policy_simulation` |
| **Refresh** | Daily |
| **Target** | Minimize |
| **Limitations** | **Fully simulated.** No real inventory-on-hand or expiry data exists. Based on modeled shelf-life and demand fulfillment assumptions. |

---

### 21 · Simulated Total Cost

| Attribute | Value |
|-----------|-------|
| **Business Definition** | ⚠️ **SIMULATED** — Combined estimated cost across all four cost components: lost sales + waste + holding + emergency replenishment. |
| **Formula** | `scenario_lost_sales_cost + scenario_waste_cost + simulated_holding_cost + simulated_emergency_cost` |
| **Grain** | Store × Day (or aggregated) |
| **Aggregation** | SUM |
| **Filters** | All products |
| **Owner** | COO |
| **Source Table** | `gold.fact_policy_simulation` |
| **Refresh** | Daily |
| **Target** | Minimize — primary optimization objective |
| **Limitations** | **Entirely simulated.** All cost components use generated commercial parameters. Useful for relative comparisons and what-if analysis, not for P&L reporting. |

---

### 22 · Pipeline Freshness

| Attribute | Value |
|-----------|-------|
| **Business Definition** | Time elapsed since the last successful completion of the end-to-end data pipeline (ingest → bronze → silver → gold → predictions). |
| **Formula** | `NOW() − MAX(pipeline_completed_at)` |
| **Grain** | Pipeline-level |
| **Aggregation** | N/A |
| **Filters** | Only successful runs |
| **Owner** | Data Engineer |
| **Source Table** | `gold.fact_pipeline_run` |
| **Refresh** | Continuous |
| **Target** | < 4 hours (for daily batch pipeline) |
| **Limitations** | Measures end-to-end latency, not individual step health. A pipeline can be "fresh" but have degraded quality. |

---

### 23 · Data Rejection Rate

| Attribute | Value |
|-----------|-------|
| **Business Definition** | Percentage of incoming data rows that fail schema validation, data contract checks, or quality rules during ingestion. |
| **Formula** | `COUNT(rejected_rows) / COUNT(total_rows) × 100` |
| **Grain** | Batch / Ingestion Run |
| **Aggregation** | Average across batches |
| **Filters** | All ingestion runs |
| **Owner** | Data Engineer |
| **Source Table** | `gold.fact_pipeline_run` |
| **Refresh** | Per ingestion run |
| **Target** | < 0.1% |
| **Limitations** | Only catches violations covered by defined data contracts. Novel data quality issues (e.g., subtle distribution shifts) are not caught by schema validation. |

---

### 24 · Model Drift Status

| Attribute | Value |
|-----------|-------|
| **Business Definition** | Categorical indicator of whether a deployed model's performance has degraded beyond acceptable thresholds compared to its training-time baseline. |
| **Formula** | Rule-based: `IF current_WAPE > training_WAPE × 1.2 OR current_bias NOT IN (−10%, +10%) THEN 'DRIFTED' ELSE 'STABLE'` |
| **Grain** | Model × Evaluation Window |
| **Aggregation** | N/A (categorical) |
| **Filters** | Rolling 7-day evaluation window |
| **Owner** | Data Scientist |
| **Source Table** | `gold.fact_model_monitoring` |
| **Refresh** | Daily |
| **Target** | `STABLE` |
| **Limitations** | Uses simple threshold rules, not statistical drift tests (e.g., PSI, KS). May flag normal seasonal variation as drift. |

---

## Governance Rules

1. **Single Source of Truth** — This document is the authoritative definition for every KPI. Dashboard implementations must reference these formulas exactly.
2. **Change Control** — Any KPI definition change requires a version bump and review by the KPI owner.
3. **Simulated Flag** — Every KPI that depends on simulated commercial data must be clearly labeled with ⚠️ SIMULATED in all UIs.
4. **Grain Consistency** — KPIs must not be compared across different grains without explicit aggregation documentation.
5. **Filter Transparency** — All filters applied to a KPI must be visible to the end user in the dashboard.

---

*For the data tables underlying these KPIs, see [data_dictionary.md](data_dictionary.md). For assumptions about simulated fields, see [assumptions.md](assumptions.md).*
