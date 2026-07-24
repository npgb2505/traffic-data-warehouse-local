select
    hour_of_day,
    is_weekend,
    count(*) as observation_count,
    round(avg(traffic_volume)::numeric, 1) as avg_traffic_volume,
    round(percentile_cont(0.5) within group (order by traffic_volume)::numeric, 1)
        as median_traffic_volume,
    round(100.0 * avg((traffic_state = 'heavy')::integer), 1)
        as heavy_traffic_rate_percent
from {{ ref('fct_traffic_observation') }}
group by 1, 2
