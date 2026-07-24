SELECT * FROM analytics.mart_congestion_hotspots
ORDER BY congestion_rate_percent DESC;

SELECT * FROM analytics.mart_hourly_traffic
ORDER BY observation_date, hour_of_day, location_id;

