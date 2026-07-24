select
    l.location_id,
    l.location_name,
    l.district,
    l.latitude,
    l.longitude,
    count(*) as observation_count,
    round(avg(f.speed_kmh)::numeric, 1) as avg_speed_kmh,
    round(100.0 * avg((f.traffic_state = 'congested')::integer), 1) as congestion_rate_percent,
    count(*) filter (where f.traffic_state = 'congested') as congested_observations
from {{ ref('fct_traffic_observation') }} f
join {{ ref('dim_location') }} l using (location_id)
group by 1, 2, 3, 4, 5

