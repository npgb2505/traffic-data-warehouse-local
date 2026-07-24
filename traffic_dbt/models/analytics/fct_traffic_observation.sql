{{
    config(
        materialized='incremental',
        unique_key='observation_id',
        incremental_strategy='delete+insert'
    )
}}

select
    observation_id,
    observed_at,
    observation_date,
    hour_of_day,
    iso_day_of_week,
    is_weekend,
    holiday,
    weather_key,
    temp_celsius,
    rain_1h,
    snow_1h,
    clouds_all,
    traffic_volume,
    traffic_state,
    batch_id,
    ingested_at
from {{ ref('stg_traffic_observations') }}

{% if is_incremental() %}
where ingested_at > (
    select coalesce(max(ingested_at), '1900-01-01'::timestamptz)
    from {{ this }}
)
{% endif %}
