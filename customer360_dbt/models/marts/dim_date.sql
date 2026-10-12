-- Dimension: one row per calendar day (grain: date_day).
-- Range covers the full ERP order history (2021-01-01 to 2025-12-31).
-- Generated in SQL; no source table needed.

with days as (

    select cast(d as date) as date_day
    from generate_series(
        cast('2021-01-01' as date),
        cast('2025-12-31' as date),
        interval '1 day'
    ) as d

)

select
    date_day,
    cast(to_char(date_day, 'YYYYMMDD') as integer)  as date_key,
    extract(year from date_day)::int                as year,
    extract(quarter from date_day)::int             as quarter,
    extract(month from date_day)::int               as month,
    to_char(date_day, 'FMMonth')                    as month_name,
    extract(week from date_day)::int                as iso_week,
    extract(isodow from date_day)::int              as day_of_week,
    to_char(date_day, 'FMDay')                      as day_name,
    extract(isodow from date_day) in (6, 7)         as is_weekend,
    to_char(date_day, 'YYYY-MM')                    as year_month
from days