-- ============================================================================
-- Script: 03_indexes.sql
-- Description: Creates performance indexes for time-series analytics and joins.
-- Target DBMS: Microsoft SQL Server 2016+
-- ============================================================================

USE WeatherDataWarehouse;
GO

-- Index 1: Optimize queries retrieving historical observations for a location sorted by time
IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'IX_weather_records_location_recorded')
BEGIN
    CREATE NONCLUSTERED INDEX IX_weather_records_location_recorded
    ON weather_records (location_id, recorded_at DESC)
    INCLUDE (temperature_c, humidity_percent, wind_speed_kmh, weather_condition);
    PRINT 'Index IX_weather_records_location_recorded created.';
END
GO

-- Index 2: Optimize queries aggregating cross-location metrics over time windows
IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'IX_weather_records_recorded_at')
BEGIN
    CREATE NONCLUSTERED INDEX IX_weather_records_recorded_at
    ON weather_records (recorded_at DESC)
    INCLUDE (temperature_c, humidity_percent, wind_speed_kmh);
    PRINT 'Index IX_weather_records_recorded_at created.';
END
GO

-- Index 3: Optimize pipeline history lookup
IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'IX_pipeline_runs_started_at')
BEGIN
    CREATE NONCLUSTERED INDEX IX_pipeline_runs_started_at
    ON pipeline_runs (started_at DESC);
    PRINT 'Index IX_pipeline_runs_started_at created.';
END
GO

-- Index 4: Optimize quality logs lookup by run ID
IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'IX_data_quality_logs_run_id')
BEGIN
    CREATE NONCLUSTERED INDEX IX_data_quality_logs_run_id
    ON data_quality_logs (run_id);
    PRINT 'Index IX_data_quality_logs_run_id created.';
END
GO
