"""
FreshFlow AI - ML Retraining & Batch Scoring Airflow DAG
Automates periodic model training, MLflow logging, evaluation, SHAP analysis, and batch demand scoring.
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator

default_args = {
    'owner': 'freshflow',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=10),
}

with DAG(
    'freshflow_ml_pipeline',
    default_args=default_args,
    description='Automated ML model retraining and batch scoring pipeline',
    schedule_interval='@weekly',
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=['freshflow', 'ml', 'lightgbm', 'mlflow', 'scoring'],
) as dag:

    train_model = BashOperator(
        task_id='train_model',
        bash_command='python /opt/airflow/src/ml/train.py',
    )

    generate_explainability = BashOperator(
        task_id='generate_explainability',
        bash_command='python /opt/airflow/src/ml/explain.py',
    )

    run_batch_scoring = BashOperator(
        task_id='run_batch_scoring',
        bash_command='python /opt/airflow/src/ml/score.py',
    )

    # ML Pipeline Dependency Graph
    train_model >> generate_explainability >> run_batch_scoring
