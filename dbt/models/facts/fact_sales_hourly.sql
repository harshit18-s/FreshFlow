{{ config(materialized='incremental', incremental_strategy='append') }}

select
    cast(to_char(s.event_date, 'YYYYMMDD') as integer) as date_key,
    cast(s.hour_of_day as smallint) as time_key,
    ds.store_id,
    dp.product_id,
    null::integer as weather_band_key,
    s.event_timestamp,
    s.observed_sales,
    s.stockout_flag,
    s.discount as discount_factor,
    s.activity_flag,
    s.holiday_flag,
    0.0 as estimated_hidden_demand,
    0.0 as recovered_demand,
    0.0 as estimated_lost_demand,
    0.0 as estimated_lost_revenue,
    s.ingestion_batch_id as source_batch_id
from {{ ref('stg_hourly_sales') }} s
join {{ ref('dim_store') }} ds on s.store_id = ds.store_id
join {{ ref('dim_product') }} dp on s.product_id = dp.product_id
{% if is_incremental() %}
  where s.event_timestamp > (select coalesce(max(event_timestamp), '1900-01-01'::timestamp) from {{ this }})
{% endif %}
