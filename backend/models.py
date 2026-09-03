from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    Integer,
    BigInteger,
    String,
    Numeric,
    DateTime,
    ForeignKey,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from backend.database import Base


class Location(Base):
    """Geographic locations monitored by the weather platform."""

    __tablename__ = "locations"

    location_id = Column(Integer, primary_key=True, autoincrement=True)
    city_name = Column(String(100), nullable=False)
    country = Column(String(100), nullable=True)
    latitude = Column(Numeric(9, 6), nullable=False)
    longitude = Column(Numeric(9, 6), nullable=False)
    created_at = Column(
        DateTime(timezone=False),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    weather_records = relationship(
        "WeatherRecord", back_populates="location", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("city_name", "country", name="UQ_locations_city_country"),
    )

    def __repr__(self) -> str:
        return f"<Location(id={self.location_id}, city='{self.city_name}', country='{self.country}')>"


class WeatherRecord(Base):
    """Time-series observation records extracted from weather API."""

    __tablename__ = "weather_records"

    weather_id = Column(BigInteger, primary_key=True, autoincrement=True)
    location_id = Column(
        Integer,
        ForeignKey("locations.location_id", ondelete="CASCADE"),
        nullable=False,
    )
    recorded_at = Column(DateTime(timezone=False), nullable=False)
    temperature_c = Column(Numeric(5, 2), nullable=True)
    humidity_percent = Column(Integer, nullable=True)
    wind_speed_kmh = Column(Numeric(6, 2), nullable=True)
    weather_code = Column(Integer, nullable=True)
    weather_condition = Column(String(100), nullable=True)
    source = Column(String(50), nullable=False, default="weather_api")
    created_at = Column(
        DateTime(timezone=False),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    location = relationship("Location", back_populates="weather_records")

    __table_args__ = (
        UniqueConstraint(
            "location_id", "recorded_at", name="UQ_weather_records_location_recorded"
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<WeatherRecord(id={self.weather_id}, loc_id={self.location_id}, "
            f"time='{self.recorded_at}', temp={self.temperature_c}°C)>"
        )


class PipelineRun(Base):
    """Audit log tracking every ETL pipeline run."""

    __tablename__ = "pipeline_runs"

    run_id = Column(BigInteger, primary_key=True, autoincrement=True)
    pipeline_name = Column(String(100), nullable=False)
    started_at = Column(DateTime(timezone=False), nullable=False)
    completed_at = Column(DateTime(timezone=False), nullable=True)
    status = Column(String(20), nullable=False)  # 'RUNNING', 'SUCCESS', 'FAILED', 'PARTIAL'
    records_extracted = Column(Integer, nullable=False, default=0)
    records_loaded = Column(Integer, nullable=False, default=0)
    error_message = Column(Text, nullable=True)

    # Relationships
    quality_logs = relationship(
        "DataQualityLog", back_populates="pipeline_run", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return (
            f"<PipelineRun(id={self.run_id}, status='{self.status}', "
            f"extracted={self.records_extracted}, loaded={self.records_loaded})>"
        )


class DataQualityLog(Base):
    """Data validation and quality issue tracking per pipeline execution."""

    __tablename__ = "data_quality_logs"

    quality_id = Column(BigInteger, primary_key=True, autoincrement=True)
    run_id = Column(
        BigInteger,
        ForeignKey("pipeline_runs.run_id", ondelete="SET NULL"),
        nullable=True,
    )
    table_name = Column(String(100), nullable=False)
    issue_type = Column(String(100), nullable=False)
    issue_count = Column(Integer, nullable=False)
    created_at = Column(
        DateTime(timezone=False),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    pipeline_run = relationship("PipelineRun", back_populates="quality_logs")

    def __repr__(self) -> str:
        return (
            f"<DataQualityLog(id={self.quality_id}, issue='{self.issue_type}', "
            f"count={self.issue_count})>"
        )
