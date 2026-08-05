"""
FreshFlow AI - Data Ingestion & Medallion ETL Airflow DAG
Orchestrates Kaggle dataset download, Bronze ingestion, PySpark Silver transformations, and dbt Gold models.
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator

default_args = {
    'owner': 'freshflow',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

with DAG(
    'freshflow_etl_pipeline',
    default_args=default_args,
    description='Batch ETL pipeline for FreshFlow AI medallion architecture',
    schedule_interval='@daily',
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=['freshflow', 'etl', 'medallion', 'spark', 'dbt'],
) as dag:

    download_raw_data = BashOperator(
        task_id='download_raw_data',
        bash_command='python /opt/airflow/ingestion/download_dataset.py',
    )

    ingest_bronze = BashOperator(
        task_id='ingest_bronze',
        bash_command='python /opt/airflow/ingestion/batch_ingest.py',
    )

    spark_transform_silver = BashOperator(
        task_id='spark_transform_silver',
        bash_command='python /opt/airflow/spark/jobs/bronze_to_silver_daily.py',
    )

    spark_explode_hourly = BashOperator(
        task_id='spark_explode_hourly',
        bash_command='python /opt/airflow/spark/jobs/explode_hourly.py',
    )

    spark_detect_stockouts = BashOperator(
        task_id='spark_detect_stockouts',
        bash_command='python /opt/airflow/spark/jobs/stockout_incidents.py',
    )

    load_to_postgres = BashOperator(
        task_id='load_to_postgres',
        bash_command='python /opt/airflow/spark/jobs/silver_to_postgres.py',
    )

    dbt_run_gold = BashOperator(
        task_id='dbt_run_gold',
        bash_command='cd /opt/airflow/dbt && dbt run --profiles-dir .',
    )

    # Pipeline Dependency Graph
    download_raw_data >> ingest_bronze >> spark_transform_silver
    spark_transform_silver >> spark_explode_hourly >> load_to_postgres
    spark_transform_silver >> spark_detect_stockouts >> load_to_postgres
    load_to_postgres >> dbt_run_gold
