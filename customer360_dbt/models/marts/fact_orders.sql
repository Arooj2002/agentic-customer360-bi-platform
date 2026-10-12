-- Fact: one row per ERP order (grain: order_id).
-- Customer attributes live in dim_customers (verified identical to the order-level copies).
-- Meaningful NULLs are kept: delivery/rating/review for non-completed orders,
-- return_status/return_reason for non-returned orders.

with orders as (

    select * from {{ ref('stg_erp_orders') }}

)

select
    -- keys
    order_id,
    customer_id,
    cast(to_char(order_date, 'YYYYMMDD') as integer)  as order_date_key,

    -- order attributes
    order_date,
    order_datetime,
    order_status,
    sales_channel,
    customer_type,
    payment_method,
    payment_status,
    currency,
    shipping_method,
    warehouse,

    -- delivery and returns
    delivery_days,
    estimated_delivery_days,
    delivery_status,
    return_status,
    return_reason,

    -- feedback
    customer_rating,
    review_sentiment,
    customer_review,

    -- marketing
    marketing_channel,
    campaign_name,
    coupon_code,

    -- loyalty
    loyalty_points_earned,
    loyalty_points_redeemed,

    -- measures
    quantity,
    gross_sales,
    discount_amount,
    tax_amount,
    shipping_cost,
    net_sales,
    product_cost,
    profit,
    profit_margin_percentage,

    -- customer-level metrics carried on the order
    customer_lifetime_value,
    is_repeat_customer,
    customer_order_count
from orders