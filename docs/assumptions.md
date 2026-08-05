# FreshFlow AI — Assumptions & Limitations

> **Version:** 0.1.0 · **Status:** Living Document · **Last Updated:** 2026-07-16

---

## Overview

FreshFlow AI is built on the **FreshRetailNet-50K** synthetic dataset. This document explicitly states every assumption, approximation, and known limitation. Any consumer of FreshFlow AI outputs — dashboards, KPIs, recommendations — **must** read and understand this document.

> [!CAUTION]
> **No assumption listed here should be silently ignored.** If a downstream decision depends on a simulated field or normalized value, the user interface must clearly communicate this to the end user.

---

## 1 · Dataset Scope

| Attribute | Value |
|-----------|-------|
| **Dataset** | FreshRetailNet-50K |
| **Source** | Synthetic / anonymized retail data |
| **Time Span** | ~90 calendar days |
| **Cities** | 18 (anonymized, identified by `city_id` 1–18) |
| **Stores** | 898 (anonymized, identified by `store_id` 1–898) |
| **Products / SKUs** | 865 (anonymized, identified by `product_id` 1–865) |
| **Daily Rows** | ~4.85 million |
| **Hourly Rows** (after explosion) | ~116 million (4.85M × 24 hours) |
| **Operational Hourly Rows** | ~77.6 million (4.85M × 16 operational hours) |

### Implications

- **90-day window** limits the ability to model seasonality beyond monthly patterns. Annual seasonality, holiday effects, and long-term trends cannot be captured.
- **No product hierarchy** — product IDs are flat; there is no category/subcategory structure in the source data. Category assignments used in FreshFlow AI are **simulated**.
- **No store hierarchy** beyond city — there is no region, district, or format (hypermarket vs. convenience) classification.
- **No customer-level data** — no loyalty card, basket composition, or trip-type information.

---

## 2 · Sale Amount — Normalized Values

> [!WARNING]
> **`sale_amount` is a normalized value, not real retail units or currency.**

| Aspect | Detail |
|--------|--------|
| **What it is** | A relative, continuous, non-negative quantity representing sales volume |
| **What it is NOT** | Real units sold, pieces, kilograms, liters, or revenue |
| **Range** | Typically 0.0 to ~50.0 (varies by product) |
| **Zero values** | May indicate stockout, genuine zero demand, or store closure |

### Rules for Interpretation

1. **Relative comparisons are valid** — "Product A sells 2× as much as Product B" is meaningful.
2. **Absolute values are NOT meaningful** — "Product A sold 7.3" has no physical meaning without denormalization (which is unavailable).
3. **All KPIs derived from `sale_amount`** (demand, lost demand, forecast error) inherit this normalization.
4. **Never present raw values as "units sold"** in user-facing dashboards. Always label as "normalized sales."

---

## 3 · Simulated Commercial Fields

The FreshRetailNet-50K dataset does **not** contain any of the following:

| Missing Field | Status in FreshFlow AI |
|---------------|----------------------|
| Unit retail price | ⚠️ **SIMULATED** |
| Unit cost (COGS) | ⚠️ **SIMULATED** |
| Gross margin | ⚠️ **SIMULATED** (derived from simulated price − cost) |
| Product shelf life / expiry | ⚠️ **SIMULATED** |
| Supplier lead time | ⚠️ **SIMULATED** |
| Inventory on hand (IOH) | ⚠️ **NOT AVAILABLE** — not simulated |
| Safety stock levels | ⚠️ **SIMULATED** |
| Order history | ⚠️ **NOT AVAILABLE** — not simulated |
| Product category / hierarchy | ⚠️ **SIMULATED** |

### Simulation Rules

All simulated fields are generated using deterministic rules defined in [`config/simulation/product_economics.yml`](../config/simulation/product_economics.yml):

1. **Random seed is fixed** (`seed: 42`) for reproducibility.
2. **Category assignment** is based on `product_id` ranges — not learned from data.
3. **Price generation** uses category-specific uniform distributions.
4. **Cost ratio** is a fixed percentage of price per category.
5. **Shelf life** is assigned per category with randomized variation.
6. **Lead time** is assigned per category.

