{{ config(materialized='view') }}

select
    store_id,
    product_id,
    event_timestamp,
    event_date,
    hour_of_day,
    city_id,
    observed_sales,
    stockout_flag,
    is_operational_hour,
    day_of_week,
    is_weekend,
    week_of_year,
    month,
    part_of_day,
    discount,
    discount_depth,
    holiday_flag,
    activity_flag,
    precpt,
    avg_temperature,
    avg_humidity,
    avg_wind_level,
    ingestion_batch_id,
    ingested_at
from {{ source('silver', 'hourly_sales') }}
