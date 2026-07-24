select
    observation_id,
    observed_at,
    observed_at::date as observation_date,
    extract(hour from observed_at)::integer as hour_of_day,
    extract(isodow from observed_at)::integer as iso_day_of_week,
    extract(isodow from observed_at) in (6, 7) as is_weekend,
    nullif(holiday, '') as holiday,
    round((temp_kelvin - 273.15)::numeric, 2) as temp_celsius,
    rain_1h,
    snow_1h,
    clouds_all,
    lower(weather_main) as weather_main,
    lower(weather_description) as weather_description,
    md5(lower(weather_main) || '|' || lower(weather_description)) as weather_key,
    traffic_volume,
    case
        when traffic_volume >= 4000 then 'heavy'
        when traffic_volume >= 2000 then 'moderate'
        else 'light'
    end as traffic_state,
    source_row_number,
    batch_id,
    ingested_at
from raw.traffic_observations
