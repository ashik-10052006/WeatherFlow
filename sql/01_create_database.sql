-- ============================================================================
-- Script: 01_create_database.sql
-- Description: Creates the WeatherDataWarehouse database if it does not exist.
-- Target DBMS: Microsoft SQL Server 2016+ / Express Edition
-- ============================================================================

IF NOT EXISTS (SELECT name FROM sys.databases WHERE name = N'WeatherDataWarehouse')
BEGIN
    CREATE DATABASE WeatherDataWarehouse;
    PRINT 'Database WeatherDataWarehouse created successfully.';
END
ELSE
BEGIN
    PRINT 'Database WeatherDataWarehouse already exists.';
END
GO
