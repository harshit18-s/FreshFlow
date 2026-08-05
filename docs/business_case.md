# FreshFlow AI — Business Case

> **Version:** 0.1.0 · **Status:** Living Document · **Last Updated:** 2026-07-16

---

## 1 · The Core Problem

### Observed Sales ≠ True Demand

Every retailer tracks **Point-of-Sale (POS)** data — the number of units scanned at checkout.
This is **observed sales**, not **true demand**.

When a product is **in stock**, observed sales approximate demand reasonably well.
When a product is **out of stock**, observed sales **drop to zero** — but customer demand does not.

```
True Demand:    ████████████████████████████████  (100 units)
Observed Sales: ████████████████████░░░░░░░░░░░░  ( 62 units — shelf went empty at 2 PM)
                                    ▲
                                 Stockout begins
```

The gap between true demand and observed sales during a stockout is called **censored demand** — the demand that existed but was never recorded because there was nothing to sell.

> [!IMPORTANT]
> **Censored demand is invisible in raw POS data.** Every downstream system that consumes raw sales inherits a systematic downward bias. Forecasts trained on censored data predict *less* than customers actually want — creating a vicious cycle of under-ordering and repeated stockouts.

### The Vicious Cycle

```
┌──────────────────────────────────────────────────────────────────────┐
│                                                                      │
│   Stockout occurs → Sales drop to 0 → Historical data is censored   │
│        ▲                                                    │        │
│        │                                                    ▼        │
│   Insufficient stock ← Under-order ← Forecast too low ← Bias       │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

This feedback loop is **self-reinforcing**: the more stockouts happen, the worse forecasts become, which causes even more stockouts.

---

## 2 · Why This Matters for Perishables

Fresh and perishable categories (dairy, bakery, produce, deli, prepared foods) amplify the problem in both directions:

| Direction | Risk | Consequence |
|-----------|------|-------------|
| **Under-order** | Stockout | Lost sales, disappointed customers, eroded loyalty |
| **Over-order** | Spoilage | Product expires on shelf → markdown losses, waste disposal costs, sustainability impact |

Unlike shelf-stable goods, perishables have a **hard expiry constraint**. The replenishment decision is a razor-thin optimization between two costly failure modes.

> [!WARNING]
> For perishables, the cost of getting it wrong in *either* direction is significant. A demand forecast that is merely "accurate on average" is insufficient — the retailer needs to understand the **full distribution** of demand including its upper tail to set appropriate service levels.

---

## 3 · The Cost Optimization Framework

FreshFlow AI frames replenishment as a **total-cost minimization** problem across four cost components:

### 3.1 Cost Components

| # | Cost Component | Definition | Driver |
|---|----------------|------------|--------|
| 1 | **Lost-Sales Cost** | Revenue forfeited when a customer wants to buy but the shelf is empty | Stockout duration × demand rate × unit margin |
| 2 | **Spoilage / Waste Cost** | Value destroyed when unsold perishable inventory expires | Units expired × unit cost + disposal cost |
| 3 | **Holding Cost** | Cost of carrying excess inventory (refrigeration, shelf space, capital) | Avg. inventory × holding-cost rate × time |
| 4 | **Emergency Replenishment Cost** | Premium paid for unscheduled, rush deliveries to cover unexpected demand | Frequency × per-incident surcharge |

### 3.2 The Optimization Objective

```
Minimize:  Total Cost = C_lost_sales + C_spoilage + C_holding + C_emergency

Subject to:
  • Service Level ≥ target (e.g., 95% or 98%)
  • Order quantity ≥ 0, integer
  • Lead time constraints
  • Shelf-life constraints (perishables)
  • Delivery window constraints
```

### 3.3 Trade-off Surface

```
                 High ▲
                      │        ╲  Lost-Sales Cost
    Cost              │         ╲
                      │          ╲         ╱  Spoilage Cost
                      │           ╲       ╱
                      │            ╲     ╱
                      │             ╲   ╱
                      │              ╳ ← Optimal Order Quantity
                      │             ╱ ╲
                      │            ╱   ╲
                 Low  │───────────╱─────╲────────────────►
                      Low          Order Quantity          High
