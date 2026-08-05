-- ============================================================================
-- FreshFlow AI — PostgreSQL Initialization
-- ============================================================================
-- This script runs on first container start to create additional databases
-- needed by Airflow and MLflow.
-- ============================================================================

-- Create database for MLflow metadata
SELECT 'CREATE DATABASE mlflow'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'mlflow')\gexec

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE mlflow TO freshflow_admin;
