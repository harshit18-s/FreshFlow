import os
import logging
import shap
import pandas as pd
import psycopg2
import mlflow
import matplotlib.pyplot as plt

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

DB_USER = os.getenv("POSTGRES_USER", "freshflow_admin")
DB_PASS = os.getenv("POSTGRES_PASSWORD", "freshflow_dev_2026")
DB_HOST = os.getenv("POSTGRES_HOST", "freshflow-postgres")
DB_PORT = os.getenv("POSTGRES_PORT", "5432")
DB_NAME = os.getenv("POSTGRES_DB", "freshflow_db")
MLFLOW_DB = os.getenv("MLFLOW_DB", "sqlite:////opt/airflow/data/mlruns.db")

def load_latest_model():
    logger.info("Connecting to MLflow...")
    mlflow.set_tracking_uri(MLFLOW_DB)
    experiment = mlflow.get_experiment_by_name("freshflow_demand_forecasting")
    if not experiment:
        raise ValueError("Experiment 'freshflow_demand_forecasting' not found.")
        
    runs = mlflow.search_runs(
        experiment_ids=[experiment.experiment_id],
        order_by=["metrics.rmse ASC"],
        max_results=1
    )
    
    if runs.empty:
        raise ValueError("No trained models found.")
        
    best_run_id = runs.iloc[0].run_id
    model_uri = f"runs:/{best_run_id}/model"
    
    logger.info(f"Loading best model from {model_uri}...")
    model = mlflow.lightgbm.load_model(model_uri)
    return model

def load_sample_data():
    """Load sample data for SHAP explainability."""
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
        f.discount_factor,
        s.store_cluster,
        s.volume_band
    FROM gold_gold.fact_sales_hourly f
    JOIN gold_gold.dim_store s ON f.store_id = s.store_id
    LIMIT 1000;
    """
    logger.info("Extracting sample data for SHAP analysis...")
    df = pd.read_sql(query, conn)
    conn.close()
    return df

def preprocess_features(df):
    """Engineer features to match training schema."""
    categorical_cols = ['store_id', 'product_id', 'store_cluster', 'volume_band']
    for col in categorical_cols:
        df[col] = df[col].astype('category')
    
    df['date_key_str'] = df['date_key'].astype(str)
    df['year'] = df['date_key_str'].str[0:4].astype(int)
    df['month'] = df['date_key_str'].str[4:6].astype(int)
    df['day'] = df['date_key_str'].str[6:8].astype(int)
    df['hour'] = df['time_key'].astype(int)
    
    X = df.drop(columns=['date_key', 'date_key_str', 'time_key'])
    return X

def explain():
    logger.info("Starting SHAP explainability job.")
    model = load_latest_model()
    
    df = load_sample_data()
    X = preprocess_features(df)
    
    logger.info("Generating SHAP values...")
    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(X)
    
    output_dir = "/opt/airflow/reports"
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "standalone_shap_summary.png")
    
    plt.figure(figsize=(10, 8))
    shap.summary_plot(shap_values, X, show=False)
    plt.tight_layout()
    plt.savefig(output_path)
    plt.close()
    
    logger.info(f"SHAP summary plot saved to {output_path}.")

if __name__ == "__main__":
    explain()
