# 🥬 FreshFlow AI — Stockout-Aware Retail Profit & Waste Control Tower

[![Python 3.11](https://img.shields.io/badge/Python-3.11-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.30+-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white)](https://streamlit.io/)
[![LightGBM](https://img.shields.io/badge/LightGBM-ML-GREEN?style=for-the-badge&logo=xgboost&logoColor=white)](https://lightgbm.readthedocs.io/)
[![Apache Spark](https://img.shields.io/badge/Apache%20Spark-3.5-E25A1C?style=for-the-badge&logo=apache-spark&logoColor=white)](https://spark.apache.org/)
[![Apache Airflow](https://img.shields.io/badge/Apache%20Airflow-2.10-017CEE?style=for-the-badge&logo=apache-airflow&logoColor=white)](https://airflow.apache.org/)
[![MLflow](https://img.shields.io/badge/MLflow-2.16-0194E2?style=for-the-badge&logo=mlflow&logoColor=white)](https://mlflow.org/)
[![Docker Compose](https://img.shields.io/badge/Docker%20Compose-v2-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://www.docker.com/)
[![License MIT](https://img.shields.io/badge/License-MIT-blue?style=for-the-badge)](LICENSE)

> **Predictive demand intelligence, Newsvendor inventory optimization, and perishable food waste prevention for enterprise grocery retail.**

---

## 📌 Executive Summary

Grocery supermarket chains lose over **$18.2 billion annually** to expired produce dumpsters while simultaneously suffering **$1 trillion in global lost sales** due to out-of-stock shelves. 

**FreshFlow AI** resolves this core tension by uniting **LightGBM gradient-boosted demand forecasting** with **Newsvendor Critical Fractile inventory optimization**. Rather than over-ordering to prevent stockouts or under-ordering to limit rot, FreshFlow AI calculates mathematically optimal daily order quantities ($Q^*$) tailored to store cluster volume, SKU perishability, and dynamic underage/overage cost ratios.

```
                  ┌──────────────────────────────────────────────┐
                  │        Newsvendor Optimization Math          │
                  │                                              │
                  │     Underage Cost:  Cu = (Price - Cost) + P  │
                  │     Overage Cost:   Co = (Cost + Hold - Salv)│
                  │     Critical Frac:  CF =  Cu / (Cu + Co)     │
                  │     Optimal Order:  Q* =  μ + Z × σ          │
                  └──────────────────────────────────────────────┘
```

---

## ✨ Key System Features

| Feature Component | Technology | Capability & Business Value |
| :--- | :--- | :--- |
| **Enterprise Cockpit** | Streamlit + Custom Dark CSS | 4-tab decision-support dashboard featuring dynamic store/SKU selectors, real-time demand spline plots, and ROI metrics. |
| **Newsvendor Optimizer** | SciPy + NumPy | Solves optimal order quantity ($Q^*$), expected net profit, spoilage risk score (%), and critical fractile thresholds. |
| **Demand Forecasting** | LightGBM + MLflow | Trains on 4.85M transaction records (FreshRetailNet-50K), tracking RMSE, WAPE, Bias, and SHAP explainability. |
| **Serving Layer** | FastAPI + Uvicorn | High-throughput REST API serving `/predict`, `/optimize-order`, `/health`, and `/reload-model` hot-reload endpoints. |
| **Medallion Pipeline** | PySpark + Delta / PostgreSQL | Bronze (raw append-only), Silver (24-hour array explode & stockout incident detector), Gold (star schema warehouse). |
| **MLOps & Monitoring** | Airflow + PSI Monitoring | Scheduled weekly model retraining DAGs, Population Stability Index (PSI) data drift shield, and automated logging. |

---

## 🏗️ System Architecture

```
                                  ┌──────────────────────────────────────────────────┐
                                  │            FreshFlow AI Architecture             │
                                  └──────────────────────────────────────────────────┘
                                                           │
        ┌──────────────────────────────────────────────────┼──────────────────────────────────────────────────┐
        │                                                  │                                                  │
 ┌──────────────┐                                   ┌──────────────┐                                   ┌──────────────┐
 │ Data Ingest  │                                   │ Medallion    │                                   │ ML & Serving │
 │              │                                   │ Lakehouse    │                                   │              │
 │ • HuggingFace│ ── Bronze (Raw Parquet) ────────> │ • PySpark    │ ── Gold (Fact/Dim Tables) ─────>  │ • LightGBM   │
 │ • Kaggle API │ ── Silver (24h Exploded Arrays) ─> │ • Postgres   │                                   │ • MLflow     │
 │ • Airflow DAG│ ── Quarantine (Malformed Rows) ─> │ • MinIO (S3) │                                   │ • FastAPI    │
 └──────────────┘                                   └──────────────┘                                   └──────────────┘
                                                           │                                                  │
                                                           ▼                                                  ▼
                                            ┌──────────────────────────────┐                   ┌──────────────────────────────┐
                                            │ Streamlit Enterprise Cockpit │                   │ Monitoring & Alerts          │
                                            │ • 🛒 Store Order Assistant   │                   │ • PSI & KS Drift Shield      │
                                            │ • 💰 ROI & Waste Prevented   │                   │ • Prometheus & Grafana       │
                                            │ • 🏷️ Clearance Assistant     │                   │ • SHAP Feature Attribution   │
                                            │ • ⚙️ System Status Controls  │                   └──────────────────────────────┘
                                            └──────────────────────────────┘
```

---

## 📁 Repository Structure

```
freshflow-ai/
├── config/                     # Configuration files & data contracts
│   ├── data_contracts/         #   YAML schema contracts for Bronze/Silver/Gold
│   ├── simulation/             #   Economic & perishable policy configs
│   ├── logging.yml             #   Structured JSON logging configuration
│   └── project.yml             #   Master platform settings
├── dags/                       # Apache Airflow orchestration DAGs
│   ├── freshflow_etl_dag.py    #   Daily Medallion ETL pipeline
│   └── freshflow_ml_dag.py     #   Weekly ML retraining & scoring pipeline
├── data/                       # Local data storage (gitignored)
│   ├── raw/                    #   FreshRetailNet-50K raw Parquet files
│   ├── bronze/                 #   Audited append-only raw layer
│   ├── silver/                 #   Cleaned, exploded hourly records
│   └── gold/                   #   Dimensional star-schema warehouse
├── dbt/                        # dbt transformations & quality tests
├── docker-compose.yml          # Multi-profile container orchestration
├── Makefile                    # Platform command automation matrix
├── pyproject.toml              # Unified project dependencies & ruff rules
├── src/                        # Platform core source code
│   ├── api/                    #   FastAPI serving REST endpoints
│   ├── dashboard/              #   Streamlit 4-tab Enterprise Cockpit
│   ├── ingestion/              #   Dataset downloaders & batch profilers
│   └── ml/                     #   LightGBM training, Newsvendor math, PSI drift
└── tests/                      # Automated test suite
    └── unit/                   #   Fast unit tests (API, optimizer, ingestion)
```

---

## ⚡ Quick Start Guide

### 1. Clone & Setup Repository

```bash
# Clone the repository
git clone https://github.com/harshit18-s/FreshFlow.git
cd FreshFlow

# Create virtual environment and install dependencies
python -m venv venv
# On Windows:
.\venv\Scripts\Activate.ps1
# On Linux/macOS:
source venv/bin/activate

pip install -r requirements/dev.txt
```

### 2. Launch Local Servers (Development Mode)

```bash
# Launch FastAPI REST API Engine on port 8000
uvicorn src.api.main:app --host 0.0.0.0 --port 8000 &

# Launch Streamlit Enterprise Cockpit on port 8501
streamlit run src/dashboard/app.py --server.port 8501
```

Access the live cockpit interface at **[http://localhost:8501](http://localhost:8501)**.

### 3. Run via Docker Compose (Multi-Profile Container Stack)

```bash
# Copy environment configuration
cp .env.example .env

# Launch core services (PostgreSQL, MinIO, MLflow, Airflow, FastAPI, Dashboard)
docker compose --profile core up -d

# Launch full ecosystem including Spark Master/Worker & Redpanda Kafka
docker compose --profile core --profile bigdata --profile streaming up -d
```

---

## 🌐 Service Access Endpoints

| Component | Endpoint / URL | Default Credentials | Status Check |
| :--- | :--- | :--- | :--- |
| **Streamlit Cockpit** | [http://localhost:8501](http://localhost:8501) | — | Live UI |
| **FastAPI REST API** | [http://localhost:8000/docs](http://localhost:8000/docs) | — | `GET /health` |
| **MLflow Server** | [http://localhost:5000](http://localhost:5000) | — | Metrics & Artifacts |
| **Airflow Webserver** | [http://localhost:8080](http://localhost:8080) | `admin` / `admin` | DAG Orchestrator |
| **MinIO Object Store** | [http://localhost:9001](http://localhost:9001) | `freshflow_minio` / `freshflow_minio_2026` | S3 Buckets |
| **Spark Master UI** | [http://localhost:8081](http://localhost:8081) | — | Spark Cluster Status |
| **Redpanda Console** | [http://localhost:8082](http://localhost:8082) | — | Kafka Streaming Topics |

---

## 🧪 Testing & Verification

Run the full automated pytest suite:

```bash
# Execute unit tests
pytest tests/unit/ -v

# Check Python static compilation
python -m py_compile src/dashboard/app.py src/api/main.py src/ml/train.py

# Run ruff code quality linter
ruff check src/ tests/
```

---

## 📦 Dataset & Attribution

This platform is benchmarked on the **FreshRetailNet-50K Dataset** provided by **Dingdong-Inc**:
- **Scale**: 4.85 Million rows, 898 store locations, 865 perishable SKUs.
- **License**: [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).

---

## 📄 License

Distributed under the **MIT License**. See [`LICENSE`](LICENSE) for complete licensing terms.