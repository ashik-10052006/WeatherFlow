-- ============================================================================
-- Script: 02_create_tables.sql
-- Description: DDL script creating all core tables in WeatherDataWarehouse.
-- Target DBMS: Microsoft SQL Server 2016+
-- ============================================================================

USE WeatherDataWarehouse;
GO

-- 1. Table: locations
-- Purpose: Dimension table holding configured geographic locations and their coordinates.
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'locations')
BEGIN
    CREATE TABLE locations (
        location_id INT IDENTITY(1,1) PRIMARY KEY,
        city_name NVARCHAR(100) NOT NULL,
        country NVARCHAR(100) NULL,
        latitude DECIMAL(9,6) NOT NULL,
        longitude DECIMAL(9,6) NOT NULL,
        created_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
        CONSTRAINT UQ_locations_city_country UNIQUE (city_name, country)
    );
    PRINT 'Table locations created successfully.';
END
ELSE
BEGIN
    PRINT 'Table locations already exists.';
END
GO

-- 2. Table: pipeline_runs
-- Purpose: Telemetry table tracking every automated or manual ETL pipeline execution.
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'pipeline_runs')
BEGIN
    CREATE TABLE pipeline_runs (
        run_id BIGINT IDENTITY(1,1) PRIMARY KEY,
        pipeline_name NVARCHAR(100) NOT NULL,
        started_at DATETIME2 NOT NULL,
        completed_at DATETIME2 NULL,
        status NVARCHAR(20) NOT NULL, -- 'RUNNING', 'SUCCESS', 'FAILED', 'PARTIAL'
        records_extracted INT NOT NULL DEFAULT 0,
        records_loaded INT NOT NULL DEFAULT 0,
        error_message NVARCHAR(MAX) NULL
    );
    PRINT 'Table pipeline_runs created successfully.';
END
ELSE
BEGIN
    PRINT 'Table pipeline_runs already exists.';
END
GO

-- 3. Table: weather_records
-- Purpose: Fact table storing time-series weather observations per location.
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'weather_records')
BEGIN
    CREATE TABLE weather_records (
        weather_id BIGINT IDENTITY(1,1) PRIMARY KEY,
        location_id INT NOT NULL,
        recorded_at DATETIME2 NOT NULL,
        temperature_c DECIMAL(5,2) NULL,
        humidity_percent INT NULL,
        wind_speed_kmh DECIMAL(6,2) NULL,
        weather_code INT NULL,
        weather_condition NVARCHAR(100) NULL,
        source NVARCHAR(50) NOT NULL DEFAULT 'weather_api',
        created_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
        CONSTRAINT FK_weather_records_locations FOREIGN KEY (location_id)
            REFERENCES locations(location_id) ON DELETE CASCADE,
        CONSTRAINT UQ_weather_records_location_recorded UNIQUE (location_id, recorded_at)
    );
    PRINT 'Table weather_records created successfully.';
END
ELSE
BEGIN
    PRINT 'Table weather_records already exists.';
END
GO

-- 4. Table: data_quality_logs
-- Purpose: Audit table recording validation failures and data cleansing events.
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'data_quality_logs')
BEGIN
    CREATE TABLE data_quality_logs (
        quality_id BIGINT IDENTITY(1,1) PRIMARY KEY,
        run_id BIGINT NULL,
        table_name NVARCHAR(100) NOT NULL,
        issue_type NVARCHAR(100) NOT NULL,
        issue_count INT NOT NULL,
        created_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
        CONSTRAINT FK_data_quality_logs_run FOREIGN KEY (run_id)
            REFERENCES pipeline_runs(run_id) ON DELETE SET NULL
    );
    PRINT 'Table data_quality_logs created successfully.';
END
ELSE
BEGIN
    PRINT 'Table data_quality_logs already exists.';
END
GO

-- Seed initial locations if table is empty
IF NOT EXISTS (SELECT 1 FROM locations)
BEGIN
    INSERT INTO locations (city_name, country, latitude, longitude)
    VALUES 
        (N'Bangalore', N'India', 12.971600, 77.594600),
        (N'Mumbai', N'India', 19.076000, 72.877700),
        (N'Delhi', N'India', 28.613900, 77.209000),
        (N'London', N'United Kingdom', 51.507400, -0.127800),
        (N'New York', N'United States', 40.712800, -74.006000),
        (N'Tokyo', N'Japan', 35.676200, 139.650300),
        (N'Paris', N'France', 48.856600, 2.352200),
        (N'Sydney', N'Australia', -33.868800, 151.209300);
    PRINT 'Seeded default geographic locations.';
END
GO
