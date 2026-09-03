import logging
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.repositories.weather_repository import WeatherRepository
from backend.schemas import (
    AnalyticsSummaryResponse,
    TemperatureTrendItem,
    HumidityTrendItem,
)

logger = logging.getLogger("weatherdata.analytics_routes")
router = APIRouter(prefix="/api/analytics", tags=["Analytics"])


@router.get("/summary", response_model=AnalyticsSummaryResponse)
def get_analytics_summary(db: Session = Depends(get_db)):
    """Retrieve warehouse KPI summary metrics (totals, temperature & humidity aggregates)."""
    try:
        return WeatherRepository.get_analytics_summary(db)
    except Exception as e:
        logger.error(f"Error fetching analytics summary: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to compute warehouse analytics summary.",
        )


@router.get("/temperature-trend", response_model=List[TemperatureTrendItem])
def get_temperature_trend(
    days: int = Query(7, ge=1, le=90, description="Number of past days for trend analysis"),
    db: Session = Depends(get_db),
):
    """Retrieve daily average, min, and max temperature aggregates for time-series charts."""
    try:
        return WeatherRepository.get_temperature_trend(db, days=days)
    except Exception as e:
        logger.error(f"Error fetching temperature trend: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve temperature trend data.",
        )


@router.get("/humidity-trend", response_model=List[HumidityTrendItem])
def get_humidity_trend(
    days: int = Query(7, ge=1, le=90, description="Number of past days for trend analysis"),
    db: Session = Depends(get_db),
):
    """Retrieve daily average humidity aggregates for time-series charts."""
    try:
        return WeatherRepository.get_humidity_trend(db, days=days)
    except Exception as e:
        logger.error(f"Error fetching humidity trend: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve humidity trend data.",
        )