### Labeling Requirements

Every dashboard, report, table, or API response that surfaces a simulated field **must**:

- Display a ⚠️ or `[SIMULATED]` badge next to the value
- Include a tooltip or footnote explaining the simulation basis
- Never present simulated values alongside real data without clear visual distinction

---

## 4 · Money-Based Impact — Scenario Estimates

> [!IMPORTANT]
> **All monetary KPIs in FreshFlow AI are scenario-based estimates, not real financial figures.**

Because prices, costs, and margins are simulated, the following KPIs are **scenario analysis tools**, not actual financial metrics:

| KPI | Basis |
|-----|-------|
| Scenario Lost-Sales Cost | `estimated_lost_demand × simulated_unit_margin` |
| Scenario Waste Cost | `simulated_expired_qty × simulated_unit_cost` |
| Simulated Holding Cost | `avg_inventory × simulated_holding_rate × days` |
| Simulated Emergency Cost | `incident_count × simulated_surcharge` |
| Simulated Total Cost | Sum of above four components |

### Valid Uses

- Comparing **relative magnitude** between products, stores, or time periods
- Evaluating **what-if scenarios** (e.g., "if we raise service level from 95% to 98%, how does total cost change?")
- Ranking products by **estimated impact** for prioritization
- Demonstrating the **methodology** of cost-based decision optimization

### Invalid Uses

- Reporting as actual **profit & loss** figures
- Making real **procurement budget** decisions based solely on these numbers
- Comparing with **competitor benchmarks** in monetary terms

---

## 5 · Operational Hours

| Parameter | Value |
|-----------|-------|
| **Operational start** | 06:00 (hour index 6) |
| **Operational end** | 22:00 (hour index 21 is the last operational hour) |
| **Operational hours per day** | 16 |
| **Non-operational hours** | 00:00–05:00, 22:00–23:00 |

### Assumptions

- All 898 stores share the same operational hours. In reality, stores may have different opening times.
- **Hours 0–5 and 22–23 are excluded** from all availability, stockout, and demand calculations.
- Sales occurring in non-operational hours (if any exist in the data) are treated as noise and filtered out.
- Stockout detection during non-operational hours is meaningless and excluded.

---

## 6 · Discount Semantics

> [!WARNING]
> The `discount_by_hours` array uses **inverted discount semantics** compared to typical retail terminology.

| Value | Meaning |
|-------|---------|
| `1.0` | **No discount** — full price |
| `0.9` | **10% discount** — customer pays 90% of full price |
| `0.8` | **20% discount** — customer pays 80% of full price |
| `0.5` | **50% discount** |
| `0.0` | **100% discount** — given away free (extremely rare) |

### Interpretation

The discount value is a **price multiplier**, not a "percentage off" value:

```
Effective Price = Full Price × discount_factor
Discount Percentage = (1 − discount_factor) × 100%
```

All pipeline code and dashboards must use the multiplier semantics. UI labels should convert to "% off" for user-facing displays:

```python
# Correct: converting for display
discount_pct_off = (1 - discount_factor) * 100  # e.g., 0.9 → 10% off
```

---

## 7 · Weather Data

| Aspect | Detail |
|--------|--------|
| **Granularity** | **Daily only** — one weather observation per store per day |
| **Hourly treatment** | Daily weather values are **repeated identically** across all 16 operational hourly rows |
| **Fields** | `weather_main` (categorical), `avg_temperature`, `avg_humidity`, `avg_wind_level` |
| **Source** | External weather API (historical, already joined to source data) |

### Assumptions

- Weather does not vary within a day in this dataset. Actual intra-day weather changes are not captured.
- All stores in the same city share the same weather data.
- Weather is used as a **feature** for ML models, not as a primary driver. Its predictive contribution is expected to be modest.
- `avg_wind_level` is normalized and unitless — no physical interpretation.

---

## 8 · Stockout Detection

| Aspect | Detail |
|--------|--------|
| **Source** | `is_stockout_by_hours` array in source data (provided by dataset) |
| **Definition** | `1` = stocked out in that hour; `0` = in stock |
| **Ground truth?** | Treated as ground truth for model training, but is itself likely derived from heuristics (zero sales + context) rather than physical inventory checks |

