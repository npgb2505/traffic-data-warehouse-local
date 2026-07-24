select
    weather_key,
    weather_main,
    weather_description
from {{ ref('stg_traffic_observations') }}
group by 1, 2, 3
