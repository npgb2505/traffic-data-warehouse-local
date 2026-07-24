select distinct
    location_id,
    location_name,
    district,
    latitude,
    longitude
from {{ ref('stg_traffic_observations') }}