### Assumptions

- The provided stockout flags are **accepted as-is** — FreshFlow AI does not re-derive stockout labels from scratch for the detection phase.
- A product can be stocked out for part of an hour but the flag is binary — partial-hour stockouts are treated as full-hour stockouts.
- Slow-moving products with genuinely zero demand may be **mislabeled** as stocked out. This is a known source of noise.
- The stockout risk classifier (ML model) uses these labels for training and evaluation — any label noise propagates into model performance.

---

## 9 · Streaming / Kafka

| Aspect | Detail |
|--------|--------|
| **Mode** | **Replay simulation** — historical data is replayed through Kafka topics at configurable speed |
| **Not** | A live, real-time feed from actual POS systems |
| **Purpose** | Demonstrate streaming architecture patterns (Kafka → Flink/Spark Streaming → Bronze) |

### Assumptions

- Event ordering in the replay mirrors the original chronological order.
- Replay speed is configurable (1×, 10×, 100× real-time) for testing.
- No out-of-order events or late-arriving data is simulated in the baseline replay.
- The streaming pipeline produces the **same Bronze output** as the batch pipeline — streaming is an alternative ingestion path, not a different data product.

---

## 10 · Model Training Assumptions

| Aspect | Detail |
|--------|--------|
| **Train/Test Split** | Temporal split — earliest N days for training, remaining for testing. No random splitting. |
| **Validation** | Time-series cross-validation within the training window |
| **Data Leakage** | All features available at prediction time in production must also be available at training time. Future information is never used as a feature. |
| **Recovered Demand** | The demand recovery model is trained first; its outputs are used as inputs to the demand forecaster. Error propagation between models is a known risk. |
| **Stationarity** | 90 days of data is assumed to be approximately stationary. Structural breaks (e.g., store renovations, major promotions) are not modeled. |

---

## 11 · General Limitations

| # | Limitation | Impact |
|---|-----------|--------|
| 1 | No real product names or categories | Cannot validate category-specific patterns against domain knowledge |
| 2 | No real prices or costs | Cannot compute actual financial metrics; all cost analysis is scenario-based |
| 3 | No inventory-on-hand data | Cannot compute exact reorder points, safety stock, or days-of-supply |
| 4 | No supplier or purchase order data | Lead times and order costs are simulated; no actual procurement validation |
| 5 | 90-day time window | Insufficient for annual seasonality, holiday modeling, or long-term trend detection |
| 6 | Normalized sales values | Absolute demand volumes cannot be determined; only relative comparisons valid |
| 7 | Daily-level weather only | Intra-day weather effects (morning rain vs. afternoon sun) cannot be modeled |
| 8 | Uniform operational hours | Store-specific schedules are not captured; all stores assumed open 06:00–22:00 |
| 9 | Binary stockout flags | Partial-hour and severity-graded stockouts are not distinguishable |
| 10 | No customer segmentation | Cannot model substitution effects, customer loyalty, or trip-type differences |
| 11 | Single-echelon view | Only store-level; no distribution center, warehouse, or supplier-tier data |
| 12 | Streaming is replay only | Architecture demonstrates the pattern but does not process real-time signals |

---

## 12 · How These Assumptions Are Enforced

| Mechanism | Where | What It Checks |
|-----------|-------|----------------|
| **Data Contracts** | `config/data_contracts/*.yml` | Column presence, types, value ranges, array lengths |
| **dbt Tests** | `dbt/tests/` | Referential integrity, uniqueness, not-null, accepted-values |
| **Dashboard Labels** | Streamlit / Power BI | ⚠️ SIMULATED badges on all simulated fields |
| **KPI Dictionary** | `docs/kpi_dictionary.md` | Each KPI's limitations are explicitly documented |
| **This Document** | `docs/assumptions.md` | Central registry of all assumptions |

---

*For simulation configuration details, see [product_economics.yml](../config/simulation/product_economics.yml) and [supplier_policy.yml](../config/simulation/supplier_policy.yml). For data column definitions, see [data_dictionary.md](data_dictionary.md).*
