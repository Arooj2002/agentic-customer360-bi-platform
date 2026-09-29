-- Staging model for erp_order_items (grain: one product per order; discount_rate is 0-1 fraction, distinct from web's 0-100 discount_percentage)
with source as (
    select * from {{ source('raw', 'erp_order_items') }}
),
renamed as (
    select
        order_id,
        product_id,
        quantity,
        cast(unit_price as numeric(12, 2)) as unit_price,
        discount_rate,
        cast(discount_amount as numeric(12, 2)) as discount_amount,
        cast(gross_sales as numeric(12, 2)) as gross_sales,
        cast(tax_amount as numeric(12, 2)) as tax_amount,
        cast(shipping_cost as numeric(12, 2)) as shipping_cost,
        cast(net_sales as numeric(12, 2)) as net_sales,
        cast(product_cost as numeric(12, 2)) as product_cost,
        cast(profit as numeric(12, 2)) as profit
    from source
)
select * from renamed