# FreshFlow AI — Architecture

> **Version:** 0.1.0 · **Status:** Living Document · **Last Updated:** 2026-07-16

---

## 1 · Logical Architecture

FreshFlow AI follows a **layered architecture** with clear separation between data ingestion, transformation, machine learning, serving, and presentation.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          PRESENTATION LAYER                                 │
│                                                                             │
│   ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐        │
│   │   Streamlit      │    │   Power BI       │    │   REST API      │        │
│   │   Dashboards     │    │   Reports        │    │   (FastAPI)     │        │
│   └────────┬────────┘    └────────┬────────┘    └────────┬────────┘        │
│            │                      │                      │                  │
└────────────┼──────────────────────┼──────────────────────┼──────────────────┘
             │                      │                      │
┌────────────┼──────────────────────┼──────────────────────┼──────────────────┐
│            ▼                      ▼                      ▼                  │
│                         SERVING LAYER                                       │
│                                                                             │
│   ┌─────────────────────────────────────────────────────────────────┐       │
│   │                     PostgreSQL (Gold Tables)                     │       │
│   │         Dimensions  ·  Facts  ·  Aggregates  ·  KPIs            │       │
│   └─────────────────────────────────────────────────────────────────┘       │
│                                                                             │
└─────────────────────────────────────┬───────────────────────────────────────┘
                                      │
┌─────────────────────────────────────┼───────────────────────────────────────┐
│                                     ▼                                       │
│                         ML / ANALYTICS LAYER                                │
│                                                                             │
│   ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│   │   Demand      │  │  Stockout    │  │  Recommend.  │  │   Policy     │  │
│   │   Recovery    │  │  Risk        │  │  Engine      │  │  Simulator   │  │
│   │   Module      │  │  Classifier  │  │              │  │              │  │
│   └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  │
│          │                  │                  │                  │          │
│          ▼                  ▼                  ▼                  ▼          │
│   ┌──────────────┐  ┌──────────────┐                                       │
│   │   Demand      │  │   MLflow     │                                       │
│   │   Forecaster  │  │   Registry   │                                       │
│   └──────┬───────┘  └──────────────┘                                       │
│          │                                                                  │
└──────────┼──────────────────────────────────────────────────────────────────┘
           │
┌──────────┼──────────────────────────────────────────────────────────────────┐
│          ▼                                                                  │
│                       TRANSFORMATION LAYER                                  │
│                                                                             │
│   ┌─────────────────────┐         ┌─────────────────────┐                  │
│   │    PySpark           │         │      dbt-core        │                  │
│   │    (Bronze → Silver) │         │   (Silver → Gold)    │                  │
│   └──────────┬──────────┘         └──────────┬──────────┘                  │
│              │                                │                             │
└──────────────┼────────────────────────────────┼─────────────────────────────┘
               │                                │
┌──────────────┼────────────────────────────────┼─────────────────────────────┐
│              ▼                                ▼                             │
│                        STORAGE LAYER                                        │
│                                                                             │
│   ┌─────────────────────────────────────────────────────────────────┐       │
│   │                   MinIO (S3-Compatible Object Store)             │       │
│   │                                                                  │       │
│   │   bronze/         silver/           gold/          mlflow/       │       │
│   │   └─ raw parquet  └─ cleaned        └─ dims+facts  └─ artifacts │       │
│   │                     daily+hourly      parquet        & models    │       │
│   └─────────────────────────────────────────────────────────────────┘       │
│                                                                             │
│   ┌──────────────────────────────────┐                                     │
│   │   PostgreSQL (Metadata + Serving) │                                     │
│   └──────────────────────────────────┘                                     │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
               ▲
┌──────────────┼──────────────────────────────────────────────────────────────┐
│              │                                                              │
│                        INGESTION LAYER                                      │
│                                                                             │
│   ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                 │
│   │  Batch        │    │  Kafka        │    │  Schema      │                 │
│   │  Ingest       │    │  Replay       │    │  Validation  │                 │
│   │  (CSV→Bronze) │    │  (Streaming)  │    │  (Contracts) │                 │
│   └──────────────┘    └──────────────┘    └──────────────┘                 │
│                                                                             │
│   ┌─────────────────────────────────────────────────────────────────┐       │
│   │              FreshRetailNet-50K Dataset (CSV)                    │       │
│   └─────────────────────────────────────────────────────────────────┘       │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2 · Physical Architecture — Docker Compose Services

