"""
FreshFlow AI — Stockout Incidents Builder
=========================================
Identifies contiguous stockout periods (incidents) from hourly data.

Pipeline steps:
1. Read silver.hourly_sales for a date range (or full table)
2. Filter to operational hours (06:00 - 22:00)
3. Detect state changes in stockout_flag (0 -> 1 or 1 -> 0)
4. Group contiguous 1s into incident rows
5. Calculate incident duration (hours) and lost_sales_impact
6. Write to silver.stockout_incidents

Usage:
    spark-submit spark/jobs/stockout_incidents.py
"""

import argparse
import logging
from pathlib import Path

from pyspark.sql import SparkSession, Window
from pyspark.sql import functions as F

logger = logging.getLogger("stockout_incidents")

def get_spark_session(app_name: str = "StockoutIncidents") -> SparkSession:
    return (
        SparkSession.builder
        .appName(app_name)
        .config("spark.sql.session.timeZone", "UTC")
        .getOrCreate()
    )

def process_incidents(spark: SparkSession, db_url: str, db_props: dict) -> dict:
    """Build stockout incidents from hourly data."""
    
    try:
        df_hourly = spark.read.jdbc(url=db_url, table="silver.hourly_sales", properties=db_props)
    except Exception as e:
        logger.error(f"Failed to read silver hourly: {e}")
        return {"status": "error", "message": str(e)}

    # We only care about operational hours for true business stockouts
    df_ops = df_hourly.filter(F.col("is_operational_hour") == True)
    
    # 1. Order by store, product, time
    window_spec = Window.partitionBy("store_id", "product_id").orderBy("event_timestamp")
    
    # 2. Find state changes (lag)
    df_lagged = df_ops.withColumn("prev_stockout", F.lag("stockout_flag").over(window_spec))
    
    # Fill nulls with 0 (assume first record wasn't stockout prior)
    df_lagged = df_lagged.fillna({"prev_stockout": 0})
    
    # 3. Create incident IDs (cumulative sum of state changes where it goes from 0 to 1)
    df_state_change = df_lagged.withColumn(
        "is_new_incident", 
        F.when((F.col("stockout_flag") == 1) & (F.col("prev_stockout") == 0), 1).otherwise(0)
    )
    
    df_incident_groups = df_state_change.withColumn(
        "incident_group", F.sum("is_new_incident").over(window_spec)
    )
    
    # 4. Filter only to the stockout hours, now they are grouped!
    df_stockouts = df_incident_groups.filter(F.col("stockout_flag") == 1)
    
    # 5. Aggregate by incident_group
    df_incidents = (
        df_stockouts
        .groupBy("store_id", "product_id", "incident_group")
        .agg(
            F.min("event_timestamp").alias("incident_start"),
            F.max("event_timestamp").alias("incident_end"),
            F.count("*").alias("duration_hours"),
            # We don't have true lost sales yet, but we can capture the average features during the incident
            F.mean("discount_depth").alias("avg_discount_during"),
            F.max("holiday_flag").alias("spans_holiday"),
            F.max("activity_flag").alias("spans_promotion"),
            F.first("event_date").alias("start_date")
        )
    )
    
    # Generate UUID for each incident
    df_final = df_incidents.withColumn("incident_id", F.expr("uuid()")).drop("incident_group")
    
    incident_count = df_final.count()
    logger.info(f"Generated {incident_count} stockout incidents")
    
    if incident_count > 0:
        # Overwrite the table (or append in a real incremental pipeline)
        # For simplicity in this demo, we overwrite the silver incidents table
        df_final.write.jdbc(
            url=db_url,
            table="silver.stockout_incidents",
            mode="overwrite",
            properties=db_props
        )

    return {
        "status": "success",
        "incident_count": incident_count
    }


def main():
    parser = argparse.ArgumentParser(description="Build Stockout Incidents")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    
    db_url = "jdbc:postgresql://postgres:5432/freshflow_db"
    db_props = {
        "user": "freshflow_etl",
        "password": "etl_dev_2026",
        "driver": "org.postgresql.Driver"
    }

    spark = get_spark_session()
    
    try:
        res = process_incidents(spark, db_url, db_props)
        logger.info(f"Pipeline finished: {res}")
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
