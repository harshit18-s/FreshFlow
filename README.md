<div align="center">

# 🥬 FreshFlow AI

### Stockout-Aware Retail Profit & Waste Control Tower

*Demand forecasting, waste prediction, and dynamic replenishment optimization for perishable goods.*

<!-- Badges -->
![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)
![Airflow](https://img.shields.io/badge/Apache%20Airflow-2.10-017CEE?logo=apache-airflow&logoColor=white)
![MLflow](https://img.shields.io/badge/MLflow-2.x-0194E2?logo=mlflow&logoColor=white)
![Spark](https://img.shields.io/badge/Apache%20Spark-3.5-E25A1C?logo=apache-spark&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?logo=postgresql&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green)

</div>

---

## 🎯 Problem Statement

Grocery retailers lose **$18.2 billion annually** to food waste while simultaneously experiencing stockouts that cost **$1 trillion globally**. FreshFlow AI builds a decision-intelligence platform that jointly optimises these competing objectives — reducing waste without increasing stockouts.

## 🏗️ Architecture

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                          FreshFlow AI Platform                              │
├──────────────┬──────────────┬──────────────┬──────────────┬────────────────┤
│   Ingestion  │  Processing  │   ML Engine  │   Serving    │  Monitoring    │
│              │              │              │              │                │
│  Kaggle API  │  PySpark     │  LightGBM    │  FastAPI     │  Prometheus    │
│  Airflow DAGs│  Delta Lake  │  CatBoost    │  Streamlit   │  Grafana       │
│  Batch/Stream│  dbt Models  │  MLflow      │  REST API    │  Alerting      │
│              │              │  SHAP        │              │                │
├──────────────┴──────────────┴──────────────┴──────────────┴────────────────┤
│                                                                            │
│   PostgreSQL  │  MinIO (S3)  │  Redpanda (Kafka)  │  Docker Compose       │
│   (Metadata)  │  (Data Lake) │  (Streaming)       │  (Orchestration)      │
└──────────────────────────────────────────────────────────────────────────────┘
```

## 📂 Project Structure

```
freshflow-ai/
├── config/                     # Configuration files
│   ├── environments/           #   Per-environment settings
│   ├── logging.yml             #   Structured logging config
│   └── prometheus/             #   Prometheus scrape config
├── dags/                       # Airflow DAG definitions
├── data/                       # Data directory (gitignored)
│   ├── raw/                    #   Original downloads
│   ├── bronze/                 #   Raw ingested (append-only)
│   ├── silver/                 #   Cleaned & validated
│   ├── gold/                   #   Business-ready aggregates
│   ├── sample/                 #   Dev/test samples
│   └── quarantine/             #   Failed quality checks
├── dbt/                        # dbt models & tests
├── docker/                     # Dockerfiles
├── ingestion/                  # Data download & ingestion scripts
├── jobs/                       # Spark job scripts
├── models/                     # Trained model artifacts
├── plugins/                    # Airflow plugins
├── reports/                    # Generated reports & plots
├── requirements/               # Python dependency files
│   ├── base.txt                #   Core dependencies
│   ├── data.txt                #   Data pipeline deps
│   ├── ml.txt                  #   ML/modelling deps
│   └── dev.txt                 #   Development & testing
├── scripts/                    # Utility scripts
│   └── bootstrap.ps1           #   Windows setup script
├── src/                        # Application source code
│   ├── api/                    #   FastAPI application
│   ├── ingestion/              #   Ingestion modules
│   ├── ml/                     #   ML training & scoring
│   └── utils/                  #   Shared utilities
├── tests/                      # Test suite
│   ├── unit/
│   ├── integration/
│   ├── data/
│   ├── ml/
│   └── e2e/
├── docker-compose.yml          # Multi-profile Docker Compose
├── Makefile                    # Task runner
├── pyproject.toml              # Python project config
└── README.md                   # You are here
```

## 🚀 Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/freshflow-ai/freshflow-ai.git
cd freshflow-ai

# 2. Bootstrap (creates .env, installs deps, starts Docker)
.\scripts\bootstrap.ps1          # Windows (PowerShell)
# make bootstrap                 # Linux / macOS

# 3. Run the full demo pipeline
make demo
```

## 📋 Prerequisites

| Tool | Version | Required |
|------|---------|----------|
| **Python** | ≥ 3.10 | ✅ |
| **Docker Desktop** | ≥ 24.0 | ✅ |
| **Docker Compose** | ≥ 2.20 (v2 plugin) | ✅ |
| **GNU Make** | ≥ 4.0 | ✅ (`choco install make` on Windows) |
| **Git** | ≥ 2.40 | ✅ |
| **RAM** | ≥ 15 GB | ✅ (for all profiles) |
| **Disk** | ≥ 20 GB free | ✅ |

## 🔧 Full Setup Instructions

### 1. Environment Configuration

```powershell
# Copy the environment template
Copy-Item .env.example .env

# Edit .env with your credentials (defaults work for local dev)
notepad .env
```

### 2. Start Services

```bash
# Core services only (Postgres, MinIO, Airflow, MLflow, FastAPI)
make up-core

# Add Spark cluster
make up-bigdata

# Add streaming (Redpanda)
make up-streaming

# Add monitoring (Prometheus + Grafana)
make up-monitoring

# Everything at once
make up-all
```

### 3. Verify Services

| Service | URL | Credentials |
|---------|-----|-------------|
| Airflow | [localhost:8080](http://localhost:8080) | admin / admin |
| MLflow | [localhost:5000](http://localhost:5000) | — |
| FastAPI Docs | [localhost:8000/docs](http://localhost:8000/docs) | — |
| MinIO Console | [localhost:9001](http://localhost:9001) | freshflow_minio / freshflow_minio_secret |
| Spark Master | [localhost:8081](http://localhost:8081) | — |
| Redpanda Console | [localhost:8082](http://localhost:8082) | — |
| Grafana | [localhost:3000](http://localhost:3000) | admin / admin |
| Prometheus | [localhost:9090](http://localhost:9090) | — |

### 4. Run the Pipeline

```bash
make download-data   # Fetch dataset
make ingest          # Bronze layer ingestion
make transform       # Spark: bronze → silver → gold
make dbt-build       # dbt models & tests
make train           # Train ML models
make score           # Batch scoring
```

## 📊 Memory Budget (15 GB Total)

| Profile | Service | Memory Limit |
|---------|---------|-------------|
| core | PostgreSQL | 512 MB |
| core | MinIO | 256 MB |
| core | Airflow Webserver | 512 MB |
| core | Airflow Scheduler | 512 MB |
| core | Airflow Triggerer | 256 MB |
| core | MLflow | 256 MB |
| core | FastAPI | 256 MB |
| bigdata | Spark Master | 1 GB |
| bigdata | Spark Worker | 2 GB |
| streaming | Redpanda | 512 MB |
| streaming | Redpanda Console | 128 MB |
| monitoring | Prometheus | 256 MB |
| monitoring | Grafana | 256 MB |
| | **Total (all profiles)** | **~5.7 GB** |

> 💡 Remaining ~9 GB is available for the OS, Python processes, and ML training.

## 🗺️ Project Phases

| Phase | Focus | Status |
|-------|-------|--------|
| **Phase 1** | Infrastructure & project setup | 🟢 Complete |
| **Phase 2** | Data ingestion & medallion architecture | 🟢 Complete |
| **Phase 3** | Feature engineering & dbt models | 🟢 Complete |
| **Phase 4** | ML model training & experiment tracking | 🟢 Complete |
| **Phase 5** | API serving & Streamlit dashboard | 🟢 Complete |
| **Phase 6** | Monitoring, alerting & DAG orchestration | 🟢 Complete |

## 📦 Dataset

This project uses the **Supermarket Sales & Waste Dataset** by Dingdong-Inc.

- **Source**: [Kaggle](https://www.kaggle.com/datasets/)
- **License**: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)
- **Attribution**: © Dingdong-Inc — shared under Creative Commons Attribution 4.0 International License

> The dataset is not included in this repository. Run `make download-data` to fetch it.

## 🧪 Testing

```bash
make test             # All tests
make test-unit        # Unit tests only
make test-integration # Integration tests (requires Docker)
make test-data        # Data quality tests
make test-ml          # ML model tests
make test-e2e         # End-to-end pipeline tests
make test-cov         # With coverage report
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Commit changes: `git commit -m 'Add amazing feature'`
4. Push to branch: `git push origin feature/amazing-feature`
5. Open a Pull Request

## 📄 License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.

---

<div align="center">

**Built with ❤️ for smarter grocery retail**

</div>
#   F r e s h F l o w  
 