import contextlib
import logging
import os

import lightgbm as lgb
import matplotlib.pyplot as plt
import mlflow
import mlflow.lightgbm
import numpy as np
import pandas as pd
import psycopg2
import shap
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Database and MLflow connection settings
DB_USER = os.getenv("POSTGRES_USER", "freshflow_admin")
DB_PASS = os.getenv("POSTGRES_PASSWORD", "freshflow_dev_2026")
DB_HOST = os.getenv("POSTGRES_HOST", "freshflow-postgres")
DB_PORT = os.getenv("POSTGRES_PORT", "5432")
DB_NAME = os.getenv("POSTGRES_DB", "freshflow_db")
MLFLOW_DB = os.getenv("MLFLOW_DB", "sqlite:///opt/airflow/data/mlruns.db")

def load_data():
    """Load data from Gold layer."""
    logger.info(f"Connecting to database at {DB_HOST}...")
    conn = psycopg2.connect(
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASS,
        host=DB_HOST,
        port=DB_PORT
    )

    query = """
    SELECT
        f.date_key,
        f.time_key,
        f.store_id,
        f.product_id,
        f.observed_sales,
        f.discount_factor,
        s.store_cluster,
        s.volume_band
    FROM gold_gold.fact_sales_hourly f
    JOIN gold_gold.dim_store s ON f.store_id = s.store_id
    WHERE f.observed_sales IS NOT NULL
    -- Scaled training data limit for higher model fidelity
    LIMIT 50000;
    """
    logger.info("Extracting data from gold.fact_sales_hourly...")
    df = pd.read_sql(query, conn)
    conn.close()
    logger.info(f"Extracted {len(df)} rows.")
    return df

def preprocess_features(df):
    """Engineer features and prepare for training."""
    logger.info("Engineering features...")
    # Convert categorical columns
    categorical_cols = ['store_id', 'product_id', 'store_cluster', 'volume_band']
    for col in categorical_cols:
        df[col] = df[col].astype('category')

    # Simple temporal features from date_key (YYYYMMDD) and time_key (hour)
    df['date_key_str'] = df['date_key'].astype(str)
    df['year'] = df['date_key_str'].str[0:4].astype(int)
    df['month'] = df['date_key_str'].str[4:6].astype(int)
    df['day'] = df['date_key_str'].str[6:8].astype(int)
    df['hour'] = df['time_key'].astype(int)

    # Target
    y = df['observed_sales']

    # Features
    X = df.drop(columns=['observed_sales', 'date_key', 'date_key_str', 'time_key'])

    return X, y

def train_model():
    """Train LightGBM model and log to MLflow."""
    df = load_data()
    X, y = preprocess_features(df)

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    logger.info("Connecting to MLflow...")
    mlflow.set_tracking_uri(MLFLOW_DB)
    with contextlib.suppress(Exception):
        mlflow.create_experiment("freshflow_demand_forecasting", artifact_location="/opt/airflow/data/mlruns")
    mlflow.set_experiment("freshflow_demand_forecasting")

    with mlflow.start_run():
        logger.info("Training LightGBM model...")
        mlflow.lightgbm.autolog()

        # Train model
        model = lgb.LGBMRegressor(
            n_estimators=100,
            learning_rate=0.1,
            max_depth=6,
            random_state=42,
            n_jobs=-1
        )
        model.fit(X_train, y_train, eval_set=[(X_test, y_test)], eval_metric="rmse")

        # Evaluate
        preds = model.predict(X_test)
        mae = mean_absolute_error(y_test, preds)
        rmse = np.sqrt(mean_squared_error(y_test, preds))
        r2 = r2_score(y_test, preds)
        sum_actual = np.sum(np.abs(y_test))
        wape = (np.sum(np.abs(y_test - preds)) / sum_actual * 100) if sum_actual > 0 else 0.0
        sum_y = np.sum(y_test)
        bias = (np.sum(preds - y_test) / sum_y * 100) if sum_y != 0 else 0.0

        logger.info(f"Metrics - MAE: {mae:.2f}, RMSE: {rmse:.2f}, R2: {r2:.2f}, WAPE: {wape:.2f}%, Bias: {bias:.2f}%")
        mlflow.log_metrics({"mae": mae, "rmse": rmse, "r2": r2, "wape": wape, "bias": bias})

        # Generate SHAP values for explainability
        logger.info("Generating SHAP values...")
        explainer = shap.TreeExplainer(model)
        # Use a sample for SHAP to avoid OOM
        shap_sample = X_test.sample(n=min(1000, len(X_test)), random_state=42)
        shap_values = explainer.shap_values(shap_sample)

        plt.figure(figsize=(10, 8))
        shap.summary_plot(shap_values, shap_sample, show=False)
        plt.tight_layout()
        plt.savefig("shap_summary.png")
        plt.close()

        mlflow.log_artifact("shap_summary.png")
        os.remove("shap_summary.png")

        logger.info("Training completed and logged to MLflow.")

if __name__ == "__main__":
    train_model()
