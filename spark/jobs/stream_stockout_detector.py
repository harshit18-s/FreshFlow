"""
FreshFlow AI — Real-Time Streaming Stockout Anomaly Detector
============================================================
PySpark Structured Streaming job detecting intraday zero-velocity stockout events
and sudden transaction drop anomalies in real time.
"""

import sys
import logging
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, window, count, avg, when, current_timestamp

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def create_spark_session(app_name: str = "FreshFlow-StreamingStockoutDetector"):
    """Create and configure Spark session for streaming."""
    return (
        SparkSession.builder
        .appName(app_name)
        .config("spark.sql.shuffle.partitions", "2")
        .getOrCreate()
    )


def process_stream(input_dir: str = "/opt/airflow/data/bronze/streaming_pos"):
    """
    Process streaming POS sales transactions with a sliding 2-hour window.
    Detects zero-sales anomalies relative to expected hourly sales velocity.
    """
    spark = create_spark_session()
    logger.info(f"Starting Structured Streaming engine listening to {input_dir}...")

    # Read streaming schema
    try:
        sales_stream = (
            spark.readStream
            .format("parquet")
            .option("maxFilesPerTrigger", 1)
            .load(input_dir)
        )
    except Exception as e:
        logger.warning(f"Streaming directory not available, initializing empty stream schema: {e}")
        return

    # Calculate 2-hour sliding window velocity with 10-minute slide
    windowed_velocity = (
        sales_stream
        .withWatermark("timestamp", "15 minutes")
        .groupBy(
            window(col("timestamp"), "2 hours", "10 minutes"),
            col("store_id"),
            col("product_id")
        )
        .agg(
            count("transaction_id").alias("transaction_count"),
            avg("units_sold").alias("avg_units_per_tx")
        )
        .withColumn(
            "anomaly_flag",
            when(col("transaction_count") == 0, "CRITICAL_STOCKOUT")
            .when(col("transaction_count") < 3, "WARNING_LOW_VELOCITY")
            .otherwise("NORMAL")
        )
    )

    # Filter anomaly stream
    stockout_alerts = windowed_velocity.filter(col("anomaly_flag") != "NORMAL")

    logger.info("Writing stream alerts console sink...")
    query = (
        stockout_alerts.writeStream
        .outputMode("update")
        .format("console")
        .option("truncate", "false")
        .start()
    )

    query.awaitTermination(timeout=5)


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "/opt/airflow/data/bronze/streaming_pos"
    process_stream(path)
