import pandas as pd
from datetime import datetime, timezone, timedelta
from backend.data_validator import WeatherDataValidator


def test_valid_weather_dataframe():
    """Verify that clean, well-formed records pass validation with 0 quality issues."""
    data = [
        {
            "location_id": 1,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "temperature_c": 24.5,
            "humidity_percent": 65,
            "wind_speed_kmh": 12.0,
            "weather_code": 3,
            "weather_condition": "Overcast",
        },
        {
            "location_id": 2,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "temperature_c": -10.2,
            "humidity_percent": 80,
            "wind_speed_kmh": 5.4,
            "weather_code": 71,
            "weather_condition": "Slight snow fall",
        },
    ]
    df = pd.DataFrame(data)
    clean_df, issues = WeatherDataValidator.validate_weather_dataframe(df)

    assert len(clean_df) == 2
    assert len(issues) == 0


def test_invalid_temperature_out_of_bounds():
    """Verify temperatures outside -60°C to +60°C are rejected and logged."""
    data = [
        {
            "location_id": 1,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "temperature_c": 85.0,  # Impossible hot
            "humidity_percent": 50,
            "wind_speed_kmh": 10.0,
        },
        {
            "location_id": 2,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "temperature_c": -95.0,  # Impossible cold
            "humidity_percent": 50,
            "wind_speed_kmh": 10.0,
        },
        {
            "location_id": 3,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "temperature_c": 22.0,  # Valid
            "humidity_percent": 50,
            "wind_speed_kmh": 10.0,
        },
    ]
    df = pd.DataFrame(data)
    clean_df, issues = WeatherDataValidator.validate_weather_dataframe(df)

    assert len(clean_df) == 1
    assert clean_df.iloc[0]["location_id"] == 3
    assert any(i["issue_type"] == "OUT_OF_RANGE_TEMPERATURE" for i in issues)


def test_invalid_humidity_bounds():
    """Verify humidity values outside 0-100% are filtered."""
    data = [
        {
            "location_id": 1,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "temperature_c": 20.0,
            "humidity_percent": -15,  # Negative
            "wind_speed_kmh": 5.0,
        },
        {
            "location_id": 2,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "temperature_c": 20.0,
            "humidity_percent": 150,  # Above 100%
            "wind_speed_kmh": 5.0,
        },
        {
            "location_id": 3,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "temperature_c": 20.0,
            "humidity_percent": 75,  # Valid
            "wind_speed_kmh": 5.0,
        },
    ]
    df = pd.DataFrame(data)
    clean_df, issues = WeatherDataValidator.validate_weather_dataframe(df)

    assert len(clean_df) == 1
    assert clean_df.iloc[0]["location_id"] == 3
    assert any(i["issue_type"] == "INVALID_HUMIDITY_RANGE" for i in issues)


def test_negative_wind_speed():
    """Verify negative wind speed is flagged and rejected."""
    data = [
        {
            "location_id": 1,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "temperature_c": 20.0,
            "humidity_percent": 50,
            "wind_speed_kmh": -8.5,  # Negative
        }
    ]
    df = pd.DataFrame(data)
    clean_df, issues = WeatherDataValidator.validate_weather_dataframe(df)

    assert len(clean_df) == 0
    assert any(i["issue_type"] == "NEGATIVE_WIND_SPEED" for i in issues)


def test_missing_required_fields():
    """Verify rows missing location_id or recorded_at are filtered."""
    data = [
        {
            "location_id": None,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "temperature_c": 20.0,
            "humidity_percent": 50,
            "wind_speed_kmh": 5.0,
        },
        {
            "location_id": 2,
            "recorded_at": None,
            "temperature_c": 20.0,
            "humidity_percent": 50,
            "wind_speed_kmh": 5.0,
        },
    ]
    df = pd.DataFrame(data)
    clean_df, issues = WeatherDataValidator.validate_weather_dataframe(df)

    assert len(clean_df) == 0
    assert any(i["issue_type"] == "MISSING_REQUIRED_FIELDS" for i in issues)


def test_duplicate_records_in_batch():
    """Verify duplicate records within the batch are detected and deduplicated."""
    now_str = datetime.now(timezone.utc).isoformat()
    data = [
        {
            "location_id": 1,
            "recorded_at": now_str,
            "temperature_c": 20.0,
            "humidity_percent": 50,
            "wind_speed_kmh": 5.0,
        },
        {
            "location_id": 1,
            "recorded_at": now_str,  # Exact duplicate
            "temperature_c": 20.0,
            "humidity_percent": 50,
            "wind_speed_kmh": 5.0,
        },
    ]
    df = pd.DataFrame(data)
    clean_df, issues = WeatherDataValidator.validate_weather_dataframe(df)

    assert len(clean_df) == 1
    assert any(i["issue_type"] == "BATCH_DUPLICATE_RECORDS" for i in issues)


def test_empty_dataframe_handling():
    """Verify validator handles an empty DataFrame safely without raising exceptions."""
    df = pd.DataFrame()
    clean_df, issues = WeatherDataValidator.validate_weather_dataframe(df)
    assert clean_df.empty
    assert issues == []
