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
    'freshflow_transform_dag',
    default_args=default_args,
    description='Transforms Bronze data to Silver using PySpark',
    schedule_interval='@daily',
    catchup=False,
) as dag:

    # Pass today's date dynamically using Airflow macros
    # ds = YYYY-MM-DD
    target_date = "{{ ds }}"

    # 1. Bronze to Silver Daily
    bronze_to_silver = BashOperator(
        task_id='bronze_to_silver_daily',
        bash_command=f'spark-submit /opt/airflow/spark/jobs/bronze_to_silver_daily.py --date {target_date}'
    )

    # 2. Explode Hourly
    explode_hourly = BashOperator(
        task_id='explode_hourly',
        bash_command=f'spark-submit /opt/airflow/spark/jobs/explode_hourly.py --date {target_date}'
    )

    # 3. Stockout Incidents
    # This job reads the full hourly table or handles state tracking across days
    # In a production setting it would be incremental, but we'll run it as a full pass for simplicity
    stockout_incidents = BashOperator(
        task_id='stockout_incidents',
        bash_command='spark-submit /opt/airflow/spark/jobs/stockout_incidents.py'
    )

    bronze_to_silver >> explode_hourly >> stockout_incidents