```

> [!NOTE]
> The optimal order quantity sits at the **intersection** where the marginal cost of ordering one more unit (risk of spoilage) equals the marginal cost of ordering one fewer unit (risk of a lost sale). FreshFlow AI uses probabilistic forecasts (quantiles) to navigate this trade-off.

---

## 4 · Stakeholder Personas

FreshFlow AI is designed to serve **seven distinct personas** across the retail organization. Each has different decision horizons, KPI ownership, and information needs.

### 4.1 Persona Profiles

| # | Persona | Role | Decision Horizon | Primary KPIs | Key Pain Point |
|---|---------|------|-------------------|--------------|----------------|
| 1 | **COO** | Chief Operating Officer | Strategic (quarterly/annual) | Total cost, service level, waste % | No single view of lost-sales vs. waste trade-off across the network |
| 2 | **Category Manager** | Owns a product category's P&L | Tactical (weekly/monthly) | Category revenue, availability, markdown % | Cannot quantify how much revenue stockouts silently destroy |
| 3 | **Store Manager** | Runs daily store operations | Operational (daily/hourly) | Store availability, on-shelf %, incident count | Alert fatigue — too many signals, not enough actionable priorities |
| 4 | **Supply Planner** | Plans replenishment & logistics | Tactical (daily/weekly) | Fill rate, forecast accuracy, order cost | Forecasts are biased by stockout history; manual adjustments are time-consuming |
| 5 | **Data Analyst** | Creates reports and dashboards | Analytical (ad-hoc) | Data quality, KPI definitions, drill-down paths | KPIs are inconsistently defined; no single source of truth |
| 6 | **Data Scientist** | Builds and validates ML models | Model lifecycle (sprint-based) | WAPE, bias, PR-AUC, calibration, drift | Stockout labels are noisy; evaluation on censored data is misleading |
| 7 | **Data Engineer** | Maintains data pipelines | Infrastructure (continuous) | Pipeline freshness, rejection rate, SLA adherence | Schema changes break downstream; no contract enforcement |

### 4.2 Persona Decision Map

```
                    ┌─────────────────────┐
                    │        COO          │  "What is our total cost of
                    │   (Strategic)       │   stockouts vs. waste network-wide?"
                    └────────┬────────────┘
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
     ┌────────────┐  ┌────────────┐  ┌────────────┐
     │  Category   │  │   Supply   │  │   Store    │
     │  Manager    │  │  Planner   │  │  Manager   │
     │ (Tactical)  │  │ (Tactical) │  │ (Operatnl) │
     └──────┬─────┘  └─────┬──────┘  └─────┬──────┘
            │               │               │
            └───────┬───────┘               │
                    ▼                       ▼
           ┌────────────┐          ┌────────────┐
           │    Data     │          │    Data    │
           │  Scientist  │          │   Analyst  │
           └──────┬─────┘          └────────────┘
                  │
                  ▼
           ┌────────────┐
           │    Data     │
           │  Engineer   │
           └────────────┘
