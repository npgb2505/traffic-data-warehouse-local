SELECT * FROM raw.pipeline_runs ORDER BY finished_at DESC LIMIT 5;
SELECT * FROM raw.data_quality_results ORDER BY batch_id, check_name;

SELECT * FROM analytics.mart_hourly_patterns
ORDER BY hour_of_day, is_weekend;

SELECT * FROM analytics.mart_weather_impact
ORDER BY observation_count DESC;

SELECT * FROM analytics.mart_congestion_profile
ORDER BY iso_day_of_week, hour_of_day;
