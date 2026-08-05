"""
FreshFlow AI — Explode Hourly
=============================
Explodes the 24-element daily arrays into individual hourly event rows.

Pipeline steps:
1. Read silver.daily_sales
2. Explode the hours_sale and hours_stock_status arrays
3. Join with dim_time to calculate is_operational_hour and part_of_day
4. Write to silver.hourly_sales (expanding 4.85M daily rows to ~116M hourly rows)

Usage:
    spark-submit spark/jobs/explode_hourly.py --date 2026-07-21
"""

import argparse
import logging
from pathlib import Path

from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import ArrayType, DoubleType, IntegerType

logger = logging.getLogger("explode_hourly")

def get_spark_session(app_name: str = "ExplodeHourly") -> SparkSession:
    return (
        SparkSession.builder
        .appName(app_name)
        .config("spark.sql.session.timeZone", "UTC")
        .getOrCreate()
    )

def process_hourly(spark: SparkSession, target_date: str, db_url: str, db_props: dict) -> dict:
    """Read daily silver, explode to hourly, and write to silver hourly."""
    
    # In production, we pushdown the date filter to the database
    if target_date.lower() == "all":
        query = "(SELECT * FROM silver.daily_sales) AS daily"
    else:
        query = f"(SELECT * FROM silver.daily_sales WHERE dt = '{target_date}') AS daily"
    
    try:
        df_daily = spark.read.jdbc(url=db_url, table=query, properties=db_props)
    except Exception as e:
        logger.error(f"Failed to read silver daily for {target_date}: {e}")
        return {"status": "error", "message": str(e)}

    initial_count = df_daily.count()
    if initial_count == 0:
        return {"status": "skipped", "message": "Zero daily records"}
        
    logger.info(f"Exploding {initial_count} daily records for {target_date}")

    # The JSON columns come in as strings. We need to parse them to arrays.
    df_parsed = (
        df_daily
        .withColumn("hours_sale_arr", F.from_json("hours_sale", ArrayType(DoubleType())))
        .withColumn("hours_stock_arr", F.from_json("hours_stock_status", ArrayType(IntegerType())))
    )

    # Explode using posexplode to get the index (hour 0-23)
    # Since both arrays are exactly length 24, we can posexplode one, and extract from the other
    df_exploded = (
        df_parsed
        .select(
            "store_id", "product_id", "dt", "city_id",
            "discount", "holiday_flag", "activity_flag", "precpt", 
            "avg_temperature", "avg_humidity", "avg_wind_level",
            "source_split", "source_file", "ingestion_batch_id", "ingested_at",
            F.posexplode("hours_sale_arr").alias("hour_of_day", "observed_sales"),
            "hours_stock_arr"
        )
    )

    # Extract the corresponding stock status using the hour index
    df_hourly = (
        df_exploded
        .withColumn("stockout_flag", F.expr("hours_stock_arr[hour_of_day]"))
        .drop("hours_stock_arr")
    )

    # Calculate timestamps and time dimensions
    df_hourly_enhanced = (
        df_hourly
        .withColumn("event_date", F.col("dt"))
        .withColumn("event_timestamp", F.expr("timestamp(dt) + make_interval(0,0,0,0, hour_of_day, 0, 0)"))
        .withColumn("is_operational_hour", (F.col("hour_of_day") >= 6) & (F.col("hour_of_day") <= 22))
        .withColumn("day_of_week", F.dayofweek("dt"))
        .withColumn("is_weekend", F.col("day_of_week").isin([1, 7])) # 1=Sun, 7=Sat
        .withColumn("week_of_year", F.weekofyear("dt"))
        .withColumn("month", F.month("dt"))
        .withColumn("part_of_day", 
            F.when((F.col("hour_of_day") >= 6) & (F.col("hour_of_day") < 12), "Morning")
             .when((F.col("hour_of_day") >= 12) & (F.col("hour_of_day") < 18), "Afternoon")
             .when((F.col("hour_of_day") >= 18) & (F.col("hour_of_day") < 22), "Evening")
             .otherwise("Night")
        )
        .withColumn("discount_depth", F.lit(1.0) - F.col("discount"))
    )

    output_count = df_hourly_enhanced.count()
    logger.info(f"Generated {output_count} hourly records")

    # Write to Postgres silver.hourly_sales
    df_write = df_hourly_enhanced.drop("dt")
    
    df_write.write.jdbc(
        url=db_url,
        table="silver.hourly_sales",
        mode="append",
        properties=db_props
    )

    return {
        "status": "success",
        "daily_records": initial_count,
        "hourly_records": output_count
    }


def main():
    parser = argparse.ArgumentParser(description="Explode Daily to Hourly")
    parser.add_argument("--date", required=True, help="Processing date YYYY-MM-DD")
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
        res = process_hourly(spark, args.date, db_url, db_props)
        logger.info(f"Pipeline finished: {res}")
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
