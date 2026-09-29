-- Staging model for erp_products (already clean at source, no changes in transform.py)
with source as (
    select * from {{ source('raw', 'erp_products') }}
),
renamed as (
    select
        product_id,
        product_name,
        product_category,
        product_subcategory,
        brand,
        supplier,
        cast(unit_price as numeric(12, 2)) as unit_price,
        cast(product_cost as numeric(12, 2)) as product_cost,
        cast(product_rating as numeric(2, 1)) as product_rating
    from source
)
select * from renamed