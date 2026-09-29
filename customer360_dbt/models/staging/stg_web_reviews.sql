-- Staging model for web_reviews (exploded from DummyJSON products; reviewer_email already dropped in transform.py)
with source as (
    select * from {{ source('raw', 'web_reviews') }}
),
renamed as (
    select
        review_id,
        product_id,
        review_rating,
        review_comment,
        review_date,
        reviewer_name
    from source
)
select * from renamed