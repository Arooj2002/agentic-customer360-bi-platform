-- Staging model for web_users (source: DummyJSON API, loaded via src/load.py)
-- Purpose: rename/passthrough columns from raw.web_users with no business logic.

with source as (

    select * from {{ source('raw', 'web_users') }}

),

renamed as (

    select
        user_id,
        first_name,
        last_name,
        age,
        gender,
        role,
        city,
        state,
        state_code,
        postal_code,
        country,
        company_department,
        job_title

    from source

)

select * from renamed