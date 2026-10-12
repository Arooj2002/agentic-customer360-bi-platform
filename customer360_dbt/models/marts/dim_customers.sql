-- Dimension: one row per ERP customer (grain: customer_id).
-- Includes customers with no orders (never purchased) via a flag, derived from fact data.

with customers as (

    select * from {{ ref('stg_erp_customers') }}

),

order_activity as (

    select
        customer_id,
        count(*)            as total_orders,
        min(order_date)     as first_order_date,
        max(order_date)     as last_order_date
    from {{ ref('stg_erp_orders') }}
    group by customer_id

)

select
    c.customer_id,
    c.customer_name,
    c.customer_age,
    c.gender,
    c.customer_segment,
    c.customer_city,
    c.customer_state,
    c.customer_country,
    c.region,
    c.customer_postal_code,
    c.customer_acquisition_cost,
    coalesce(a.total_orders, 0)           as total_orders,
    a.first_order_date,
    a.last_order_date,
    (a.customer_id is null)               as is_never_purchased
from customers c
left join order_activity a
    on c.customer_id = a.customer_id