FreshFlow AI runs as a set of **Docker Compose services** organized into **profiles** that can be activated independently.

### 2.1 Service Inventory

| Service | Image / Build | Ports | Profile | Purpose |
|---------|---------------|-------|---------|---------|
| `postgres` | `postgres:16` | 5432 | `core` | Metadata store, Gold serving layer, Airflow backend |
| `minio` | `minio/minio` | 9000, 9001 | `core` | S3-compatible object storage (Bronze/Silver/Gold/MLflow) |
| `mlflow` | `ghcr.io/mlflow/mlflow` | 5000 | `core` | Experiment tracking, model registry |
| `airflow-webserver` | Custom build | 8080 | `core` | DAG UI and API |
| `airflow-scheduler` | Custom build | — | `core` | DAG execution engine |
| `streamlit` | Custom build | 8501 | `core` | Interactive dashboards |
| `spark-master` | `bitnami/spark:3.5` | 8082, 7077 | `bigdata` | Spark cluster coordinator |
| `spark-worker` | `bitnami/spark:3.5` | 8083 | `bigdata` | Spark executor (scalable) |
| `kafka` | `bitnami/kafka:3.7` | 9092 | `streaming` | Event streaming (replay simulation) |
| `zookeeper` | `bitnami/zookeeper` | 2181 | `streaming` | Kafka coordination |
| `kafka-ui` | `provectuslabs/kafka-ui` | 8084 | `streaming` | Kafka topic browser |
| `prometheus` | `prom/prometheus` | 9090 | `monitoring` | Metrics collection |
| `grafana` | `grafana/grafana` | 3000 | `monitoring` | Metrics dashboards |
| `dbt` | Custom build | — | `core` | Silver → Gold transformations (run via Airflow) |
| `fastapi` | Custom build | 8000 | `core` | REST API for predictions and recommendations |

### 2.2 Docker Profiles

Profiles allow developers to run only the services they need:

```bash
# Core services only — sufficient for most development
docker compose --profile core up -d

# Core + Big Data (Spark cluster for large-scale processing)
docker compose --profile core --profile bigdata up -d

# Core + Streaming (Kafka replay simulation)
docker compose --profile core --profile streaming up -d

# Full stack — all services
docker compose --profile core --profile bigdata --profile streaming --profile monitoring up -d
```

| Profile | Services Included | Typical Use Case |
|---------|-------------------|------------------|
| `core` | postgres, minio, mlflow, airflow-*, streamlit, dbt, fastapi | Day-to-day development, testing, demos |
| `bigdata` | spark-master, spark-worker(s) | Large-scale PySpark transformations |
| `streaming` | kafka, zookeeper, kafka-ui | Streaming replay simulation, Kafka development |
| `monitoring` | prometheus, grafana | Performance monitoring, alerting, observability |

> [!TIP]
> Start with `core` profile only. Add `bigdata` when processing the full 4.85M-row dataset. Add `streaming` only when developing the Kafka replay pipeline.

---

## 3 · Medallion Data Architecture

FreshFlow AI implements a **three-layer medallion architecture** (Bronze → Silver → Gold) for progressive data refinement.

```
┌─────────────┐        ┌─────────────┐        ┌─────────────┐
│             │        │             │        │             │
│   BRONZE    │──────▶ │   SILVER    │──────▶ │    GOLD     │
│             │        │             │        │             │
│  Raw        │PySpark │  Cleaned    │  dbt   │  Star       │
│  Ingested   │        │  Validated  │        │  Schema     │
│  Immutable  │        │  Enriched   │        │  Dims+Facts │
│             │        │             │        │             │
│  Parquet    │        │  Parquet    │        │  Parquet +  │
│  in MinIO   │        │  in MinIO   │        │  PostgreSQL │
│             │        │             │        │             │
└─────────────┘        └─────────────┘        └─────────────┘
```

### 3.1 Bronze Layer

