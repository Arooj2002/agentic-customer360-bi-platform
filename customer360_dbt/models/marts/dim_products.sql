-- Dimension: one row per ERP product (grain: product_id).
-- Source: stg_erp_products. Marts are materialized as tables.

with products as (

    select * from {{ ref('stg_erp_products') }}

)

select
    product_id,
    product_name,
    product_category,
    product_subcategory,
    brand,
    supplier,
    unit_price,
    product_cost,
    product_rating
from products