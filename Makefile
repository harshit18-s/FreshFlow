# ============================================================================
# FreshFlow AI — Makefile
# ============================================================================
# Usage:
#   make bootstrap          # First-time setup
#   make up-core            # Start core services
#   make up-all             # Start everything
#   make demo               # Run full pipeline end-to-end
#
# On Windows with PowerShell, use:
#   make -f Makefile <target>   (requires GNU Make for Windows / choco install make)
# ============================================================================

.DEFAULT_GOAL := help
SHELL := /bin/bash

# --- Variables ---------------------------------------------------------------
COMPOSE        := docker compose
PYTHON         := python
PYTEST         := pytest
DBT            := dbt
SPARK_SUBMIT   := spark-submit

PROFILES_CORE       := --profile core
PROFILES_BIGDATA    := --profile bigdata
PROFILES_STREAMING  := --profile streaming
PROFILES_MONITORING := --profile monitoring
PROFILES_ALL        := $(PROFILES_CORE) $(PROFILES_BIGDATA) $(PROFILES_STREAMING) $(PROFILES_MONITORING)

# --- Help --------------------------------------------------------------------
.PHONY: help
help: ## Show this help message
	@echo ""
	@echo "  FreshFlow AI — Available Targets"
	@echo "  ================================"
	@grep -E '^[a-zA-Z_-]+:.*##' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*##"}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
	@echo ""

# =============================================================================
# Bootstrap & Setup
# =============================================================================

.PHONY: bootstrap
bootstrap: ## First-time project setup (env, dirs, deps, services)
	@echo "▸ Copying .env.example → .env (if missing)..."
	@test -f .env || cp .env.example .env
	@echo "▸ Creating data directories..."
	@mkdir -p data/{raw,bronze,silver,gold,sample,quarantine}
	@mkdir -p dags plugins logs models reports
	@echo "▸ Installing Python dependencies..."
	pip install -r requirements/dev.txt
	@echo "▸ Starting core Docker services..."
	$(COMPOSE) $(PROFILES_CORE) up -d
	@echo ""
	@echo "✓ Bootstrap complete. Run 'make ps' to check service status."

.PHONY: init-dirs
init-dirs: ## Create all project directories
	@mkdir -p data/{raw,bronze,silver,gold,sample,quarantine}
	@mkdir -p dags plugins logs models reports
	@mkdir -p config/prometheus config/environments

# =============================================================================
# Docker Compose — Lifecycle
# =============================================================================

.PHONY: up-core
up-core: ## Start core services (Postgres, MinIO, Airflow, MLflow, FastAPI)
	$(COMPOSE) $(PROFILES_CORE) up -d

.PHONY: up-bigdata
up-bigdata: ## Start Spark cluster
	$(COMPOSE) $(PROFILES_BIGDATA) up -d

.PHONY: up-streaming
up-streaming: ## Start Redpanda (Kafka-compatible)
	$(COMPOSE) $(PROFILES_STREAMING) up -d

.PHONY: up-monitoring
up-monitoring: ## Start Prometheus + Grafana
	$(COMPOSE) $(PROFILES_MONITORING) up -d

.PHONY: up-all
up-all: ## Start ALL profiles
	$(COMPOSE) $(PROFILES_ALL) up -d

.PHONY: down
down: ## Stop and remove all containers
	$(COMPOSE) $(PROFILES_ALL) down

.PHONY: down-volumes
down-volumes: ## Stop containers and DELETE volumes (⚠ destructive)
	$(COMPOSE) $(PROFILES_ALL) down -v

.PHONY: restart
restart: down up-core ## Restart core services

.PHONY: ps
ps: ## Show running containers
	$(COMPOSE) $(PROFILES_ALL) ps

.PHONY: logs
logs: ## Tail logs from all services
	$(COMPOSE) $(PROFILES_ALL) logs -f --tail=100

.PHONY: logs-core
logs-core: ## Tail logs from core services only
	$(COMPOSE) $(PROFILES_CORE) logs -f --tail=100

# =============================================================================
# Data Pipeline
# =============================================================================

.PHONY: download-data
download-data: ## Download dataset from source
	$(PYTHON) ingestion/download_dataset.py

.PHONY: ingest
ingest: ## Run batch ingestion pipeline
	$(PYTHON) ingestion/batch_ingest.py

