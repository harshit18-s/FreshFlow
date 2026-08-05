{{ config(materialized='incremental', incremental_strategy='append') }}

select
    ds.store_id,
    dp.product_id,
    i.incident_start as start_timestamp,
    i.incident_end as end_timestamp,
    i.duration_hours,
    null::numeric as operational_duration_hours,
    null::numeric as pre_incident_sales,
    null::numeric as post_incident_sales,
    null::numeric as estimated_lost_demand,
    null::numeric as estimated_lost_revenue,
    null::numeric as severity_score,
    null::text as incident_class
from {{ source('silver', 'stockout_incidents') }} i
join {{ ref('dim_store') }} ds on i.store_id = ds.store_id
join {{ ref('dim_product') }} dp on i.product_id = dp.product_id
{% if is_incremental() %}
  where i.incident_start > (select coalesce(max(start_timestamp), '1900-01-01'::timestamp) from {{ this }})
{% endif %}