```

---

## 5 · Business Questions Catalog

All questions that FreshFlow AI must answer, organized by category and mapped to the persona who asks them.

### 5.1 Executive Questions

| # | Question | Primary Persona |
|---|----------|-----------------|
| E1 | What is our **network-wide estimated lost revenue** due to stockouts this week/month? | COO |
| E2 | Which **cities or stores** have the worst availability performance? | COO |
| E3 | What is the **total simulated waste cost** across all perishable categories? | COO |
| E4 | How does **service level** vary across store clusters? | COO |
| E5 | What is the **trade-off curve** between service level and total cost? | COO |
| E6 | Are we **improving or degrading** on key KPIs period-over-period? | COO |

### 5.2 Store-Level Questions

| # | Question | Primary Persona |
|---|----------|-----------------|
| S1 | Which products in **my store** are at risk of stocking out in the next 4–8 hours? | Store Manager |
| S2 | What is the **recommended action** for each at-risk product — replenish, markdown, or do nothing? | Store Manager |
| S3 | How many **stockout incidents** did my store have today, and what was the total duration? | Store Manager |
| S4 | Which **hours of the day** see the most stockout events? | Store Manager |
| S5 | What is the **estimated lost demand** in my store from yesterday's stockouts? | Store Manager |
| S6 | Are there products I should **markdown now** to avoid spoilage before closing? | Store Manager |

### 5.3 Product / Category Questions

| # | Question | Primary Persona |
|---|----------|-----------------|
| P1 | What is the **true (recovered) demand** for this product vs. what we observed? | Category Manager |
| P2 | Which products have the **highest frequency** of stockout incidents? | Category Manager |
| P3 | What is the **forecast accuracy** (WAPE, bias) for this category? | Supply Planner |
| P4 | How much **demand is being censored** (hidden) by chronic stockouts? | Category Manager |
| P5 | What **order quantity** should I place for this product for the next delivery cycle? | Supply Planner |
| P6 | What is the **probability of stockout** for this product in the next 4/8/12/24 hours? | Supply Planner |
| P7 | What is the **fill rate** for this product over the past 30 days? | Supply Planner |
| P8 | Which products have the **highest estimated spoilage** cost this week? | Category Manager |

### 5.4 Data & Model Questions

| # | Question | Primary Persona |
|---|----------|-----------------|
| D1 | Is the **data pipeline** running on schedule and within SLA? | Data Engineer |
| D2 | What is the **data rejection rate** — how many rows failed validation? | Data Engineer |
| D3 | Are any **data contracts** being violated by upstream changes? | Data Engineer |
| D4 | Has **model drift** been detected for the demand forecast or stockout classifier? | Data Scientist |
| D5 | What is the **forecast value added (FVA)** — does the ML model beat a naïve baseline? | Data Scientist |
| D6 | What is the **PR-AUC** of the stockout risk classifier? | Data Scientist |
| D7 | How well **calibrated** are the probabilistic forecast quantiles? | Data Scientist |
| D8 | What **features** contribute most to stockout risk predictions? | Data Scientist |

---

## 6 · Value Proposition Summary

| Without FreshFlow AI | With FreshFlow AI |
|----------------------|-------------------|
| Forecasts trained on censored sales → systematic under-prediction | Demand recovery module restores hidden demand before forecasting |
| Binary in-stock/out-of-stock view | Continuous stockout probability with configurable horizons |
| Reactive: discover stockouts after the fact | Proactive: predict stockouts 4–24 hours ahead |
| Generic order quantities based on averages | Quantile-based recommendations tuned to service-level targets |
| No visibility into lost revenue from stockouts | Scenario-based lost-sales estimation per product, store, day |
| Waste tracked only after disposal | Forward-looking spoilage risk based on shelf life + forecast |
| Siloed KPIs, inconsistent definitions | Unified KPI dictionary with single source of truth |
| Manual data quality monitoring | Automated data contracts and pipeline health monitoring |

---

## 7 · Scope & Boundaries

### In Scope

- Stockout detection from POS signals (zero-sales + contextual features)
- Censored demand recovery (Tobit-inspired, ML-based)
- Multi-horizon demand forecasting (1h to 7 days)
- Stockout risk prediction (classification with calibrated probabilities)
- Replenishment & markdown recommendation engine
- Policy simulation (what-if analysis across service levels)
- Unified KPI layer with automated monitoring
- End-to-end data pipeline with contract enforcement

### Out of Scope

- Real-time POS integration (Kafka layer is replay simulation)
- Actual financial transactions or live order placement
- Planogram or shelf-space optimization
- Customer-level demand modeling (basket analysis)
- Supplier negotiation or procurement automation
- Multi-echelon inventory optimization (DC → store)

> [!CAUTION]
> **All monetary values in FreshFlow AI are simulated.** The FreshRetailNet-50K dataset does not include real prices, costs, or margins. Commercial fields (unit_price, unit_cost, shelf_life, lead_time) are generated using documented simulation rules. All cost-based KPIs (lost-sales cost, waste cost, total cost) are scenario estimates, not actuals. See [assumptions.md](assumptions.md) for full details.

---

*This document is maintained as part of the FreshFlow AI project documentation. For technical architecture, see [architecture.md](architecture.md). For KPI definitions, see [kpi_dictionary.md](kpi_dictionary.md).*