| Attribute | Value |
|-----------|-------|
| **Purpose** | Immutable, append-only landing zone for raw data |
| **Format** | Parquet (converted from CSV on ingest) |
| **Storage** | MinIO → `s3://freshflow/bronze/` |
| **Transformations** | None — raw data preserved exactly as received |
| **Additions** | Metadata columns: `_ingested_at`, `_source_file`, `_batch_id` |
| **Grain** | One row per store × product × day (matches source) |
| **Partitioning** | `dt` (date) |

### 3.2 Silver Layer

| Attribute | Value |
|-----------|-------|
| **Purpose** | Cleaned, validated, enriched, and exploded to hourly grain |
| **Format** | Parquet |
| **Storage** | MinIO → `s3://freshflow/silver/` |
| **Engine** | PySpark |
| **Key Operations** | Schema validation, null handling, type casting, array explosion (24-element arrays → 24 hourly rows), feature engineering, simulated commercial field attachment |
| **Daily Grain** | `silver_daily` — one row per store × product × day |
| **Hourly Grain** | `silver_hourly` — one row per store × product × hour (06:00–22:00 = 16 operational hours) |
| **Partitioning** | `dt`, `city_id` |

### 3.3 Gold Layer

| Attribute | Value |
|-----------|-------|
| **Purpose** | Analytics-ready star schema for dashboards, KPIs, and ML consumption |
| **Format** | Parquet (MinIO) + PostgreSQL (serving) |
| **Storage** | MinIO → `s3://freshflow/gold/` + PostgreSQL tables |
| **Engine** | dbt-core (SQL transformations) |
| **Schema** | Dimensional model — dimension tables + fact tables |
| **Consumers** | Streamlit dashboards, Power BI, FastAPI, ad-hoc SQL queries |

---

## 4 · End-to-End Data Flow

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│              │    │              │    │              │    │              │
│  CSV Files   │───▶│  Batch       │───▶│   BRONZE     │───▶│  PySpark     │
│  (Raw Data)  │    │  Ingest      │    │  (MinIO)     │    │  Jobs        │
│              │    │  + Validate  │    │              │    │              │
└──────────────┘    └──────────────┘    └──────────────┘    └──────┬───────┘
                                                                    │
                         ┌──────────────────────────────────────────┘
                         ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│              │    │              │    │              │    │              │
│   SILVER     │───▶│  dbt-core    │───▶│    GOLD      │───▶│  PostgreSQL  │
│  (MinIO)     │    │  Models      │    │  (MinIO)     │    │  (Serving)   │
│  Daily +     │    │              │    │  Dims+Facts  │    │              │
│  Hourly      │    │              │    │              │    │              │
└──────────────┘    └──────────────┘    └──────────────┘    └──────┬───────┘
                                                                    │
                         ┌──────────────────────────────────────────┘
                         ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│              │    │              │    │              │    │              │
