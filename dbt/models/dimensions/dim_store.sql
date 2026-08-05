{{ config(materialized='incremental', incremental_strategy='append') }}

select distinct
    s.store_id,
    c.city_id,
    'Store ' || s.store_id::varchar as store_label,
    'Cluster A' as store_cluster,
    'High' as volume_band
from {{ ref('stg_hourly_sales') }} s
left join {{ ref('dim_city') }} c on s.city_id = c.city_id
where s.store_id is not null
{% if is_incremental() %}
  and s.store_id not in (select store_id from {{ this }})
{% endif %}
