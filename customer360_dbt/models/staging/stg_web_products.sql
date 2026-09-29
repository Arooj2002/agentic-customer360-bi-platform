-- Staging model for web_products (source: DummyJSON API, loaded via src/load.py)
-- Purpose: rename/passthrough columns from raw.web_products with no business logic.
-- Note: discount_percentage here is DummyJSON's 0-100 scale (distinct from erp_order_items.discount_rate, a 0-1 fraction).

with source as (

    select * from {{ source('raw', 'web_products') }}

),

renamed as (

    select
        product_id,
        product_name,
        category,
        brand,
        sku,
        price,
        discount_percentage,
        rating,
        stock,
        weight,
        availability_status,
        minimum_order_quantity,
        warranty_information,
        shipping_information,
        return_policy,
        created_at

    from source

)

select * from renamed