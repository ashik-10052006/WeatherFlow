-- ============================================================================
-- Script: 04_sample_queries.sql
-- Description: Analytical & reporting queries for WeatherDataWarehouse.
-- ============================================================================

USE WeatherDataWarehouse;
GO

-- 1. Latest Weather Observation per City (Window Function)
WITH RankedWeather AS (
    SELECT 
        l.city_name,
        l.country,
        w.recorded_at,
        w.temperature_c,
        w.humidity_percent,
        w.wind_speed_kmh,
        w.weather_condition,
        ROW_NUMBER() OVER(PARTITION BY l.location_id ORDER BY w.recorded_at DESC) AS rn
    FROM weather_records w
    INNER JOIN locations l ON w.location_id = l.location_id
)
SELECT 
    city_name,
    country,
    recorded_at,
    temperature_c,
    humidity_percent,
    wind_speed_kmh,
    weather_condition
FROM RankedWeather
WHERE rn = 1
ORDER BY city_name;
GO

-- 2. Warehouse KPI Summary
SELECT 
    COUNT(*) AS total_observations,
    COUNT(DISTINCT location_id) AS monitored_cities,
    ROUND(AVG(temperature_c), 2) AS avg_temperature_c,
    MAX(temperature_c) AS max_temperature_c,
    MIN(temperature_c) AS min_temperature_c,
    ROUND(AVG(CAST(humidity_percent AS FLOAT)), 2) AS avg_humidity_percent,
    MAX(recorded_at) AS latest_observation_time
FROM weather_records;
GO

-- 3. Daily Temperature Trends by City (Time-Series Aggregation)
SELECT 
    CAST(w.recorded_at AS DATE) AS observation_date,
    l.city_name,
    ROUND(AVG(w.temperature_c), 2) AS avg_temp,
    MAX(w.temperature_c) AS max_temp,
    MIN(w.temperature_c) AS min_temp,
    COUNT(*) AS sample_count
FROM weather_records w
INNER JOIN locations l ON w.location_id = l.location_id
GROUP BY CAST(w.recorded_at AS DATE), l.city_name
ORDER BY observation_date DESC, l.city_name;
GO

-- 4. Pipeline Execution & Data Quality Audit
SELECT 
    p.run_id,
    p.pipeline_name,
    p.status,
    p.started_at,
    p.completed_at,
    DATEDIFF(SECOND, p.started_at, p.completed_at) AS duration_seconds,
    p.records_extracted,
    p.records_loaded,
    COALESCE(SUM(q.issue_count), 0) AS total_quality_issues
FROM pipeline_runs p
LEFT JOIN data_quality_logs q ON p.run_id = q.run_id
GROUP BY 
    p.run_id, p.pipeline_name, p.status, p.started_at, p.completed_at, 
    p.records_extracted, p.records_loaded
ORDER BY p.started_at DESC;
GO
