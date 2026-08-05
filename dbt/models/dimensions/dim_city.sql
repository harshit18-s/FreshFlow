{{ config(materialized='incremental', incremental_strategy='append') }}

select distinct
    city_id,
    'City ' || city_id::varchar as city_label,
    'Region Unknown' as region_label
from {{ ref('stg_hourly_sales') }}
where city_id is not null
{% if is_incremental() %}
  and city_id not in (select city_id from {{ this }})
{% endif %}