.PHONY: transform
transform: ## Run Spark transformations (bronze → silver)
	docker exec --user root freshflow-spark-master spark-submit \
		--packages org.postgresql:postgresql:42.6.0 \
		--master spark://spark-master:7077 \
		/app/spark/jobs/bronze_to_silver_daily.py --date all
	docker exec --user root freshflow-spark-master spark-submit \
		--packages org.postgresql:postgresql:42.6.0 \
		--master spark://spark-master:7077 \
		/app/spark/jobs/explode_hourly.py --date all
	docker exec --user root freshflow-spark-master spark-submit \
		--packages org.postgresql:postgresql:42.6.0 \
		--master spark://spark-master:7077 \
		/app/spark/jobs/stockout_incidents.py

.PHONY: dbt-build
dbt-build: ## Run dbt build (models + tests)
	docker run --rm --network freshflow-net -v "$$(pwd)/dbt:/usr/app" -v "$$(pwd)/dbt/profiles.yml:/root/.dbt/profiles.yml" ghcr.io/dbt-labs/dbt-postgres:1.7.latest build --profiles-dir /usr/app

.PHONY: dbt-docs
dbt-docs: ## Generate and serve dbt docs
	cd dbt && $(DBT) docs generate --profiles-dir . && $(DBT) docs serve --profiles-dir .

# =============================================================================
# ML Pipeline
# =============================================================================

.PHONY: train
train: ## Train ML models
	docker cp "src/" freshflow-airflow-webserver:/opt/airflow/src
	docker cp "run_train.sh" freshflow-airflow-webserver:/opt/airflow/run_train.sh
	docker exec --user root freshflow-airflow-webserver bash -c "apt-get update && apt-get install -y libgomp1 && chown -R airflow:root /opt/airflow/src /opt/airflow/run_train.sh"
	docker exec freshflow-airflow-webserver bash -c "cd /opt/airflow && bash run_train.sh"

.PHONY: score
score: ## Run batch scoring
	docker exec freshflow-airflow-webserver bash -c "cd /opt/airflow && python -m src.ml.score"

.PHONY: serve
serve: ## Start API and Dashboard services
	docker compose --profile core up -d api dashboard

.PHONY: explain
explain: ## Generate SHAP explanations
	$(PYTHON) -m src.ml.explain

# =============================================================================
# Testing
# =============================================================================

.PHONY: test
test: ## Run all tests
	$(PYTEST) tests/ -v --tb=short

.PHONY: test-unit
test-unit: ## Run unit tests only
	$(PYTEST) tests/unit/ -v --tb=short

.PHONY: test-integration
test-integration: ## Run integration tests
	$(PYTEST) tests/integration/ -v --tb=short

.PHONY: test-data
test-data: ## Run data quality tests
	$(PYTEST) tests/data/ -v --tb=short

.PHONY: test-ml
test-ml: ## Run ML model tests
	$(PYTEST) tests/ml/ -v --tb=short

.PHONY: test-e2e
test-e2e: ## Run end-to-end pipeline tests
	$(PYTEST) tests/e2e/ -v --tb=short

.PHONY: test-cov
test-cov: ## Run tests with coverage report
	$(PYTEST) tests/ -v --cov=src --cov-report=html --cov-report=term-missing

# =============================================================================
# Quality & Formatting
# =============================================================================

.PHONY: lint
lint: ## Run ruff linter
	ruff check src/ tests/

.PHONY: format
format: ## Auto-format code with black + ruff
	black src/ tests/
	ruff check --fix src/ tests/

.PHONY: typecheck
typecheck: ## Run mypy type checks
	mypy src/

# =============================================================================
# Demo & End-to-End
# =============================================================================

.PHONY: demo
demo: up-all download-data ingest transform dbt-build train score ## Full pipeline demo (download → ingest → transform → dbt → train → score)
	@echo ""
	@echo "✓ FreshFlow AI demo pipeline complete."
	@echo "  → Airflow:  http://localhost:8080"
	@echo "  → MLflow:   http://localhost:5000"
	@echo "  → FastAPI:  http://localhost:8000/docs"
	@echo "  → MinIO:    http://localhost:9001"

# =============================================================================
# Cleanup
# =============================================================================

.PHONY: clean
clean: ## Remove generated data and caches
	rm -rf data/bronze/* data/silver/* data/gold/*
	rm -rf models/*.pkl models/*.joblib
	rm -rf reports/*
	rm -rf .pytest_cache .mypy_cache .ruff_cache
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

.PHONY: clean-all
clean-all: clean down-volumes ## Remove everything (data, volumes, caches) ⚠ destructive
	rm -rf logs/*
