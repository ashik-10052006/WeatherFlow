from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict


# ============================================================================
# Location Schemas
# ============================================================================

class LocationBase(BaseModel):
    city_name: str
    country: Optional[str] = None
    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)


class LocationCreate(LocationBase):
    pass


class LocationResponse(LocationBase):
    location_id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Weather Record Schemas
# ============================================================================

class WeatherRecordResponse(BaseModel):
    weather_id: Optional[int] = None
    location_id: int
    city_name: str
    country: Optional[str] = None
    recorded_at: Optional[str] = None
    temperature_c: Optional[float] = None
    humidity_percent: Optional[int] = None
    wind_speed_kmh: Optional[float] = None
    weather_code: Optional[int] = None
    weather_condition: Optional[str] = None
    source: str = "weather_api"

    model_config = ConfigDict(from_attributes=True)


class LatestWeatherResponse(BaseModel):
    weather_id: Optional[int] = None
    location_id: int
    city_name: str
    country: Optional[str] = None
    latitude: float
    longitude: float
    recorded_at: Optional[datetime] = None
    temperature_c: Optional[float] = None
    humidity_percent: Optional[int] = None
    wind_speed_kmh: Optional[float] = None
    weather_code: Optional[int] = None
    weather_condition: Optional[str] = None
    source: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Analytics Schemas
# ============================================================================

class AnalyticsSummaryResponse(BaseModel):
    total_records: int
    total_locations: int
    avg_temperature_c: Optional[float] = None
    max_temperature_c: Optional[float] = None
    min_temperature_c: Optional[float] = None
    avg_humidity_percent: Optional[float] = None
    latest_record_time: Optional[str] = None


class TemperatureTrendItem(BaseModel):
    date: str
    city_name: str
    avg_temperature: Optional[float] = None
    max_temperature: Optional[float] = None
    min_temperature: Optional[float] = None
    sample_count: int


class HumidityTrendItem(BaseModel):
    date: str
    city_name: str
    avg_humidity: Optional[float] = None
    max_humidity: Optional[int] = None
    min_humidity: Optional[int] = None
    sample_count: int


# ============================================================================
# Pipeline Schemas
# ============================================================================

class PipelineRunRequest(BaseModel):
    use_sample_data: bool = Field(
        default=False,
        description="Set to true to run ETL with offline sample JSON dataset instead of live API",
    )


class DataQualityLogResponse(BaseModel):
    quality_id: int
    table_name: str
    issue_type: str
    issue_count: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PipelineRunResponse(BaseModel):
    run_id: int
    pipeline_name: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    status: str
    records_extracted: int
    records_loaded: int
    error_message: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class PipelineRunDetailResponse(PipelineRunResponse):
    quality_logs: List[DataQualityLogResponse] = []


class PipelineExecutionResult(BaseModel):
    success: bool
    run_id: int
    status: str
    records_extracted: int
    records_loaded: int
    duplicates_skipped: int
    quality_issues_found: int
    message: str
