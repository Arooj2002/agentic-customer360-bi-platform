-- Staging model for web_carts (header totals reconcile with cart line items)
with source as (
    select * from {{ source('raw', 'web_carts') }}
),
renamed as (
    select
        cart_id,
        user_id,
        total,
        discounted_total,
        total_products,
        total_quantity
    from source
)
select * from renamed