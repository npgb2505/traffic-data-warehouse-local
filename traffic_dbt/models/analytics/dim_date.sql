select distinct
    observation_date as date_key,
    extract(day from observation_date)::integer as day_of_month,
    extract(month from observation_date)::integer as month_number,
    extract(quarter from observation_date)::integer as quarter_number,
    extract(year from observation_date)::integer as year_number,
    extract(isodow from observation_date)::integer as iso_day_of_week,
    extract(isodow from observation_date) in (6, 7) as is_weekend
from {{ ref('stg_traffic_observations') }}

