select
    observation_id,
    observed_at,
    observation_date,
    hour_of_day,
    location_id,
    vehicle_type,
    speed_kmh,
    traffic_state,
    direction,
    sensor_id,
    ingested_at
from {{ ref('stg_traffic_observations') }}

