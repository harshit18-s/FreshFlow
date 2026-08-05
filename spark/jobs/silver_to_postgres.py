"""
FreshFlow AI — Silver to Postgres
=================================
Moves processed data from Silver (Spark) to Gold tables in PostgreSQL.
Currently acts as a bridge to push aggregated or filtered silver data to Postgres for visualization.

Usage:
    spark-submit spark/jobs/silver_to_postgres.py --table <table_name>
"""

import argparse
import logging
from pathlib import Path

from pyspark.sql import SparkSession

logger = logging.getLogger("silver_to_postgres")

def get_spark_session(app_name: str = "SilverToPostgres") -> SparkSession:
    return (
        SparkSession.builder
        .appName(app_name)
        .config("spark.sql.session.timeZone", "UTC")
        .getOrCreate()
    )

def process_sync(spark: SparkSession, table_name: str, db_url: str, db_props: dict) -> dict:
    # This is a stub for potential future use if silver tables are stored externally
    # Currently, our pipeline writes directly to postgres silver schema!
    logger.info(f"Syncing {table_name} to postgres (noop - already in PG)")
    return {"status": "success", "message": "Silver data is already in PostgreSQL in this architecture."}

def main():
    parser = argparse.ArgumentParser(description="Sync Silver to Postgres")
    parser.add_argument("--table", required=True)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    
    spark = get_spark_session()
    spark.stop()

if __name__ == "__main__":
    main()
