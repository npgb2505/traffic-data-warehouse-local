select
    observation_id,
    observed_at,
    observed_at::date as observation_date,
    extract(hour from observed_at)::integer as hour_of_day,
    location_id,
    location_name,
    district,
    latitude,
    longitude,
    lower(vehicle_type) as vehicle_type,
    speed_kmh,
    case
        when speed_kmh < 20 then 'congested'
        when speed_kmh < 35 then 'slow'
        else 'free_flow'
    end as traffic_state,
    direction,
    sensor_id,
    ingested_at
from raw.traffic_observations

