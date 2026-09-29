-- Staging model for erp_customers (25,000 rows; 2,376 postal codes zfill(5)'d in transform.py)
with source as (
    select * from {{ source('raw', 'erp_customers') }}
),
renamed as (
    select
        customer_id,
        customer_name,
        customer_age,
        gender,
        customer_segment,
        customer_city,
        customer_state,
        customer_country,
        region,
        customer_postal_code,
        cast(customer_acquisition_cost as numeric(12, 2)) as customer_acquisition_cost
    from source
)
select * from renamed