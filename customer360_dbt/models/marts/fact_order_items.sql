-- Fact: one row per ERP order line (grain: order line).
-- (order_id, product_id) is NOT unique: 87 pairs appear twice as real separate lines.
-- order_item_id is an md5 hash over all 12 source columns (deterministic across runs).
--
-- Source inconsistency: for 11,226 of 138,116 orders (8.1%) the line totals do not match
-- the order header in fact_orders (lines are always higher). All 1-line orders reconcile.
-- Lines are kept unchanged and flagged via is_order_reconciled. Revenue KPIs must use
-- fact_orders (matches dataset_statistics); line-level sums are valid only where the
-- flag is true.

with items as (

    select * from {{ ref('stg_erp_order_items') }}

),

orders as (

    select order_id, net_sales, profit, quantity
    from {{ ref('fact_orders') }}

),

line_totals as (

    select
        order_id,
        count(*)          as line_count,
        sum(net_sales)    as net_sales,
        sum(profit)       as profit,
        sum(quantity)     as quantity
    from items
    group by order_id

),

reconciliation as (

    select
        o.order_id,
        t.line_count,
        (
            abs(t.net_sales - o.net_sales) <= 0.05
            and abs(t.profit - o.profit) <= 0.05
            and t.quantity = o.quantity
        ) as is_order_reconciled
    from orders o
    join line_totals t on t.order_id = o.order_id

)

select
    md5(concat_ws('|',
        i.order_id, i.product_id, i.quantity, i.unit_price, i.discount_rate, i.discount_amount,
        i.gross_sales, i.tax_amount, i.shipping_cost, i.net_sales, i.product_cost, i.profit
    ))                        as order_item_id,
    i.order_id,
    i.product_id,
    i.quantity,
    i.unit_price,
    i.discount_rate,
    i.discount_amount,
    i.gross_sales,
    i.tax_amount,
    i.shipping_cost,
    i.net_sales,
    i.product_cost,
    i.profit,
    r.line_count,
    r.is_order_reconciled
from items i
left join reconciliation r on r.order_id = i.order_id