# FreshFlow AI — Risk Register

> **Version:** 0.1.0 · **Status:** Living Document · **Last Updated:** 2026-07-16

---

## Overview

This document catalogs known risks to the FreshFlow AI project, their potential impact, likelihood, and planned mitigations. Risks are reviewed at each phase gate and updated as the project evolves.

### Risk Scoring

| Level | Likelihood | Impact |
|-------|-----------|--------|
| **High** | Very likely to occur | Significant — could block deliverables, invalidate results, or require major rework |
| **Medium** | Possible — may occur under certain conditions | Moderate — causes delays, degrades quality, or requires workarounds |
| **Low** | Unlikely under normal circumstances | Minor — cosmetic, easily fixable, or limited blast radius |

---

## Risk Register

| # | Risk | Category | Likelihood | Impact | Severity | Mitigation |
|---|------|----------|-----------|--------|----------|------------|
| R01 | **Stockout labels are noisy** — the `is_stockout_by_hours` flags in the source data may mislabel slow-moving products (zero demand ≠ stockout) as stocked out, or miss brief within-hour stockouts | Data Quality | High | High | 🔴 Critical | Build a heuristic pre-filter that cross-references zero sales with product velocity, day-of-week patterns, and neighboring-hour sales before accepting stockout labels. Evaluate label quality with a confusion-matrix audit on a sample. |
| R02 | **Censored demand recovery model compounds errors downstream** — the demand recovery model's output feeds into the demand forecaster and KPIs; systematic overestimation or underestimation propagates through the entire system | Model | High | High | 🔴 Critical | Validate recovery model against held-out non-stockout periods (artificially censor known-demand hours and measure recovery accuracy). Implement uncertainty bounds on recovered values. Flag KPIs that depend on recovered demand. |
| R03 | **Normalized `sale_amount` misinterpreted as real units** — users or downstream code treats normalized values as actual retail units, leading to incorrect conclusions | Communication | Medium | High | 🟠 High | Enforce labeling in all UIs ("normalized sales"), add assertions in code that prevent unit-based calculations (e.g., revenue = qty × price) without explicit disclaimers, and document prominently in assumptions.md. |
| R04 | **Simulated commercial fields mistaken for real data** — simulated prices, costs, shelf-life, and margins are treated as ground truth for financial decisions | Communication | Medium | High | 🟠 High | Tag every simulated column with a `simulated_` prefix in schema. Display ⚠️ SIMULATED badges in all dashboards. Include simulation disclaimer in API response headers. |
| R05 | **90-day dataset is too short for robust seasonality modeling** — models cannot learn annual seasonal patterns, holiday effects, or long-term trends from only 3 months of data | Data Scope | High | Medium | 🟠 High | Focus on short-horizon forecasts (1h to 7 days) where 90 days provides sufficient training signal. Do not claim annual seasonality capability. Document this limitation in model cards. Use day-of-week and time-of-day features instead. |
| R06 | **Spark cluster resource contention or OOM on full dataset explosion** — exploding 4.85M daily rows × 24 hours = 116M hourly rows may exceed available memory in a single-worker Docker setup | Infrastructure | Medium | Medium | 🟡 Medium | Partition processing by `city_id` or `dt` to reduce per-partition memory. Configure Spark with appropriate `spark.driver.memory` and `spark.executor.memory`. Provide a "lite" mode that processes a subset of cities for development. |
| R07 | **Docker Compose environment complexity** — 15+ services across 4 profiles create setup friction, port conflicts, and "works on my machine" issues | Infrastructure | Medium | Medium | 🟡 Medium | Provide a `Makefile` or `justfile` with named targets (`make up-core`, `make up-full`). Pin all image versions. Include a health-check script that validates all services are running. Document minimum hardware requirements. |
| R08 | **dbt ↔ PySpark layer boundary causes schema drift** — changes to PySpark Silver output may silently break dbt Gold models if schemas are not synchronized | Data Quality | Medium | Medium | 🟡 Medium | Define data contracts (`config/data_contracts/*.yml`) at each layer boundary. Run schema-validation tests in CI. dbt `source` definitions should include column-level tests. Alert on any new or missing column. |
| R09 | **Class imbalance in stockout prediction** — stockout hours are a small minority of all hours, making the classifier prone to high false-positive rates or poor recall | Model | High | Medium | 🟡 Medium | Use PR-AUC (not ROC-AUC) as the primary evaluation metric. Apply class weighting or focal loss during training. Calibrate predicted probabilities with isotonic regression. Set alert threshold based on precision/recall trade-off analysis. |
| R10 | **Forecast evaluation on censored data gives misleading accuracy** — if the test set contains stockout hours where `sale_amount = 0`, standard error metrics (WAPE, MAE) will be biased | Model | Medium | Medium | 🟡 Medium | Evaluate forecasts on **non-censored hours only** (where `is_stockout = FALSE`) as the primary metric. Report censored-hour metrics separately with caveats. Use recovered demand as a secondary evaluation target. |
| R11 | **Kafka replay simulation oversells streaming capability** — stakeholders may interpret the Kafka replay pipeline as evidence of real-time processing capability | Communication | Low | Medium | 🟢 Low | Clearly label the streaming profile as "replay simulation" in all documentation and UI. Never use the word "real-time" without the qualifier "simulated." Explain the replay mechanism in architecture.md. |
| R12 | **Model drift detection has limited statistical power** — with only 90 days of data and a simple threshold-based drift detector, the system may generate false drift alerts or miss genuine degradation | Model | Medium | Low | 🟢 Low | Start with simple threshold rules (WAPE > 1.2× baseline) and iterate. Log all drift decisions for post-hoc analysis. Plan to upgrade to statistical tests (PSI, KS test) when more data or production deployment is available. |

---

## Risk Matrix Visualization

```
                        IMPACT
                 Low      Medium      High
            ┌──────────┬──────────┬──────────┐
    High    │          │ R05, R09 │ R01, R02 │
            ├──────────┼──────────┼──────────┤
LIKELIHOOD  │          │ R06, R07 │ R03, R04 │
  Medium    │          │ R08, R10 │          │
            ├──────────┼──────────┼──────────┤
    Low     │          │ R11     │          │
            │   R12    │          │          │
            └──────────┴──────────┴──────────┘
```

---

## Escalation & Review Process

| Trigger | Action |
|---------|--------|
| New risk identified | Add to register, assign severity, define mitigation, notify team |
| Risk materializes | Activate mitigation plan, escalate to project lead if severity ≥ High |
| Phase gate review | Review all open risks, update likelihood/impact based on current evidence |
| Mitigation completed | Mark risk as "mitigated" with evidence, move to closed section |

---

*This register is reviewed at each project phase gate. For the assumptions that drive many of these risks, see [assumptions.md](assumptions.md).*
