from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator

default_args = {
    'owner': 'freshflow',
    'depends_on_past': False,
    'start_date': datetime(2026, 1, 1),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

with DAG(
    'freshflow_ingestion_dag',
    default_args=default_args,
    description='Downloads and ingests raw dataset to Bronze',
    schedule_interval='@daily',
    catchup=False,
) as dag:

    # 1. Download Dataset (uses huggingface_hub)
    # Using sample size 1000 to keep it manageable in demo mode
    download_task = BashOperator(
        task_id='download_dataset',
        bash_command='python /opt/airflow/ingestion/download_dataset.py --sample 1000'
    )

    # 2. Batch Ingest to Bronze
    batch_ingest_task = BashOperator(
        task_id='batch_ingest',
        bash_command='python /opt/airflow/ingestion/batch_ingest.py'
    )

    download_task >> batch_ingest_task
