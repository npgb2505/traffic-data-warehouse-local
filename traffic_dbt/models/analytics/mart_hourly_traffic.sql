select
    observation_date,
    hour_of_day,
    location_id,
    count(*) as observation_count,
    round(avg(speed_kmh)::numeric, 1) as avg_speed_kmh,
    round(percentile_cont(0.5) within group (order by speed_kmh)::numeric, 1) as median_speed_kmh,
    round(100.0 * avg((traffic_state = 'congested')::integer), 1) as congestion_rate_percent
from {{ ref('fct_traffic_observation') }}
group by 1, 2, 3

