"""
FreshFlow AI — Bronze to Silver Daily
=====================================
Validates and cleans Bronze daily records and writes them to Silver.

Pipeline steps:
1. Read Bronze parquet partitions for a specific ingestion_date
2. Cast identifiers and parse dates
3. Apply data contract validation (e.g., arrays must be length 24)
4. Deduplicate on natural key (store_id, product_id, dt)
5. Quarantine malformed records to silver.quarantine
6. Write clean records to silver.daily_sales in PostgreSQL

Usage:
    spark-submit spark/jobs/bronze_to_silver_daily.py --date 2026-07-21
"""

import argparse
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import (
    StructType, StructField, StringType, IntegerType, DoubleType, ArrayType
)

logger = logging.getLogger("bronze_to_silver")

def get_spark_session(app_name: str = "BronzeToSilverDaily") -> SparkSession:
    """Initialize Spark session."""
    return (
        SparkSession.builder
        .appName(app_name)
        .config("spark.sql.session.timeZone", "UTC")
        .config("spark.sql.parquet.datetimeRebaseModeInWrite", "CORRECTED")
        .getOrCreate()
    )

def process_daily(spark: SparkSession, ingestion_date: str, data_dir: Path, db_url: str, db_props: dict) -> dict:
    """Read bronze, validate, and write to silver database."""
    bronze_path = str(data_dir / "bronze" / "freshretail" / "source_split=*" / f"ingestion_date={ingestion_date}")
    
    try:
        df = spark.read.parquet(bronze_path)
    except Exception as e:
        logger.error(f"Failed to read bronze data for {ingestion_date}: {e}")
        return {"status": "error", "message": "No data found"}
        
    initial_count = df.count()
    if initial_count == 0:
        return {"status": "skipped", "message": "Zero records"}

    logger.info(f"Loaded {initial_count} records from Bronze")

    # 1. Deduplicate by primary key, keeping latest ingested_at
    # If ingested_at is the same, use source_file_hash to be deterministic
    window_spec = F.expr("row_number() over (partition by store_id, product_id, dt order by ingested_at desc, source_file_hash desc)")
    df_dedup = df.withColumn("rn", window_spec).filter("rn = 1").drop("rn")

    # 2. Add validation flags
    # We check if arrays have exactly 24 elements, and sale_amount is non-negative
    df_validated = (
        df_dedup
        .withColumn("is_valid", 
            (F.size("hours_sale") == 24) & 
            (F.size("hours_stock_status") == 24) & 
            (F.col("sale_amount") >= 0)
        )
    )

    # 3. Split into valid and quarantine
    df_clean = df_validated.filter("is_valid = True").drop("is_valid")
    df_quarantine = df_validated.filter("is_valid = False").drop("is_valid")

    clean_count = df_clean.count()
    quarantine_count = df_quarantine.count()

    logger.info(f"Clean records: {clean_count}, Quarantined: {quarantine_count}")

    # 4. Write Quarantine to JSON or Postgres
    # In a real system, we'd write to the silver.quarantine table.
    # For now, we serialize the row to JSON and write.
    if quarantine_count > 0:
        quarantine_df = df_quarantine.select(
            F.to_json(F.struct("*")).alias("source_record"),
            F.lit("VALIDATION_FAILED").alias("error_code"),
            F.lit("Array length != 24 or negative sales").alias("error_message"),
            F.col("ingestion_batch_id").alias("batch_id")
        ).withColumn("detected_at", F.current_timestamp())

        quarantine_df.write.jdbc(
            url=db_url,
            table="silver.quarantine",
            mode="append",
            properties=db_props
        )

    # 5. Write Clean to Silver Daily
    if clean_count > 0:
        # PostgreSQL doesn't natively accept Spark arrays into JSONB without a cast.
        # We convert arrays to JSON strings in Spark, then we can let PG handle it.
        df_write = (
            df_clean
            .withColumn("hours_sale", F.to_json("hours_sale"))
            .withColumn("hours_stock_status", F.to_json("hours_stock_status"))
            .withColumn("dt", F.to_date("dt"))
        )
        
        # Write to Postgres silver.daily_sales
        df_write.write.jdbc(
            url=db_url,
            table="silver.daily_sales",
            mode="append",
            properties=db_props
        )

    return {
        "status": "success", 
        "initial": initial_count,
        "clean": clean_count,
        "quarantined": quarantine_count
    }


def main():
    parser = argparse.ArgumentParser(description="Bronze to Silver Daily ETL")
    parser.add_argument("--date", required=True, help="Ingestion date YYYY-MM-DD")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    
    # In production, these come from environment variables or Airflow connections
    db_url = "jdbc:postgresql://postgres:5432/freshflow_db"
    db_props = {
        "user": "freshflow_etl",
        "password": "etl_dev_2026",
        "driver": "org.postgresql.Driver"
    }
    
    data_dir = Path("/app/data") if Path("/app/data").exists() else Path("../../data").resolve()

    spark = get_spark_session()
    
    try:
        res = process_daily(spark, args.date, data_dir, db_url, db_props)
        logger.info(f"Pipeline finished: {res}")
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
