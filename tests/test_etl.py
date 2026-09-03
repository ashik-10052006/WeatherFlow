import pytest
import pandas as pd
from datetime import datetime, timezone

from backend.api_client import WeatherApiClient, decode_wmo_code
from backend.etl_pipeline import WeatherETLPipeline
from backend.database import SessionLocal
from backend.repositories.weather_repository import WeatherRepository
from backend.models import Location, WeatherRecord


def test_wmo_code_decoding():
    """Verify numeric WMO weather codes are decoded accurately."""
    assert decode_wmo_code(0) == "Clear sky"
    assert decode_wmo_code(1) == "Mainly clear"
    assert decode_wmo_code(3) == "Overcast"
    assert decode_wmo_code(61) == "Slight rain"
    assert decode_wmo_code(95) == "Thunderstorm"
    assert decode_wmo_code(None) == "Unknown"
    assert decode_wmo_code(999) == "Weather Code 999"


def test_sample_weather_data_loading():
    """Verify loading offline sample dataset loads valid dictionaries."""
    sample_records = WeatherApiClient.load_sample_data()
    assert len(sample_records) >= 8
    first = sample_records[0]
    assert first["success"] is True
    assert "city_name" in first
    assert "temperature_c" in first
    assert "humidity_percent" in first
    assert "weather_condition" in first


def test_etl_transform_structure():
    """Verify DataFrame structure and typing produced by transform phase."""
    raw_data = [
        {
            "success": True,
            "location_id": "1",
            "city_name": "TestCity",
            "recorded_at": "2026-09-03T10:00",
            "temperature_c": "25.4",
            "humidity_percent": "60",
            "wind_speed_kmh": "10.5",
            "weather_code": "0",
            "weather_condition": "Clear sky",
        },
        {
            "success": False,  # Failed API request
            "error": "Timeout",
        },
    ]

    pipeline = WeatherETLPipeline()
    df = pipeline.transform(raw_data)

    assert len(df) == 1
    assert df.iloc[0]["location_id"] == 1
    assert isinstance(df.iloc[0]["temperature_c"], float)
    assert df.iloc[0]["temperature_c"] == 25.4
    assert df.iloc[0]["humidity_percent"] == 60
    assert df.iloc[0]["weather_condition"] == "Clear sky"


def test_etl_end_to_end_mock_dataset():
    """Verify end-to-end pipeline execution with sample dataset."""
    db = SessionLocal()
    try:
        pipeline = WeatherETLPipeline()
        result = pipeline.run(db, use_sample_data=True)

        assert result["status"] in ("SUCCESS", "PARTIAL")
        assert result["records_extracted"] >= 8
        assert "run_id" in result
        assert result["error"] is None
    finally:
        db.close()


def test_incremental_deduplication():
    """Verify incremental load skips duplicate records when re-inserted."""
    db = SessionLocal()
    try:
        locations = WeatherRepository.get_all_locations(db)
        assert len(locations) > 0
        loc = locations[0]

        fixed_time = datetime(2026, 9, 3, 12, 0, 0)

        df = pd.DataFrame(
            [
                {
                    "location_id": loc.location_id,
                    "recorded_at": fixed_time,
                    "temperature_c": 21.5,
                    "humidity_percent": 55,
                    "wind_speed_kmh": 10.0,
                    "weather_code": 1,
                    "weather_condition": "Mainly clear",
                    "source": "unit_test",
                }
            ]
        )

        # First insert
        loaded1, skipped1 = WeatherRepository.insert_weather_records_incremental(db, df)
        assert loaded1 in (0, 1)

        # Second insert with identical key (location_id, recorded_at)
        loaded2, skipped2 = WeatherRepository.insert_weather_records_incremental(db, df)
        assert loaded2 == 0
        assert skipped2 == 1

    finally:
        db.close()
