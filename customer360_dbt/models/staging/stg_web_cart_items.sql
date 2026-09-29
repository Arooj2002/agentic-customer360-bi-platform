-- Staging model for web_cart_items (grain: cart line; (cart_id, product_id) is NOT unique — 12 carts have same product on two lines)
with source as (
    select * from {{ source('raw', 'web_cart_items') }}
),
renamed as (
    select
        cart_item_id,
        cart_id,
        user_id,
        product_id,
        price,
        quantity,
        total,
        discount_percentage,
        discounted_total
    from source
)
select * from renamed