select
    w.weather_main,
    w.weather_description,
    count(*) as observation_count,
    round(avg(f.traffic_volume)::numeric, 1) as avg_traffic_volume,
    round(avg(f.temp_celsius)::numeric, 1) as avg_temp_celsius,
    round(100.0 * avg((f.traffic_state = 'heavy')::integer), 1)
        as heavy_traffic_rate_percent
from {{ ref('fct_traffic_observation') }} f
join {{ ref('dim_weather') }} w using (weather_key)
group by 1, 2