│  ML Models   │───▶│  Predictions │───▶│  Recommend.  │───▶│  Streamlit   │
│  (MLflow)    │    │  + Forecasts │    │  Engine      │    │  Power BI    │
│              │    │              │    │              │    │  FastAPI     │
└──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘
```

### 4.1 Flow Summary

| Step | Source | Engine | Destination | Description |
|------|--------|--------|-------------|-------------|
| 1 | CSV files | Python / Airflow | Bronze (MinIO) | Raw ingest — CSV → Parquet, add metadata columns |
| 2 | Bronze | PySpark | Silver (MinIO) | Clean, validate, cast types, explode arrays to hourly, add simulated fields |
| 3 | Silver | dbt-core | Gold (MinIO + PostgreSQL) | Build star schema — dims, facts, aggregates |
| 4 | Gold | ML Pipeline (Python) | MLflow + PostgreSQL | Train/score demand forecasts, stockout risk, recommendations |
| 5 | PostgreSQL | Streamlit / Power BI / FastAPI | End Users | Dashboards, reports, API responses |

### 4.2 Orchestration

All pipeline steps are orchestrated by **Apache Airflow** DAGs:

| DAG | Schedule | Steps |
|-----|----------|-------|
| `ingest_daily` | Daily (or on-demand) | Validate CSV → Write Bronze Parquet → Log to metadata |
| `transform_silver` | After `ingest_daily` | PySpark: Bronze → Silver daily → Silver hourly |
| `transform_gold` | After `transform_silver` | dbt run: Silver → Gold dimensions + facts |
| `train_models` | Weekly (or on-demand) | Train demand recovery, forecaster, stockout classifier |
| `score_predictions` | After `transform_gold` | Score forecasts, stockout risk, generate recommendations |
| `quality_checks` | After each layer | Great Expectations / dbt tests / contract validation |
| `kafka_replay` | On-demand | Replay historical data through Kafka topics |

---

## 5 · Cloud Mapping

FreshFlow AI is designed as a **cloud-portable** platform. Every local service maps to a managed cloud equivalent:

| Local Service | AWS Equivalent | Azure Equivalent | GCP Equivalent | Notes |
|---------------|---------------|-------------------|----------------|-------|
| **MinIO** | Amazon S3 | Azure Blob / ADLS Gen2 | Google Cloud Storage | Object storage; Parquet files |
| **Apache Spark** | Amazon EMR / AWS Glue | Azure Synapse Spark | Dataproc / Databricks | PySpark transformations |
| **PostgreSQL** | Amazon RDS / Aurora | Azure Database for PostgreSQL | Cloud SQL | Metadata + Gold serving |
| **dbt-core** | dbt Cloud | dbt Cloud | dbt Cloud | SQL transformations |
| **Apache Airflow** | Amazon MWAA | Azure Data Factory | Cloud Composer | Pipeline orchestration |
| **MLflow** | SageMaker (partial) | Azure ML | Vertex AI (partial) | Experiment tracking + model registry |
| **Kafka** | Amazon MSK | Azure Event Hubs (Kafka mode) | Confluent on GCP | Event streaming |
| **Streamlit** | EC2 / ECS / App Runner | Azure App Service | Cloud Run | Dashboard hosting |
| **Prometheus + Grafana** | CloudWatch + Managed Grafana | Azure Monitor + Grafana | Cloud Monitoring | Observability |
| **Docker Compose** | ECS / EKS | AKS / Container Apps | GKE / Cloud Run | Container orchestration |
| **FastAPI** | Lambda + API Gateway / ECS | Azure Functions / App Service | Cloud Run / Cloud Functions | API serving |

> [!NOTE]
> The local Docker Compose setup is designed for **development parity** with cloud deployments. Switching from MinIO to S3 (for example) requires only changing the endpoint URL and credentials — the Parquet file format and path conventions remain identical.

---

## 6 · Network & Port Map

```
┌─────────────────────────────────────────────────────────────────┐
│                      Host Machine                                │
│                                                                  │
│   :8080  → Airflow Web UI                                       │
│   :8501  → Streamlit Dashboards                                 │
│   :8000  → FastAPI REST API                                     │
│   :5000  → MLflow Tracking UI                                   │
│   :9000  → MinIO API                                            │
│   :9001  → MinIO Console                                        │
│   :5432  → PostgreSQL                                           │
│   :8082  → Spark Master UI                                      │
│   :9092  → Kafka Broker                                         │
│   :8084  → Kafka UI                                             │
│   :9090  → Prometheus                                           │
│   :3000  → Grafana                                              │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 7 · Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| **Medallion (Bronze/Silver/Gold)** over flat staging | Progressive refinement makes debugging and reprocessing straightforward; each layer is independently queryable |
| **MinIO** over local filesystem | S3 API compatibility ensures cloud-portable code; Parquet + object store is the modern lakehouse pattern |
| **PySpark** for Bronze → Silver | Handles the array explosion (24 hourly elements) and 4.85M→116M row amplification efficiently |
| **dbt-core** for Silver → Gold | SQL-native dimensional modeling with built-in testing, documentation, and lineage |
| **PostgreSQL** as Gold serving layer | Enables standard SQL access for Streamlit, Power BI, and FastAPI without requiring Spark at query time |
| **Docker profiles** | Developers can run lightweight `core` profile for 90% of work; `bigdata` and `streaming` only when needed |
| **MLflow** for model management | Lightweight, open-source, tracks experiments + registers models + serves via API |
| **Airflow** for orchestration | Industry-standard, Python-native, supports complex DAG dependencies |

---

*For data-level details, see [data_dictionary.md](data_dictionary.md). For KPI definitions built on this architecture, see [kpi_dictionary.md](kpi_dictionary.md).*
