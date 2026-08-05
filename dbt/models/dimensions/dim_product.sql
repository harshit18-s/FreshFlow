{{ config(materialized='incremental', incremental_strategy='append') }}

-- We need to read daily_sales to get the category IDs (they were dropped in hourly_sales)
select distinct
    product_id,
    management_group_id,
    first_category_id,
    second_category_id,
    third_category_id,
    'Product ' || product_id::varchar as product_label,
    'A' as abc_class,
    'X' as xyz_class,
    'High' as perishability_class
from {{ source('silver', 'daily_sales') }}
where product_id is not null
{% if is_incremental() %}
  and product_id not in (select product_id from {{ this }})
{% endif %}
